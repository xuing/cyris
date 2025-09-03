"""
Local VM Image Builder Service

Builds VM images locally using virt-builder and distributes to target hosts.
"""

import logging
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
        self.logger = logging.getLogger(__name__)
    
    def check_local_dependencies(self) -> Dict[str, bool]:
        """Check availability of required tools on local machine"""
        tools = {}
        for tool in ['virt-builder', 'virt-install', 'virt-customize']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, timeout=10)
                tools[tool] = result.returncode == 0
                self.logger.debug(f"Tool {tool}: {'available' if tools[tool] else 'not available'}")
            except (subprocess.SubprocessError, FileNotFoundError):
                tools[tool] = False
                self.logger.debug(f"Tool {tool}: not found")
        return tools
    
    def get_available_images(self) -> List[str]:
        """Get list of available virt-builder images"""
        try:
            result = subprocess.run(['virt-builder', '--list'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # Parse virt-builder --list output
                lines = result.stdout.strip().split('\n')
                images = []
                for line in lines[1:]:  # Skip header
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
    
    def build_image_locally(self, guest: Guest) -> BuildResult:
        """Build VM image locally using virt-builder"""
        start_time = time.time()
        
        if not self._validate_build_requirements(guest):
            return BuildResult(
                success=False,
                error_message="Build requirements validation failed",
                build_time=time.time() - start_time
            )
        
        image_path = self.work_dir / f"{guest.guest_id}-{guest.image_name}.qcow2"
        
        try:
            # Build base image with virt-builder
            build_cmd = [
                'virt-builder', guest.image_name,
                '--size', guest.disk_size,
                '--format', 'qcow2',
                '--output', str(image_path)
            ]
            
            self.logger.info(f"Building image: {' '.join(build_cmd)}")
            result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                return BuildResult(
                    success=False,
                    error_message=f"virt-builder failed: {result.stderr}",
                    build_time=time.time() - start_time
                )
            
            self.logger.info(f"Base image built successfully: {image_path}")
            
            # Execute build-time tasks
            if guest.tasks:
                self.logger.info(f"Executing {len(guest.tasks)} build-time tasks")
                self._execute_build_time_tasks(image_path, guest.tasks)
            
            return BuildResult(
                success=True,
                image_path=str(image_path),
                build_time=time.time() - start_time
            )
            
        except subprocess.TimeoutExpired:
            return BuildResult(
                success=False,
                error_message="virt-builder timeout after 10 minutes",
                build_time=time.time() - start_time
            )
        except Exception as e:
            return BuildResult(
                success=False,
                error_message=f"Build failed: {str(e)}",
                build_time=time.time() - start_time
            )
    
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
            self.logger.error("virt-builder not available locally")
            return False
        
        if not deps.get('virt-customize', False):
            self.logger.warning("virt-customize not available - tasks may not execute")
        
        # Check image availability
        available_images = self.get_available_images()
        if guest.image_name not in available_images:
            self.logger.error(f"Image '{guest.image_name}' not available. "
                            f"Available: {available_images[:5]}...")
            return False
        
        # Validate required kvm-auto fields
        required_fields = ['image_name', 'vcpus', 'memory', 'disk_size']
        missing = [f for f in required_fields if not getattr(guest, f)]
        if missing:
            self.logger.error(f"Missing required kvm-auto fields: {missing}")
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
            # Create user and set password
            cmd = [
                'virt-customize', '-a', str(image_path),
                '--run-command', f'useradd -m {account}',
                '--password', f'{account}:password:{passwd}'
            ]
            
            self.logger.debug(f"Adding account: {account}")
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
                'virt-customize', '-a', str(image_path),
                '--password', f'{account}:password:{new_passwd}'
            ]
            
            self.logger.debug(f"Modifying account: {account}")
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