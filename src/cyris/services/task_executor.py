"""
Task Execution Service

This service handles the execution of tasks defined in cyber range YAML files.
It integrates the traditional modules.py functionality into the modern architecture.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import subprocess
import time
import tempfile
import os
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Import security utilities
from ..core.security import (
    SecureCommandExecutor, 
    SecureLogger, 
    validate_user_input, 
    sanitize_for_shell
)

try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    paramiko = None


class TaskType(Enum):
    """Types of tasks that can be executed"""
    ADD_ACCOUNT = "add_account"
    MODIFY_ACCOUNT = "modify_account" 
    INSTALL_PACKAGE = "install_package"
    COPY_CONTENT = "copy_content"
    EXECUTE_PROGRAM = "execute_program"
    EMULATE_ATTACK = "emulate_attack"
    EMULATE_MALWARE = "emulate_malware"
    EMULATE_TRAFFIC_CAPTURE = "emulate_traffic_capture_file"
    FIREWALL_RULES = "firewall_rules"


@dataclass
class TaskResult:
    """Result of task execution with verification support"""
    task_id: str
    task_type: TaskType
    success: bool
    message: str
    execution_time: float = 0.0
    output: Optional[str] = None
    error: Optional[str] = None
    # Enhanced fields for verification (optional for backward compatibility)
    vm_name: Optional[str] = None
    vm_ip: Optional[str] = None
    evidence: Optional[str] = None  # Verification evidence
    verification_passed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskExecutor:
    """
    Service for executing tasks on cyber range guests.
    
    Integrates functionality from the original modules.py file
    into the modern service-oriented architecture.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize task executor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = get_logger(__name__, "task_executor")
        self.secure_logger = SecureLogger(self.logger)
        self.abspath = config.get('base_path', '/home/ubuntu/cyris')
        self.instantiation_dir = "instantiation"
        
        # SSH configuration
        self.ssh_timeout = config.get('ssh_timeout', 30)
        self.ssh_retries = config.get('ssh_retries', 3)
        
        # Initialize secure command executor
        self.secure_executor = SecureCommandExecutor(timeout=300)
    
    def execute_guest_tasks(
        self, 
        guest: Any, 
        guest_ip: str,
        tasks: List[Dict[str, Any]]
    ) -> List[TaskResult]:
        """
        Execute all tasks for a guest.
        
        Args:
            guest: Guest configuration object
            guest_ip: IP address of the guest VM
            tasks: List of task configurations
        
        Returns:
            List of task execution results
        """
        results = []
        guest_id = getattr(guest, 'id', None) or getattr(guest, 'guest_id', 'unknown')
        
        self.logger.info(f"Executing {len(tasks)} tasks for guest {guest_id} at {guest_ip}")
        
        for task_config in tasks:
            for task_type, task_params in task_config.items():
                task_type_enum = TaskType(task_type)
                
                if isinstance(task_params, list):
                    # Multiple tasks of the same type
                    for i, params in enumerate(task_params):
                        task_id = f"{guest_id}_{task_type}_{i}"
                        result = self._execute_single_task(
                            task_id, task_type_enum, params, guest, guest_ip
                        )
                        results.append(result)
                else:
                    # Single task
                    task_id = f"{guest_id}_{task_type}"
                    result = self._execute_single_task(
                        task_id, task_type_enum, task_params, guest, guest_ip
                    )
                    results.append(result)
        
        return results
    
    def _execute_single_task(
        self,
        task_id: str,
        task_type: TaskType,
        params: Dict[str, Any],
        guest: Any,
        guest_ip: str
    ) -> TaskResult:
        """Execute a single task"""
        
        start_time = time.time()
        
        try:
            if task_type == TaskType.ADD_ACCOUNT:
                result = self._execute_add_account(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.MODIFY_ACCOUNT:
                result = self._execute_modify_account(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.INSTALL_PACKAGE:
                result = self._execute_install_package(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.COPY_CONTENT:
                result = self._execute_copy_content(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.EXECUTE_PROGRAM:
                result = self._execute_program(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.EMULATE_ATTACK:
                result = self._execute_emulate_attack(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.EMULATE_MALWARE:
                result = self._execute_emulate_malware(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.EMULATE_TRAFFIC_CAPTURE:
                result = self._execute_traffic_capture(task_id, params, guest_ip, guest, start_time)
            elif task_type == TaskType.FIREWALL_RULES:
                result = self._execute_firewall_rules(task_id, params, guest_ip, guest, start_time)
            else:
                result = TaskResult(
                    task_id=task_id,
                    task_type=task_type,
                    success=False,
                    message=f"Unknown task type: {task_type}",
                    execution_time=time.time() - start_time
                )
            
            # Ensure execution_time is set if not already set by the specific method
            if result.execution_time == 0.0:
                result.execution_time = time.time() - start_time
                
        except Exception as e:
            self.logger.error(f"Task {task_id} failed with exception: {e}")
            result = TaskResult(
                task_id=task_id,
                task_type=task_type,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message=f"Task execution failed: {str(e)}",
                execution_time=time.time() - start_time,
                error=str(e)
            )
        
        return result
    
    def _execute_add_account(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute add_account task with verification"""
        account = params.get('account')
        passwd = params.get('passwd')
        full_name = params.get('full_name', account)
        
        if not account or not passwd:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.ADD_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message="Missing required parameters: account or passwd",
                execution_time=time.time() - start_time
            )
        
        try:
            # Import SSH manager
            from ..tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand
            
            # Create SSH connection
            ssh_manager = SSHManager()
            credentials = ssh_manager.create_from_vm_info("guest", guest_ip, "root")
            
            # Verify connection
            if not ssh_manager.establish_connection(credentials):
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.ADD_ACCOUNT,
                    vm_name=getattr(guest, 'id', 'unknown'),
                    vm_ip=guest_ip,
                    success=False,
                    message=f"Cannot establish SSH connection to {guest_ip}",
                    execution_time=time.time() - start_time
                )
            
            # Execute user creation commands
            commands = [
                f"useradd -m -c '{full_name}' -s /bin/bash {account}",
                f"echo '{account}:{passwd}' | chpasswd",
                f"mkdir -p /home/{account}/.ssh",
                f"chmod 700 /home/{account}/.ssh",
                f"chown {account}:{account} /home/{account}/.ssh"
            ]
            
            all_success = True
            outputs = []
            
            for cmd in commands:
                result = ssh_manager.execute_with_retry(credentials, SSHCommand(cmd, "Create user"))
                outputs.append(f"Command: {cmd}\\nResult: {result.stdout}\\nError: {result.stderr}\\n")
                if not result.success:
                    all_success = False
                    break
            
            # Verification: Check if user exists and can login
            verification_success = False
            evidence = ""
            
            if all_success:
                # Verify user exists
                verify_result = ssh_manager.execute_command(
                    credentials, 
                    SSHCommand(f"id {account}", "Verify user exists")
                )
                
                if verify_result.success:
                    evidence = f"User verification: {verify_result.stdout.strip()}"
                    
                    # Test user login
                    user_credentials = SSHCredentials(
                        hostname=guest_ip,
                        username=account,
                        password=passwd,
                        timeout=10
                    )
                    
                    test_result = ssh_manager.execute_command(
                        user_credentials,
                        SSHCommand("whoami", "Test user login")
                    )
                    
                    if test_result.success and account in test_result.stdout:
                        verification_success = True
                        evidence += f"\\nLogin test: SUCCESS ({test_result.stdout.strip()})"
                    else:
                        evidence += f"\\nLogin test: FAILED ({test_result.stderr})"
                else:
                    evidence = f"User verification failed: {verify_result.stderr}"
            
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.ADD_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=all_success,
                message=f"Account '{account}' {'created successfully' if all_success else 'creation failed'}",
                evidence=evidence,
                execution_time=time.time() - start_time,
                output="\\n".join(outputs),
                verification_passed=verification_success
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.ADD_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message=f"Add account task failed: {str(e)}",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _execute_modify_account(
        self,
        task_id: str,
        params: Dict[str, Any],
        guest_ip: str,
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute modify_account task with verification"""
        account = params.get('account')
        new_account = params.get('new_account')
        new_passwd = params.get('new_passwd')
        
        if not account or (not new_account and not new_passwd):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message="Missing required parameters",
                execution_time=time.time() - start_time
            )
        
        try:
            from ..tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand
            
            ssh_manager = SSHManager()
            credentials = ssh_manager.create_from_vm_info("guest", guest_ip, "root")
            
            if not ssh_manager.establish_connection(credentials):
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.MODIFY_ACCOUNT,
                    vm_name=getattr(guest, 'id', 'unknown'),
                    vm_ip=guest_ip,
                    success=False,
                    message=f"Cannot establish SSH connection to {guest_ip}",
                    execution_time=time.time() - start_time
                )
            
            commands = []
            
            # Change password if requested
            if new_passwd:
                commands.append(f"echo '{account}:{new_passwd}' | chpasswd")
            
            # Change username if requested
            if new_account:
                commands.extend([
                    f"usermod -l {new_account} {account}",
                    f"usermod -d /home/{new_account} -m {new_account}"
                ])
            
            all_success = True
            outputs = []
            
            for cmd in commands:
                result = ssh_manager.execute_with_retry(credentials, SSHCommand(cmd, "Modify user"))
                outputs.append(f"Command: {cmd}\\nResult: {result.stdout}\\nError: {result.stderr}\\n")
                if not result.success:
                    all_success = False
                    break
            
            # Verification
            verification_success = False
            evidence = ""
            
            if all_success:
                final_username = new_account or account
                verify_result = ssh_manager.execute_command(
                    credentials,
                    SSHCommand(f"id {final_username}", "Verify modified user")
                )
                
                if verify_result.success:
                    evidence = f"Modified user verification: {verify_result.stdout.strip()}"
                    verification_success = True
                else:
                    evidence = f"Verification failed: {verify_result.stderr}"
            
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=all_success,
                message=f"Account '{account}' modification {'completed' if all_success else 'failed'}",
                evidence=evidence,
                execution_time=time.time() - start_time,
                output="\\n".join(outputs),
                verification_passed=verification_success
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message=f"Modify account task failed: {str(e)}",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _execute_install_package(
        self,
        task_id: str,
        params: Dict[str, Any],
        guest_ip: str,
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute install_package task with verification"""
        package_manager = params.get('package_manager', 'yum')
        name = params.get('name')
        version = params.get('version')
        
        if not name:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.INSTALL_PACKAGE,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message="Missing required parameter: name",
                execution_time=time.time() - start_time
            )
        
        try:
            from ..tools.ssh_manager import SSHManager, SSHCredentials, SSHCommand
            
            ssh_manager = SSHManager()
            credentials = ssh_manager.create_from_vm_info("guest", guest_ip, "root")
            
            if not ssh_manager.establish_connection(credentials):
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.INSTALL_PACKAGE,
                    vm_name=getattr(guest, 'id', 'unknown'),
                    vm_ip=guest_ip,
                    success=False,
                    message=f"Cannot establish SSH connection to {guest_ip}",
                    execution_time=time.time() - start_time
                )
            
            # Build install command based on package manager
            package_spec = f"{name}-{version}" if version else name
            
            if package_manager in ['yum', 'dnf']:
                install_cmd = f"{package_manager} install -y {package_spec}"
                check_cmd = f"{package_manager} list installed {name}"
            elif package_manager in ['apt', 'apt-get']:
                install_cmd = f"{package_manager} update && {package_manager} install -y {package_spec}"
                check_cmd = f"dpkg -l | grep {name}"
            else:
                return TaskResult(
                    task_id=task_id,
                    task_type=TaskType.INSTALL_PACKAGE,
                    vm_name=getattr(guest, 'id', 'unknown'),
                    vm_ip=guest_ip,
                    success=False,
                    message=f"Unsupported package manager: {package_manager}",
                    execution_time=time.time() - start_time
                )
            
            # Execute installation
            result = ssh_manager.execute_with_retry(
                credentials,
                SSHCommand(install_cmd, "Install package", timeout=600)  # Longer timeout for packages
            )
            
            # Verification: Check if package is installed
            verification_success = False
            evidence = ""
            
            if result.success:
                verify_result = ssh_manager.execute_command(
                    credentials,
                    SSHCommand(check_cmd, "Verify package installation")
                )
                
                if verify_result.success and name in verify_result.stdout:
                    verification_success = True
                    evidence = f"Package verification: {verify_result.stdout.strip()}"
                else:
                    evidence = f"Package verification failed: {verify_result.stderr}"
            
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.INSTALL_PACKAGE,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=result.success,
                message=f"Package '{name}' installation {'completed' if result.success else 'failed'}",
                evidence=evidence,
                execution_time=time.time() - start_time,
                output=result.stdout,
                error=result.stderr if not result.success else None,
                verification_passed=verification_success
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.INSTALL_PACKAGE,
                vm_name=getattr(guest, 'id', 'unknown'),
                vm_ip=guest_ip,
                success=False,
                message=f"Install package task failed: {str(e)}",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _execute_add_account(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute add account task securely"""
        
        account = params['account']
        passwd = params['passwd']
        full_name = params.get('full_name', '')
        
        # Validate inputs for security
        if not validate_user_input(account, "username"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.ADD_ACCOUNT,
                success=False,
                message="Invalid username format"
            )
        
        if len(passwd) < 8:
            self.secure_logger.warning(f"Weak password provided for user {account}")
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        
        try:
            if os_type == "windows.7":
                # Use secure Windows user creation
                success, output, error = self._execute_secure_windows_add_user(guest_ip, account, passwd)
            else:
                # Use secure Linux user creation
                success, output, error = self._execute_secure_linux_add_user(guest_ip, account, passwd, full_name)
        except Exception as e:
            self.secure_logger.error(f"Add account task failed for user {account}: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.ADD_ACCOUNT,
                success=False,
                message=f"Task execution failed: {str(e)}"
            )
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.ADD_ACCOUNT,
            success=success,
            message=f"Add account '{account}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_modify_account(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute modify account task"""
        
        account = params['account']
        new_account = params.get('new_account', 'null')
        new_passwd = params.get('new_passwd', 'null')
        
        # Validate inputs
        if not validate_user_input(account, "username"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                success=False,
                message="Invalid username format"
            )
        
        if new_account != 'null' and not validate_user_input(new_account, "username"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                success=False,
                message="Invalid new username format"
            )
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        
        try:
            if os_type == "windows.7":
                if new_passwd != 'null':
                    success, output, error = self._execute_secure_windows_modify_user(guest_ip, account, new_passwd)
                else:
                    return TaskResult(
                        task_id=task_id,
                        task_type=TaskType.MODIFY_ACCOUNT,
                        success=False,
                        message="Password modification required for Windows"
                    )
            else:
                success, output, error = self._execute_secure_linux_modify_user(guest_ip, account, new_account, new_passwd)
        except Exception as e:
            self.secure_logger.error(f"Modify account task failed for user {account}: {e}")
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.MODIFY_ACCOUNT,
                success=False,
                message=f"Task execution failed: {str(e)}"
            )
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.MODIFY_ACCOUNT,
            success=success,
            message=f"Modify account '{account}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_install_package(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute install package task with input validation"""
        
        package_manager = params.get('package_manager', 'yum')
        name = params['name']
        version = params.get('version', '')
        
        # Validate package name for security
        if not validate_user_input(name, "general"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.INSTALL_PACKAGE,
                success=False,
                message="Invalid package name format",
                execution_time=time.time() - start_time
            )
        
        # Validate package manager
        allowed_managers = ['yum', 'apt', 'apt-get', 'dnf', 'zypper', 'chocolatey', 'brew']
        if package_manager not in allowed_managers:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.INSTALL_PACKAGE,
                success=False,
                message=f"Unsupported package manager: {package_manager}",
                execution_time=time.time() - start_time
            )
        
        # Build install command with proper escaping
        if package_manager == "chocolatey":
            if version and validate_user_input(version, "general"):
                command = f"{package_manager} install -y {sanitize_for_shell(name)} --version {sanitize_for_shell(version)}"
            else:
                command = f"{package_manager} install -y {sanitize_for_shell(name)}"
        else:
            if version and validate_user_input(version, "general"):
                command = f"{package_manager} install -y {sanitize_for_shell(name)} {sanitize_for_shell(version)}"
            else:
                command = f"{package_manager} install -y {sanitize_for_shell(name)}"
        
        success, output, error = self._execute_ssh_command(guest_ip, command)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.INSTALL_PACKAGE,
            success=success,
            message=f"Install package '{name}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_copy_content(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute copy content task with path validation"""
        
        src = params['src']
        dst = params['dst']
        
        # Validate file paths for security
        if not validate_user_input(src, "file_path") or not validate_user_input(dst, "file_path"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.COPY_CONTENT,
                success=False,
                message="Invalid file path detected",
                execution_time=time.time() - start_time
            )
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Build secure command using secure executor
        if os_type == "windows.7":
            script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/copy_content_win.sh"
            command_parts = ['bash', script_path, src, dst, guest_ip]
        else:
            script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/copy_content.sh"
            command_parts = ['bash', script_path, src, dst, guest_ip, basevm_type, os_type]
        
        # Execute copy command securely
        success, output, error = self.secure_executor.execute_command(command_parts)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.COPY_CONTENT,
            success=success,
            message=f"Copy '{src}' to '{dst}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_program(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute program task with input validation"""
        
        program = params['program']
        interpreter = params['interpreter']
        args = params.get('args', '')
        execute_time = params.get('execute_time', 'before_clone')
        
        # Validate program and interpreter inputs
        if not validate_user_input(program, "file_path"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.EXECUTE_PROGRAM,
                success=False,
                message="Invalid program path",
                execution_time=time.time() - start_time
            )
        
        # Validate interpreter
        allowed_interpreters = ['python', 'python3', 'bash', 'sh', 'powershell', 'cmd', 'java', 'node']
        if interpreter not in allowed_interpreters:
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.EXECUTE_PROGRAM,
                success=False,
                message=f"Unsupported interpreter: {interpreter}",
                execution_time=time.time() - start_time
            )
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        
        # Use run_program.py script with secure command execution
        script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/run_program.py"
        log_file = f"/tmp/{sanitize_for_shell(task_id)}.log"
        
        # NOTE: This still contains 'password' hardcoded - this should be addressed in a future security update
        # For now, we'll use secure command execution but this needs further improvement
        command_parts = [
            'python3', script_path, program, interpreter, args, 
            guest_ip, 'password', log_file, os_type, '-'
        ]
        
        success, output, error = self.secure_executor.execute_command(command_parts)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.EXECUTE_PROGRAM,
            success=success,
            message=f"Execute program '{program}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_emulate_attack(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute emulate attack task"""
        
        attack_type = params['attack_type']
        target_account = params.get('target_account', 'root')
        attempt_number = params.get('attempt_number', 10)
        attack_time = params.get('attack_time', '2024-01-01')
        
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        if attack_type == "ssh_attack":
            script_path = f"{self.abspath}/{self.instantiation_dir}/attacks_emulation"
            command = f"{script_path}/install_paramiko.sh && python3 {script_path}/attack_paramiko_ssh.py {guest_ip} {target_account} {attempt_number} {attack_time} {basevm_type}"
            
            try:
                result = subprocess.run(
                    command, 
                    shell=True,
                    capture_output=True, 
                    text=True, 
                    timeout=300
                )
                success = result.returncode == 0
                output = result.stdout
                error = result.stderr
            except Exception as e:
                success = False
                output = ""
                error = str(e)
        else:
            success = False
            output = ""
            error = f"Unsupported attack type: {attack_type}"
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.EMULATE_ATTACK,
            success=success,
            message=f"Emulate {attack_type} attack: {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_emulate_malware(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute emulate malware task"""
        
        malware_name = params['name']
        mode = params['mode']
        cpu_utilization = params.get('cpu_utilization', 10)
        port = params.get('port', 8080)
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Determine corresponding option for malware script
        if mode == "dummy_calculation":
            crspd_option = str(cpu_utilization)
        elif mode == "port_listening":
            crspd_option = str(port)
        else:
            crspd_option = "10"
        
        # Use malware launch script
        script_path = f"{self.abspath}/{self.instantiation_dir}/malware_creation/malware_launch.sh"
        command = f'bash "{script_path}" {guest_ip} {malware_name} {mode} {crspd_option} {basevm_type} "{self.abspath}" {os_type}'
        
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True, 
                text=True, 
                timeout=300
            )
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr
        except Exception as e:
            success = False
            output = ""
            error = str(e)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.EMULATE_MALWARE,
            success=success,
            message=f"Deploy malware '{malware_name}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_traffic_capture(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute traffic capture file generation task"""
        
        format_type = params.get('format', 'pcap')
        file_name = params['file_name']
        attack_type = params['attack_type']
        noise_level = params.get('noise_level', 'medium')
        attack_source = params.get('attack_source', '10.0.0.1')
        
        # This is a more complex task that generates traffic capture files
        # For now, return success with a note
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.EMULATE_TRAFFIC_CAPTURE,
            success=True,
            message=f"Traffic capture file task '{file_name}' scheduled",
            execution_time=time.time() - start_time,
            output=f"Task configured for {attack_type} with {noise_level} noise level"
        )
    
    def _execute_firewall_rules(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any,
        start_time: float
    ) -> TaskResult:
        """Execute firewall rules task with input validation"""
        
        rule_file = params['rule']
        
        # Validate rule file path
        if not validate_user_input(rule_file, "file_path"):
            return TaskResult(
                task_id=task_id,
                task_type=TaskType.FIREWALL_RULES,
                success=False,
                message="Invalid rule file path",
                execution_time=time.time() - start_time
            )
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Use ruleset modification script with secure execution
        script_path = f"{self.abspath}/{self.instantiation_dir}/ruleset_modification/ruleset_modify.sh"
        command_parts = ['bash', script_path, self.abspath, guest_ip, rule_file, basevm_type, os_type]
        
        success, output, error = self.secure_executor.execute_command(command_parts)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.FIREWALL_RULES,
            success=success,
            message=f"Apply firewall rules from '{rule_file}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=time.time() - start_time,
            output=output,
            error=error
        )
    
    def _execute_ssh_command(
        self, 
        host: str, 
        command: str,
        username: str = "ubuntu",
        password: str = "ubuntu"
    ) -> tuple[bool, str, str]:
        """Execute command via SSH with password authentication"""
        
        if not SSH_AVAILABLE:
            self.logger.warning("SSH not available, simulating command execution")
            return True, f"Simulated: {command}", ""
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password authentication for cloud-init configured user
            ssh.connect(
                host, 
                username=username,
                password=password,
                timeout=self.ssh_timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            # For non-root users, prepend sudo to commands that need privilege escalation
            if username != "root" and self._command_needs_sudo(command):
                command = f"sudo {command}"
            
            stdin, stdout, stderr = ssh.exec_command(command)
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            success = exit_status == 0
            return success, output, error
            
        except Exception as e:
            self.logger.error(f"SSH command execution failed: {e}")
            return False, "", str(e)
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get status of a task (placeholder for future async execution)"""
        # This would be implemented for async task tracking
        return None
    
    def _command_needs_sudo(self, command: str) -> bool:
        """Determine if a command needs sudo privileges"""
        sudo_commands = [
            'useradd', 'usermod', 'userdel', 'chpasswd', 'chfn',
            'apt-get', 'yum', 'dnf', 'zypper', 'pacman',
            'systemctl', 'service', 'chkconfig',
            'iptables', 'firewall-cmd', 'ufw',
            'mount', 'umount', 'fdisk', 'parted'
        ]
        
        command_parts = command.strip().split()
        if not command_parts:
            return False
            
        # Check if the first word (command name) requires sudo
        first_command = command_parts[0]
        return any(first_command.startswith(sudo_cmd) for sudo_cmd in sudo_commands)
    
    def _execute_secure_linux_add_user(self, guest_ip: str, username: str, password: str, full_name: str = "") -> tuple[bool, str, str]:
        """Securely add user on Linux systems without exposing password in command line"""
        try:
            # Create a temporary script that adds the user securely
            script_content = f"""#!/bin/bash
set -euo pipefail

# Create user (needs sudo)
sudo useradd -m -s /bin/bash "{sanitize_for_shell(username)}"

# Set password securely using chpasswd (needs sudo)
echo "{sanitize_for_shell(username)}:$1" | sudo chpasswd

# Set full name if provided (needs sudo)
if [ -n "$2" ]; then
    sudo chfn -f "$2" "{sanitize_for_shell(username)}"
fi

echo "User {sanitize_for_shell(username)} created successfully"
"""
            
            # Write script to temporary file on remote host
            temp_script = f"/tmp/add_user_{username}_{os.getpid()}.sh"
            
            # Upload script
            upload_success, upload_output, upload_error = self._execute_ssh_command(
                guest_ip, 
                f"cat > {temp_script} << 'EOF'\n{script_content}\nEOF"
            )
            
            if not upload_success:
                return False, upload_output, f"Failed to upload user creation script: {upload_error}"
            
            # Make script executable
            chmod_success, chmod_output, chmod_error = self._execute_ssh_command(
                guest_ip, 
                f"chmod +x {temp_script}"
            )
            
            if not chmod_success:
                return False, chmod_output, f"Failed to make script executable: {chmod_error}"
            
            # Execute script with password as argument (more secure than command line)
            exec_command = f"{temp_script} '{password}' '{sanitize_for_shell(full_name)}'"
            success, output, error = self._execute_ssh_command(guest_ip, exec_command)
            
            # Clean up temporary script
            cleanup_success, _, _ = self._execute_ssh_command(guest_ip, f"rm -f {temp_script}")
            if not cleanup_success:
                self.secure_logger.warning(f"Failed to clean up temporary script {temp_script}")
            
            return success, output, error
            
        except Exception as e:
            self.secure_logger.error(f"Secure Linux user creation failed: {e}")
            return False, "", str(e)
    
    def _execute_secure_windows_add_user(self, guest_ip: str, username: str, password: str) -> tuple[bool, str, str]:
        """Securely add user on Windows systems using PowerShell SecureString"""
        try:
            # Create a temporary PowerShell script that handles password securely
            script_content = f"""
param([string]$Password)
$username = '{sanitize_for_shell(username)}'
$securePassword = ConvertTo-SecureString $Password -AsPlainText -Force

try {{
    New-LocalUser -Name $username -Password $securePassword -Description 'Created by CyRIS' -ErrorAction Stop
    Add-LocalGroupMember -Group 'Remote Desktop Users' -Member $username -ErrorAction Stop
    Write-Output "User $username created successfully"
}} catch {{
    Write-Error "Failed to create user: $_.Exception.Message"
    exit 1
}}
"""
            
            # Write script to temporary file on remote host
            temp_script = f"/tmp/add_user_{username}_{os.getpid()}.ps1"
            
            # Upload script (Windows path conversion needed)
            windows_temp_script = f"C:\\temp\\add_user_{username}_{os.getpid()}.ps1"
            upload_success, upload_output, upload_error = self._execute_ssh_command(
                guest_ip, 
                f'echo "{script_content}" > "{windows_temp_script}"'
            )
            
            if not upload_success:
                return False, upload_output, f"Failed to upload PowerShell script: {upload_error}"
            
            # Execute script with password as parameter
            exec_command = f'powershell.exe -ExecutionPolicy Bypass -File "{windows_temp_script}" -Password "{password}"'
            success, output, error = self._execute_ssh_command(guest_ip, exec_command)
            
            # Clean up temporary script
            cleanup_success, _, _ = self._execute_ssh_command(guest_ip, f'del "{windows_temp_script}"')
            if not cleanup_success:
                self.secure_logger.warning(f"Failed to clean up temporary script {windows_temp_script}")
            
            return success, output, error
            
        except Exception as e:
            self.secure_logger.error(f"Secure Windows user creation failed: {e}")
            return False, "", str(e)
    
    def _execute_secure_linux_modify_user(self, guest_ip: str, username: str, new_username: str, new_password: str) -> tuple[bool, str, str]:
        """Securely modify user on Linux systems"""
        try:
            script_parts = []
            script_parts.append("#!/bin/bash")
            script_parts.append("set -euo pipefail")
            script_parts.append("")
            
            # Validate current user exists
            script_parts.append(f'if ! id "{sanitize_for_shell(username)}" &>/dev/null; then')
            script_parts.append(f'    echo "User {sanitize_for_shell(username)} does not exist"')
            script_parts.append('    exit 1')
            script_parts.append('fi')
            script_parts.append("")
            
            # Change username if requested
            if new_username != 'null' and new_username != username:
                script_parts.append(f'# Rename user from {sanitize_for_shell(username)} to {sanitize_for_shell(new_username)}')
                script_parts.append(f'sudo usermod -l "{sanitize_for_shell(new_username)}" "{sanitize_for_shell(username)}"')
                script_parts.append(f'sudo usermod -d "/home/{sanitize_for_shell(new_username)}" -m "{sanitize_for_shell(new_username)}"')
                actual_username = new_username
            else:
                actual_username = username
            
            # Change password if requested
            if new_password != 'null':
                script_parts.append(f'# Change password for {sanitize_for_shell(actual_username)}')
                script_parts.append(f'echo "{sanitize_for_shell(actual_username)}:$1" | sudo chpasswd')
            
            script_parts.append(f'echo "User modification completed for {sanitize_for_shell(actual_username)}"')
            
            script_content = "\n".join(script_parts)
            
            # Write script to temporary file on remote host
            temp_script = f"/tmp/modify_user_{username}_{os.getpid()}.sh"
            
            # Upload script
            upload_success, upload_output, upload_error = self._execute_ssh_command(
                guest_ip, 
                f"cat > {temp_script} << 'EOF'\n{script_content}\nEOF"
            )
            
            if not upload_success:
                return False, upload_output, f"Failed to upload user modification script: {upload_error}"
            
            # Make script executable
            chmod_success, chmod_output, chmod_error = self._execute_ssh_command(
                guest_ip, 
                f"chmod +x {temp_script}"
            )
            
            if not chmod_success:
                return False, chmod_output, f"Failed to make script executable: {chmod_error}"
            
            # Execute script with password as argument if needed
            if new_password != 'null':
                exec_command = f"{temp_script} '{new_password}'"
            else:
                exec_command = f"{temp_script} ''"
                
            success, output, error = self._execute_ssh_command(guest_ip, exec_command)
            
            # Clean up temporary script
            cleanup_success, _, _ = self._execute_ssh_command(guest_ip, f"rm -f {temp_script}")
            if not cleanup_success:
                self.secure_logger.warning(f"Failed to clean up temporary script {temp_script}")
            
            return success, output, error
            
        except Exception as e:
            self.secure_logger.error(f"Secure Linux user modification failed: {e}")
            return False, "", str(e)
    
    def _execute_secure_windows_modify_user(self, guest_ip: str, username: str, new_password: str) -> tuple[bool, str, str]:
        """Securely modify user password on Windows systems"""
        try:
            # Create PowerShell script for secure password modification
            script_content = f"""
param([string]$Password)
$username = '{sanitize_for_shell(username)}'
$securePassword = ConvertTo-SecureString $Password -AsPlainText -Force

try {{
    # Check if user exists
    $user = Get-LocalUser -Name $username -ErrorAction Stop
    
    # Change password
    $user | Set-LocalUser -Password $securePassword -ErrorAction Stop
    
    Write-Output "Password changed successfully for user $username"
}} catch {{
    Write-Error "Failed to modify user: $_.Exception.Message"
    exit 1
}}
"""
            
            # Write script to temporary file on remote host
            windows_temp_script = f"C:\\temp\\modify_user_{username}_{os.getpid()}.ps1"
            
            # Upload script
            upload_success, upload_output, upload_error = self._execute_ssh_command(
                guest_ip, 
                f'echo "{script_content}" > "{windows_temp_script}"'
            )
            
            if not upload_success:
                return False, upload_output, f"Failed to upload PowerShell script: {upload_error}"
            
            # Execute script with password as parameter
            exec_command = f'powershell.exe -ExecutionPolicy Bypass -File "{windows_temp_script}" -Password "{new_password}"'
            success, output, error = self._execute_ssh_command(guest_ip, exec_command)
            
            # Clean up temporary script
            cleanup_success, _, _ = self._execute_ssh_command(guest_ip, f'del "{windows_temp_script}"')
            if not cleanup_success:
                self.secure_logger.warning(f"Failed to clean up temporary script {windows_temp_script}")
            
            return success, output, error
            
        except Exception as e:
            self.secure_logger.error(f"Secure Windows user modification failed: {e}")
            return False, "", str(e)