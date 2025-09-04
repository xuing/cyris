"""
Local VM Image Builder Service

Builds VM images locally using virt-builder and distributes to target hosts.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import os
import subprocess
import tempfile
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..domain.entities.guest import Guest
from ..domain.entities.host import Host
from ..core.exceptions import CyRISException
from ..core.rich_progress import RichProgressManager
from .providers.base_provider import ResourceCreationError

@dataclass
class BuildResult:
    """Result of image building operation"""
    success: bool
    image_path: Optional[str] = None
    error_message: Optional[str] = None
    build_time: float = 0.0

class LocalImageBuilder:
    """
    Local VM image builder using virt-builder and virt-install
    
    Workflow:
    1. Check local virt-builder availability
    2. Build base image with virt-builder
    3. Execute build-time tasks (add_account, modify_account)
    4. Distribute image to target hosts
    5. Create VMs on target hosts using virt-install
    """
    
    def __init__(self, work_dir: Optional[Path] = None):
        self.work_dir = work_dir or Path("/tmp/cyris-builds")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__, "image_builder")
        
        # Rich progress manager (can be set by KVM provider)
        self.progress_manager: Optional[RichProgressManager] = None
    
    def set_progress_manager(self, progress_manager: RichProgressManager) -> None:
        """Set progress manager for rich progress reporting"""
        self.progress_manager = progress_manager
    
    def check_local_dependencies(self) -> Dict[str, bool]:
        """Check availability of required tools on local machine"""
        tools = {}
        
        # First, ensure sudo authentication is cached
        try:
            self.logger.info("🔐 Checking sudo authentication for virt-builder tools...")
            self.logger.info("💡 You may be prompted for your password to run virt-builder commands.")
            result = subprocess.run(['sudo', '-v'], timeout=30)
            if result.returncode != 0:
                self.logger.error("Failed to authenticate with sudo")
                return {tool: False for tool in ['virt-builder', 'virt-install', 'virt-customize', 'supermin']}
        except subprocess.SubprocessError:
            self.logger.error("Failed to check sudo authentication")
            return {tool: False for tool in ['virt-builder', 'virt-install', 'virt-customize', 'supermin']}
        
        # Check libguestfs tools
        libguestfs_tools = ['virt-builder', 'virt-install', 'virt-customize']
        for tool in libguestfs_tools:
            try:
                # Use non-interactive sudo (should work with cached authentication)
                result = subprocess.run(['sudo', '-n', tool, '--version'], 
                                      capture_output=True, timeout=10)
                tools[tool] = result.returncode == 0
                self.logger.debug(f"Tool {tool}: {'available' if tools[tool] else 'not available'}")
            except (subprocess.SubprocessError, FileNotFoundError):
                tools[tool] = False
                self.logger.debug(f"Tool {tool}: not found")
        
        # Check supermin specifically (critical for libguestfs functionality)
        try:
            result = subprocess.run(['which', 'supermin'], capture_output=True, timeout=5)
            tools['supermin'] = result.returncode == 0
            if tools['supermin']:
                # Test supermin functionality
                test_result = subprocess.run(['supermin', '--version'], 
                                           capture_output=True, timeout=5)
                tools['supermin'] = test_result.returncode == 0
                
            self.logger.debug(f"Tool supermin: {'available' if tools['supermin'] else 'not available'}")
        except (subprocess.SubprocessError, FileNotFoundError):
            tools['supermin'] = False
            self.logger.debug("Tool supermin: not found")
        
        # Check libguestfs-test-tool availability for diagnostics
        try:
            result = subprocess.run(['which', 'libguestfs-test-tool'], 
                                  capture_output=True, timeout=5)
            tools['libguestfs-test-tool'] = result.returncode == 0
            self.logger.debug(f"Tool libguestfs-test-tool: {'available' if tools['libguestfs-test-tool'] else 'not available'}")
        except (subprocess.SubprocessError, FileNotFoundError):
            tools['libguestfs-test-tool'] = False
            self.logger.debug("Tool libguestfs-test-tool: not found")
            
        return tools
    
    def get_available_images(self) -> List[str]:
        """Get list of available virt-builder images"""
        try:
            # Use cached sudo authentication for virt-builder --list
            result = subprocess.run(['sudo', '-n', 'virt-builder', '--list'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # Parse virt-builder --list output
                lines = result.stdout.strip().split('\n')
                images = []
                for line in lines:  # Don't skip any lines - no header in virt-builder --list
                    if line.strip() and not line.startswith(' '):
                        # Get the first word which is the image name
                        image_name = line.split()[0]
                        images.append(image_name)
                self.logger.debug(f"Found {len(images)} available images")
                return images
            else:
                self.logger.warning(f"virt-builder --list failed: {result.stderr}")
                return []
        except subprocess.SubprocessError as e:
            self.logger.warning(f"Failed to get image list: {e}")
            return []
    
    def build_image_locally(self, guest: Guest, build_only: bool = False) -> BuildResult:
        """Build VM image locally using virt-builder with Rich progress tracking"""
        start_time = time.time()
        
        start_msg = f"🔧 Starting image build for guest '{guest.guest_id}'"
        params_msg = f"📋 Build parameters: image={guest.image_name}, vcpus={guest.vcpus}, memory={guest.memory}, disk={guest.disk_size}"
        
        if self.progress_manager:
            self.progress_manager.log_info(start_msg)
            self.progress_manager.log_info(params_msg)
        else:
            self.logger.info(start_msg)
            self.logger.info(params_msg)
        
        if not self._validate_build_requirements(guest):
            error_msg = "Build requirements validation failed"
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
            
            return BuildResult(
                success=False,
                error_message=error_msg,
                build_time=time.time() - start_time
            )
        
        image_path = self.work_dir / f"{guest.guest_id}-{guest.image_name}.qcow2"
        path_msg = f"📁 Output image path: {image_path}"
        
        if self.progress_manager:
            self.progress_manager.log_info(path_msg)
        else:
            self.logger.info(path_msg)
        
        try:
            # Build base image with virt-builder (using cached sudo authentication)
            build_cmd = [
                'sudo', '-n', 'virt-builder', guest.image_name,
                '--size', guest.disk_size,
                '--format', 'qcow2',
                '--output', str(image_path)
            ]
            
            # Add libguestfs debugging environment for better error reporting
            build_env = os.environ.copy()
            build_env.update({
                'LIBGUESTFS_DEBUG': '1',
                'LIBGUESTFS_TRACE': '1',
                'TMPDIR': '/tmp'  # Ensure writable temp directory
            })
            
            cmd_msg = f"🚀 Executing virt-builder command:"
            cmd_detail = f"    {' '.join(build_cmd)}"
            time_msg = f"⏳ This may take several minutes for image download and creation..."
            
            if self.progress_manager:
                self.progress_manager.log_info(cmd_msg)
                self.progress_manager.log_command(' '.join(build_cmd))
                self.progress_manager.log_info(time_msg)
            else:
                self.logger.info(cmd_msg)
                self.logger.info(cmd_detail)
                self.logger.info(time_msg)
            
            # Execute with progress monitoring (allow interactive sudo)
            if self.progress_manager:
                result = self._run_command_with_progress(build_cmd, "Building VM image", timeout=600, env=build_env)
            else:
                # Use cached sudo authentication for virt-builder
                result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=600, env=build_env)
            
            # Enhanced debugging: Log return code immediately
            debug_msg = f"🔍 virt-builder completed with return code: {result.returncode}"
            if self.progress_manager:
                self.progress_manager.log_info(debug_msg)
            else:
                self.logger.info(debug_msg)
            
            # Log command output for debugging
            if result.stdout:
                if self.progress_manager:
                    self.progress_manager.log_info(f"virt-builder output: {result.stdout[:200]}...") 
                else:
                    self.logger.debug(f"virt-builder stdout: {result.stdout}")
            if result.stderr:
                # Always log stderr for failed commands, regardless of whether it's treated as progress
                stderr_msg = f"virt-builder stderr: {result.stderr[:500]}..."
                if result.returncode == 0:
                    # virt-builder often outputs progress to stderr even on success
                    if self.progress_manager:
                        self.progress_manager.log_info(f"virt-builder progress: {result.stderr[:200]}...")
                    else:
                        self.logger.debug(stderr_msg)
                else:
                    if self.progress_manager:
                        self.progress_manager.log_error(stderr_msg)
                    else:
                        self.logger.error(stderr_msg)
            
            # CRITICAL: Check for libguestfs/supermin errors even if return code is 0
            has_libguestfs_error = (result.stderr and 
                                  ('libguestfs error' in result.stderr or 
                                   'supermin exited with error' in result.stderr or
                                   'virt-resize: error' in result.stderr))
            
            if result.returncode != 0 or has_libguestfs_error:
                error_reason = "exit code" if result.returncode != 0 else "libguestfs error"
                error_msg = f"virt-builder failed ({error_reason} {result.returncode}): {result.stderr}"
                if self.progress_manager:
                    self.progress_manager.log_error(error_msg)
                    if has_libguestfs_error:
                        self.progress_manager.log_error("🔧 Libguestfs troubleshooting:")
                        self.progress_manager.log_error("   1. sudo apt-get update && sudo apt-get install libguestfs-tools supermin")
                        self.progress_manager.log_error("   2. Run: libguestfs-test-tool (if available)")
                        self.progress_manager.log_error("   3. Check /tmp permissions and disk space")
                    else:
                        self.progress_manager.log_error("💡 Try running: sudo apt-get update && sudo apt-get install libguestfs-tools")
                else:
                    self.logger.error(error_msg)
                
                return BuildResult(
                    success=False,
                    error_message=error_msg,
                    build_time=time.time() - start_time
                )
            
            # Check if output file was created
            if not image_path.exists():
                error_msg = f"virt-builder succeeded but output file not found: {image_path}"
                if self.progress_manager:
                    self.progress_manager.log_error(error_msg)
                    
                return BuildResult(
                    success=False,
                    error_message=error_msg,
                    build_time=time.time() - start_time
                )
            
            image_size = image_path.stat().st_size
            success_msg = f"✅ Base image built successfully: {image_path}"
            size_msg = f"📏 Image size: {image_size / 1024 / 1024:.1f} MB"
            
            if self.progress_manager:
                self.progress_manager.log_success(success_msg)
                self.progress_manager.log_info(size_msg)
            else:
                self.logger.info(success_msg)
                self.logger.info(size_msg)
            
            # Execute build-time tasks
            if guest.tasks:
                tasks_msg = f"📝 Executing {len(guest.tasks)} build-time tasks"
                if self.progress_manager:
                    self.progress_manager.log_info(tasks_msg)
                else:
                    self.logger.info(tasks_msg)
                    
                self._execute_build_time_tasks(image_path, guest.tasks)
            else:
                no_tasks_msg = f"📝 No build-time tasks to execute"
                if self.progress_manager:
                    self.progress_manager.log_info(no_tasks_msg)
                else:
                    self.logger.info(no_tasks_msg)
            
            build_time = time.time() - start_time
            
            if build_only:
                # In build-only mode, provide clear success message and file location
                completion_msg = f"🎉 Image build completed successfully in {build_time:.1f}s"
                location_msg = f"📁 Image saved at: {image_path}"
                preserve_msg = f"🔒 File preserved for later use (--build-only mode)"
                
                if self.progress_manager:
                    self.progress_manager.log_success(completion_msg)
                    self.progress_manager.log_success(location_msg)
                    self.progress_manager.log_info(preserve_msg)
                else:
                    self.logger.info(completion_msg)
                    self.logger.info(location_msg)
                    self.logger.info(preserve_msg)
            else:
                completion_msg = f"🎉 Image build completed successfully in {build_time:.1f}s"
                if self.progress_manager:
                    self.progress_manager.log_success(completion_msg)
                else:
                    self.logger.info(completion_msg)
            
            return BuildResult(
                success=True,
                image_path=str(image_path),
                build_time=build_time
            )
            
        except subprocess.TimeoutExpired:
            timeout_msg = f"⏰ virt-builder timed out after 10 minutes"
            if self.progress_manager:
                self.progress_manager.log_error(timeout_msg)
            else:
                self.logger.error(timeout_msg)
                
            return BuildResult(
                success=False,
                error_message="virt-builder timeout after 10 minutes",
                build_time=time.time() - start_time
            )
        except Exception as e:
            error_msg = f"💥 Build failed with exception: {str(e)}"
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
            else:
                self.logger.error(error_msg)
                
            return BuildResult(
                success=False,
                error_message=f"Build failed: {str(e)}",
                build_time=time.time() - start_time
            )
    
    def _run_command_with_progress(self, cmd: List[str], description: str, timeout: int = 300, env=None):
        """Run a command with progress monitoring"""
        import threading
        
        # Start process (allow interactive sudo password input)
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            stdin=None,  # Allow interactive password input
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        
        # Create a simple spinner effect for long-running commands
        if self.progress_manager:
            # Add indeterminate progress step
            step_id = f"cmd_{int(time.time())}"
            self.progress_manager.start_step(step_id, description)
        
        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            
            if self.progress_manager:
                if process.returncode == 0:
                    self.progress_manager.complete_step(step_id)
                else:
                    self.progress_manager.fail_step(step_id, f"Command failed with exit code {process.returncode}")
            
            # Create result object that matches subprocess.run
            class CommandResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr
            
            return CommandResult(process.returncode, stdout, stderr)
            
        except subprocess.TimeoutExpired:
            process.kill()
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
            
            raise subprocess.TimeoutExpired(cmd, timeout)
    
    def distribute_image_to_host(self, image_path: str, target_host: Host, 
                               remote_path: str) -> bool:
        """Copy built image to target host using scp"""
        try:
            scp_cmd = [
                'scp', '-o', 'StrictHostKeyChecking=no',
                image_path,
                f"{target_host.account}@{target_host.mgmt_addr}:{remote_path}"
            ]
            
            self.logger.info(f"Distributing image to {target_host.host_id}: {image_path} -> {remote_path}")
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.info(f"Image distributed successfully to {target_host.host_id}")
                return True
            else:
                self.logger.error(f"SCP failed: {result.stderr}")
                return False
                
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to distribute image: {e}")
            return False
    
    def _validate_build_requirements(self, guest: Guest) -> bool:
        """Validate that all requirements for building are met"""
        # Check local tools
        deps = self.check_local_dependencies()
        if not deps.get('virt-builder', False):
            error_msg = "virt-builder not available locally"
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
                self.progress_manager.log_error("💡 Install: sudo apt-get install libguestfs-tools")
            else:
                self.logger.error(error_msg)
            return False
        
        if not deps.get('supermin', False):
            error_msg = "supermin not available - critical for libguestfs functionality"
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
                self.progress_manager.log_error("💡 Install: sudo apt-get install supermin")
            else:
                self.logger.error(error_msg)
            return False
        
        if not deps.get('virt-customize', False):
            warning_msg = "virt-customize not available - tasks may not execute"
            if self.progress_manager:
                self.progress_manager.log_warning(warning_msg)
            else:
                self.logger.warning(warning_msg)
        
        # Check image availability
        available_images = self.get_available_images()
        if guest.image_name not in available_images:
            error_msg = f"Image '{guest.image_name}' not available. Available: {available_images[:5]}..."
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
                self.progress_manager.log_error("💡 Run 'virt-builder --list' to see all available images")
            else:
                self.logger.error(error_msg)
            return False
        
        # Validate required kvm-auto fields
        required_fields = ['image_name', 'vcpus', 'memory', 'disk_size']
        missing = [f for f in required_fields if not getattr(guest, f)]
        if missing:
            error_msg = f"Missing required kvm-auto fields: {missing}"
            if self.progress_manager:
                self.progress_manager.log_error(error_msg)
            else:
                self.logger.error(error_msg)
            return False
        
        return True
    
    def _execute_build_time_tasks(self, image_path: str, tasks: List[Dict[str, Any]]) -> None:
        """Execute build-time tasks using virt-customize"""
        for task in tasks:
            try:
                # Handle add_account tasks - maintain original YAML structure
                if 'add_account' in task:
                    accounts = task['add_account']
                    for account_info in accounts:
                        self._add_account_to_image(image_path, account_info)
                
                # Handle modify_account tasks
                elif 'modify_account' in task:
                    accounts = task['modify_account']  
                    for account_info in accounts:
                        self._modify_account_in_image(image_path, account_info)
                
                else:
                    self.logger.warning(f"Unsupported build-time task type: {list(task.keys())}")
                    
            except Exception as e:
                self.logger.error(f"Failed to execute task {task}: {e}")
    
    def _add_account_to_image(self, image_path: str, account_info: Dict[str, str]) -> None:
        """Add user account to image using virt-customize"""
        account = account_info.get('account')
        passwd = account_info.get('passwd')
        
        if not account or not passwd:
            self.logger.warning(f"Invalid account info: {account_info}")
            return
        
        try:
            # Create user and set password (using cached sudo authentication)
            cmd = [
                'sudo', '-n', 'virt-customize', '-a', str(image_path),
                '--run-command', f'useradd -m {account}',
                '--password', f'{account}:password:{passwd}'
            ]
            
            self.logger.debug(f"Adding account: {account}")
            # Use cached sudo authentication for virt-customize
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.logger.error(f"Failed to add account {account}: {result.stderr}")
            else:
                self.logger.info(f"Successfully added account: {account}")
                
        except subprocess.SubprocessError as e:
            self.logger.error(f"Error adding account {account}: {e}")
    
    def _modify_account_in_image(self, image_path: str, account_info: Dict[str, str]) -> None:
        """Modify user account in image using virt-customize"""
        account = account_info.get('account')
        new_passwd = account_info.get('new_passwd')
        
        if not account or not new_passwd:
            self.logger.warning(f"Invalid account modification info: {account_info}")
            return
        
        try:
            cmd = [
                'sudo', 'virt-customize', '-a', str(image_path),
                '--password', f'{account}:password:{new_passwd}'
            ]
            
            self.logger.debug(f"Modifying account: {account}")
            # Use cached sudo authentication for virt-customize
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.logger.error(f"Failed to modify account {account}: {result.stderr}")
            else:
                self.logger.info(f"Successfully modified account: {account}")
                
        except subprocess.SubprocessError as e:
            self.logger.error(f"Error modifying account {account}: {e}")
    
    def cleanup_build_files(self, image_path: str) -> None:
        """Clean up build artifacts"""
        try:
            Path(image_path).unlink(missing_ok=True)
            self.logger.debug(f"Cleaned up build file: {image_path}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup {image_path}: {e}")