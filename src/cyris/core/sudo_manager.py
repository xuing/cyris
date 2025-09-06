"""
Sudo Permission Manager

Handles sudo authentication and permission caching for CyRIS operations.
Provides a seamless way to request and manage sudo privileges for tools like virt-builder.
"""

import subprocess
import time
import getpass
import sys
import os
from typing import Optional, Tuple, Dict, List, Any
from pathlib import Path

try:
    from .unified_logger import get_logger
    from .rich_progress import RichProgressManager
    from .streaming_executor import StreamingCommandExecutor
except ImportError:
    # Fallback for testing
    import logging
    get_logger = lambda name, module: logging.getLogger(f"{name}.{module}")
    RichProgressManager = None
    StreamingCommandExecutor = None


class SudoPermissionManager:
    """
    Manages sudo permissions and authentication for CyRIS operations.
    
    This class provides methods to:
    - Check current sudo authentication status
    - Request sudo privileges with user-friendly prompts
    - Cache and monitor sudo session timeout
    - Provide fallback options for different authentication scenarios
    """
    
    def __init__(self, progress_manager: Optional[RichProgressManager] = None):
        """
        Initialize the sudo permission manager.
        
        Args:
            progress_manager: RichProgressManager for UI integration
        """
        self.progress_manager = progress_manager
        self.logger = get_logger(__name__, "sudo_manager")
        self._last_check_time = 0
        self._last_status = None
        
        # Initialize streaming executor for PTY-enabled sudo commands
        if StreamingCommandExecutor:
            self.command_executor = StreamingCommandExecutor(
                progress_manager=progress_manager,
                logger=self.logger
            )
        else:
            self.command_executor = None
    
    def check_sudo_status(self, cache_seconds: int = 5) -> bool:
        """
        Check if sudo privileges are currently available without prompting.
        
        Args:
            cache_seconds: Cache the result for this many seconds
            
        Returns:
            True if sudo is available without password, False otherwise
        """
        current_time = time.time()
        
        # Use cached result if recent
        if (current_time - self._last_check_time) < cache_seconds and self._last_status is not None:
            return self._last_status
        
        try:
            # Use sudo -n (non-interactive) to test current privileges
            result = subprocess.run(
                ['sudo', '-n', 'true'], 
                capture_output=True, 
                timeout=3
            )
            
            status = result.returncode == 0
            self._last_check_time = current_time
            self._last_status = status
            
            if status:
                self.logger.debug("Sudo privileges confirmed (cached)")
            else:
                self.logger.debug("Sudo privileges not available (authentication required)")
                
            return status
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            self.logger.warning(f"Sudo status check failed: {e}")
            return False
    
    def get_sudo_cache_info(self) -> Tuple[bool, Optional[int]]:
        """
        Get information about sudo cache status and remaining time.
        
        Returns:
            Tuple of (has_privileges, estimated_remaining_minutes)
        """
        if not self.check_sudo_status():
            return False, None
        
        try:
            # Try to get more detailed sudo status (this is approximate)
            # Sudo typically caches for 15 minutes by default
            result = subprocess.run(
                ['sudo', '-n', '-v'],
                capture_output=True,
                timeout=3
            )
            
            if result.returncode == 0:
                # Estimate remaining time (sudo default is 15 minutes)
                # This is approximate since we can't get exact timing
                return True, 10  # Conservative estimate
            else:
                return False, None
                
        except Exception:
            # If we can't get detailed info, just return basic status
            return True, None
    
    def request_sudo_access(self, reason: str = "CyRIS operations") -> bool:
        """
        Request sudo privileges with user-friendly prompting.
        
        Args:
            reason: Human-readable reason for requesting sudo
            
        Returns:
            True if sudo access granted, False otherwise
        """
        # First check if we already have access
        if self.check_sudo_status():
            self.logger.info("✅ Sudo privileges already available")
            return True
        
        # Provide user-friendly explanation
        self._show_sudo_request_message(reason)
        
        try:
            # Try PTY-enabled executor first for proper password prompting
            if self.command_executor:
                result = self.command_executor.execute_with_realtime_output(
                    cmd=['sudo', '-v'],
                    description=f"Requesting sudo privileges: {reason}",
                    timeout=60,
                    use_pty=True,
                    allow_password_prompt=True
                )
                success = result.returncode == 0
                
                # If PTY method failed with terminal error, try stdin fallback
                # Note: In PTY mode, stderr is merged into stdout, so check both
                terminal_error_detected = False
                if not success:
                    # Check both stdout and stderr for terminal-related errors
                    error_indicators = [
                        "terminal is required",
                        "a password is required", 
                        "askpass helper"
                    ]
                    
                    combined_output = (result.stdout or '') + (result.stderr or '')
                    terminal_error_detected = any(indicator in combined_output for indicator in error_indicators)
                
                if terminal_error_detected:
                    if self.logger:
                        self.logger.info("🔄 PTY method failed with terminal error, trying stdin fallback...")
                    success = self._request_sudo_with_stdin_fallback()
            else:
                # Fallback to stdin method for testing environments
                success = self._request_sudo_with_stdin_fallback()
            
            if success:
                self._show_sudo_success_message()
                # Clear cached status to force recheck
                self._last_status = None
                return True
            else:
                self._show_sudo_failure_message()
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("⏰ Sudo authentication timed out")
            if self.progress_manager:
                self.progress_manager.log_error("⏰ Sudo authentication timed out (60 seconds)")
            return False
        except Exception as e:
            self.logger.error(f"Sudo authentication failed: {e}")
            if self.progress_manager:
                self.progress_manager.log_error(f"❌ Sudo authentication failed: {e}")
            return False
    
    def ensure_sudo_access(self, operation: str, required_commands: list = None) -> bool:
        """
        Ensure sudo access is available for a specific operation.
        
        Args:
            operation: Description of the operation requiring sudo
            required_commands: List of commands that will need sudo (optional)
            
        Returns:
            True if sudo access is ensured, False otherwise
        """
        if required_commands is None:
            required_commands = []
        
        # Check current status
        has_access, remaining_time = self.get_sudo_cache_info()
        
        if has_access:
            if remaining_time:
                self.logger.info(f"✅ Sudo access available (≈{remaining_time} minutes remaining)")
                if self.progress_manager:
                    self.progress_manager.log_success(f"✅ Sudo privileges cached (≈{remaining_time} min remaining)")
            else:
                self.logger.info("✅ Sudo access available")
                if self.progress_manager:
                    self.progress_manager.log_success("✅ Sudo privileges available")
            return True
        
        # Need to request access
        operation_desc = f"{operation}"
        if required_commands:
            operation_desc += f" (commands: {', '.join(required_commands)})"
            
        return self.request_sudo_access(operation_desc)
    
    def _show_sudo_request_message(self, reason: str):
        """Show user-friendly sudo request message."""
        messages = [
            "🔐 Sudo Permission Request",
            f"📋 Purpose: {reason}",
            "💡 Please enter your password to continue (privileges will be cached ~15 minutes)",
            ""
        ]
        
        if self.progress_manager:
            for msg in messages:
                if msg:
                    self.progress_manager.log_info(msg)
                else:
                    self.progress_manager.console.print()
        else:
            for msg in messages:
                if msg:
                    self.logger.info(msg)
                else:
                    print()
    
    def _show_sudo_success_message(self):
        """Show success message after sudo authentication."""
        msg = "✅ Sudo permissions verified successfully!"
        
        if self.progress_manager:
            self.progress_manager.log_success(msg)
        else:
            self.logger.info(msg)
    
    def _show_sudo_failure_message(self):
        """Show failure message and suggestions."""
        messages = [
            "❌ Sudo permission verification failed",
            "💡 Possible solutions:",
            "   1. Check if password is correct",
            "   2. Confirm user is in sudo group: groups $USER",
            "   3. Configure passwordless sudo (recommended): sudo visudo",
            "   4. Use --skip-sudo-check to skip checks (if applicable)"
        ]
        
        if self.progress_manager:
            self.progress_manager.log_error(messages[0])
            for msg in messages[1:]:
                self.progress_manager.log_info(msg)
        else:
            for msg in messages:
                self.logger.error(msg) if msg.startswith("❌") else self.logger.info(msg)
    
    def check_specific_command_access(self, command: str) -> bool:
        """
        Check if a specific command can be run with sudo without prompting.
        
        Args:
            command: Command to test (e.g., 'virt-builder')
            
        Returns:
            True if command can be run with sudo, False otherwise
        """
        try:
            # Try to run the command with sudo -n and a safe operation
            if command == 'virt-builder':
                # Test with --help which is safe and fast
                test_cmd = ['sudo', '-n', command, '--help']
            else:
                # For other commands, try a version check or help
                test_cmd = ['sudo', '-n', command, '--version']
            
            result = subprocess.run(
                test_cmd,
                capture_output=True,
                timeout=5
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"Command access check failed for {command}: {e}")
            return False
    
    def validate_virt_builder_access(self) -> bool:
        """
        Specifically validate virt-builder sudo access.
        
        Returns:
            True if virt-builder can be run with sudo, False otherwise
        """
        return self.check_specific_command_access('virt-builder')
    
    def _request_sudo_with_stdin_fallback(self) -> bool:
        """
        Fallback method to request sudo using stdin input (-S option).
        
        This method is used when PTY is not available or fails.
        
        Returns:
            True if sudo authentication succeeded, False otherwise
        """
        try:
            # Check if we're in an interactive environment
            if not sys.stdin.isatty():
                if self.logger:
                    self.logger.warning("⚠️ Not in interactive terminal, cannot prompt for password")
                return False
            
            # Prompt user for password using getpass (secure input)
            try:
                password = getpass.getpass("🔐 Enter your password for sudo: ")
                if not password:
                    if self.logger:
                        self.logger.warning("No password entered")
                    return False
            except (KeyboardInterrupt, EOFError):
                if self.logger:
                    self.logger.info("Password prompt cancelled by user")
                return False
            
            # Use sudo -S to read password from stdin
            process = subprocess.Popen(
                ['sudo', '-S', '-v'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send password to sudo via stdin with timeout
            stdout, stderr = process.communicate(input=password + '\n', timeout=30)
            
            # Clear password from memory
            password = None
            
            success = process.returncode == 0
            
            if success:
                if self.logger:
                    self.logger.info("✅ Sudo authentication successful via stdin method")
            else:
                if self.logger:
                    self.logger.warning(f"❌ Sudo authentication failed via stdin: {stderr}")
            
            return success
            
        except subprocess.TimeoutExpired:
            if self.logger:
                self.logger.error("⏰ Sudo stdin authentication timed out")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Stdin sudo authentication failed: {e}")
            return False
    
    def detect_execution_environment(self) -> Dict[str, Any]:
        """
        Detect the current execution environment to provide appropriate guidance.
        
        Returns:
            Dictionary with environment information and capabilities
        """
        env_info = {
            'is_interactive': sys.stdin.isatty() and sys.stdout.isatty(),
            'is_ssh_session': bool(os.environ.get('SSH_CLIENT') or os.environ.get('SSH_CONNECTION')),
            'has_display': bool(os.environ.get('DISPLAY')),
            'terminal_type': os.environ.get('TERM', 'unknown'),
            'user': os.environ.get('USER', 'unknown'),
            'has_sudo_askpass': bool(os.environ.get('SUDO_ASKPASS')),
            'python_executable': sys.executable,
            'working_directory': os.getcwd()
        }
        
        # Determine recommended authentication method
        if env_info['is_interactive']:
            if self.command_executor:
                env_info['recommended_method'] = 'enhanced_pty'
                env_info['fallback_method'] = 'stdin'
            else:
                env_info['recommended_method'] = 'stdin'
        else:
            env_info['recommended_method'] = 'passwordless_sudo'
            env_info['fallback_method'] = 'askpass_helper'
        
        return env_info
    
    def provide_setup_guidance(self) -> List[str]:
        """
        Provide setup guidance based on current environment.
        
        Returns:
            List of setup recommendations and commands
        """
        env_info = self.detect_execution_environment()
        guidance = []
        
        guidance.append("🔧 Sudo Setup Recommendations:")
        guidance.append("")
        
        if env_info['is_interactive']:
            guidance.append("✅ Interactive terminal detected - password prompting should work")
            guidance.append("")
            guidance.append("📋 For better experience, consider setting up passwordless sudo:")
            guidance.append("   1. Run: sudo visudo")
            guidance.append(f"   2. Add: {env_info['user']} ALL=(ALL) NOPASSWD: /usr/bin/virt-builder")
            guidance.append(f"   3. Or for all commands: {env_info['user']} ALL=(ALL) NOPASSWD: ALL")
            guidance.append("")
        else:
            guidance.append("⚠️ Non-interactive environment detected")
            guidance.append("")
            guidance.append("🔧 Required: Set up passwordless sudo")
            guidance.append("   1. Run (from interactive terminal): sudo visudo")
            guidance.append(f"   2. Add: {env_info['user']} ALL=(ALL) NOPASSWD: /usr/bin/virt-builder")
            guidance.append("")
            guidance.append("🔄 Alternative: Set up askpass helper")
            guidance.append("   1. Create askpass script: /usr/local/bin/cyris-askpass")
            guidance.append("   2. Set environment: export SUDO_ASKPASS=/usr/local/bin/cyris-askpass")
            guidance.append("")
        
        if env_info['is_ssh_session']:
            guidance.append("🔗 SSH session detected")
            guidance.append("   • Ensure SSH connection allows TTY: ssh -t user@host")
            guidance.append("   • Check SSH configuration: AllowTTY yes")
            guidance.append("")
        
        # Environment-specific troubleshooting
        guidance.append("🔍 Troubleshooting:")
        guidance.append(f"   • Terminal type: {env_info['terminal_type']}")
        guidance.append(f"   • Interactive: {env_info['is_interactive']}")
        guidance.append(f"   • SSH session: {env_info['is_ssh_session']}")
        guidance.append(f"   • Recommended method: {env_info['recommended_method']}")
        
        return guidance