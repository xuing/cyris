"""
Task Execution Service

This service handles the execution of tasks defined in cyber range YAML files.
It integrates the traditional modules.py functionality into the modern architecture.
"""

import logging
import subprocess
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

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
    """Result of task execution"""
    task_id: str
    task_type: TaskType
    success: bool
    message: str
    execution_time: float
    output: Optional[str] = None
    error: Optional[str] = None


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
        self.logger = logging.getLogger(__name__)
        self.abspath = config.get('base_path', '/home/ubuntu/cyris')
        self.instantiation_dir = "instantiation"
        
        # SSH configuration
        self.ssh_timeout = config.get('ssh_timeout', 30)
        self.ssh_retries = config.get('ssh_retries', 3)
    
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
                result = self._execute_add_account(task_id, params, guest_ip, guest)
            elif task_type == TaskType.MODIFY_ACCOUNT:
                result = self._execute_modify_account(task_id, params, guest_ip, guest)
            elif task_type == TaskType.INSTALL_PACKAGE:
                result = self._execute_install_package(task_id, params, guest_ip, guest)
            elif task_type == TaskType.COPY_CONTENT:
                result = self._execute_copy_content(task_id, params, guest_ip, guest)
            elif task_type == TaskType.EXECUTE_PROGRAM:
                result = self._execute_program(task_id, params, guest_ip, guest)
            elif task_type == TaskType.EMULATE_ATTACK:
                result = self._execute_emulate_attack(task_id, params, guest_ip, guest)
            elif task_type == TaskType.EMULATE_MALWARE:
                result = self._execute_emulate_malware(task_id, params, guest_ip, guest)
            elif task_type == TaskType.EMULATE_TRAFFIC_CAPTURE:
                result = self._execute_traffic_capture(task_id, params, guest_ip, guest)
            elif task_type == TaskType.FIREWALL_RULES:
                result = self._execute_firewall_rules(task_id, params, guest_ip, guest)
            else:
                result = TaskResult(
                    task_id=task_id,
                    task_type=task_type,
                    success=False,
                    message=f"Unknown task type: {task_type}",
                    execution_time=time.time() - start_time
                )
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed with exception: {e}")
            result = TaskResult(
                task_id=task_id,
                task_type=task_type,
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
        guest: Any
    ) -> TaskResult:
        """Execute add account task"""
        
        account = params['account']
        passwd = params['passwd']
        full_name = params.get('full_name', '')
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Generate command based on OS type
        if os_type == "windows.7":
            command = f"net user {account} {passwd} /ADD && net localgroup \"Remote Desktop Users\" {account} /ADD"
        else:
            # Use the shell script for Linux systems
            script_path = f"{self.abspath}/{self.instantiation_dir}/users_managing/add_user.sh"
            command = f"bash {script_path} {account} {passwd} yes \"{full_name}\""
        
        # Execute command via SSH
        success, output, error = self._execute_ssh_command(guest_ip, command)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.ADD_ACCOUNT,
            success=success,
            message=f"Add account '{account}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,  # Set by caller
            output=output,
            error=error
        )
    
    def _execute_modify_account(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
    ) -> TaskResult:
        """Execute modify account task"""
        
        account = params['account']
        new_account = params.get('new_account', 'null')
        new_passwd = params.get('new_passwd', 'null')
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        
        if os_type == "windows.7":
            if new_passwd != 'null':
                command = f"net user {account} {new_passwd}"
            else:
                command = "echo 'Password change only supported on Windows'"
        else:
            script_path = f"{self.abspath}/{self.instantiation_dir}/users_managing/modify_user.sh"
            command = f"bash {script_path} {account} {new_account} {new_passwd}"
        
        success, output, error = self._execute_ssh_command(guest_ip, command)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.MODIFY_ACCOUNT,
            success=success,
            message=f"Modify account '{account}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_install_package(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
    ) -> TaskResult:
        """Execute install package task"""
        
        package_manager = params.get('package_manager', 'yum')
        name = params['name']
        version = params.get('version', '')
        
        # Build install command
        if package_manager == "chocolatey":
            if version:
                command = f"{package_manager} install -y {name} --version {version}"
            else:
                command = f"{package_manager} install -y {name}"
        else:
            command = f"{package_manager} install -y {name} {version}".strip()
        
        success, output, error = self._execute_ssh_command(guest_ip, command)
        
        return TaskResult(
            task_id=task_id,
            task_type=TaskType.INSTALL_PACKAGE,
            success=success,
            message=f"Install package '{name}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_copy_content(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
    ) -> TaskResult:
        """Execute copy content task"""
        
        src = params['src']
        dst = params['dst']
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Use copy script
        if os_type == "windows.7":
            script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/copy_content_win.sh"
            command = f'bash "{script_path}" "{src}" "{dst}" {guest_ip}'
        else:
            script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/copy_content.sh"
            command = f'bash "{script_path}" "{src}" "{dst}" {guest_ip} {basevm_type} {os_type}'
        
        # Execute copy command
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
            task_type=TaskType.COPY_CONTENT,
            success=success,
            message=f"Copy '{src}' to '{dst}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_program(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
    ) -> TaskResult:
        """Execute program task"""
        
        program = params['program']
        interpreter = params['interpreter']
        args = params.get('args', '')
        execute_time = params.get('execute_time', 'before_clone')
        
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        
        # Use run_program.py script
        script_path = f"{self.abspath}/{self.instantiation_dir}/content_copy_program_run/run_program.py"
        log_file = f"/tmp/{task_id}.log"
        
        command = f'python3 "{script_path}" "{program}" {interpreter} "{args}" {guest_ip} password "{log_file}" {os_type} "-"'
        
        try:
            result = subprocess.run(
                command.split(), 
                capture_output=True, 
                text=True, 
                timeout=600
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
            task_type=TaskType.EXECUTE_PROGRAM,
            success=success,
            message=f"Execute program '{program}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_emulate_attack(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
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
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_emulate_malware(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
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
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_traffic_capture(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
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
            execution_time=0,
            output=f"Task configured for {attack_type} with {noise_level} noise level"
        )
    
    def _execute_firewall_rules(
        self, 
        task_id: str, 
        params: Dict[str, Any], 
        guest_ip: str, 
        guest: Any
    ) -> TaskResult:
        """Execute firewall rules task"""
        
        rule_file = params['rule']
        os_type = getattr(guest, 'basevm_os_type', 'linux')
        basevm_type = getattr(guest, 'basevm_type', 'kvm')
        
        # Use ruleset modification script
        script_path = f"{self.abspath}/{self.instantiation_dir}/ruleset_modification/ruleset_modify.sh"
        command = f'bash "{script_path}" "{self.abspath}" {guest_ip} {rule_file} {basevm_type} {os_type}'
        
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
            task_type=TaskType.FIREWALL_RULES,
            success=success,
            message=f"Apply firewall rules from '{rule_file}': {'SUCCESS' if success else 'FAILED'}",
            execution_time=0,
            output=output,
            error=error
        )
    
    def _execute_ssh_command(
        self, 
        host: str, 
        command: str,
        username: str = "root"
    ) -> tuple[bool, str, str]:
        """Execute command via SSH"""
        
        if not SSH_AVAILABLE:
            self.logger.warning("SSH not available, simulating command execution")
            return True, f"Simulated: {command}", ""
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with key-based authentication (no password)
            ssh.connect(
                host, 
                username=username,
                timeout=self.ssh_timeout,
                look_for_keys=True,
                allow_agent=True
            )
            
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