"""
SSH Manager

This module provides SSH key management and remote command execution
capabilities for cyber range operations.
"""

import logging
import paramiko
import socket
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass
class SSHCredentials:
    """SSH connection credentials"""
    hostname: str
    port: int = 22
    username: str = "root"
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_data: Optional[str] = None
    timeout: int = 30


@dataclass
class SSHCommand:
    """SSH command execution details"""
    command: str
    description: str
    timeout: int = 300
    ignore_errors: bool = False
    expected_return_codes: List[int] = field(default_factory=lambda: [0])


@dataclass
class SSHResult:
    """SSH command execution result"""
    hostname: str
    command: str
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    success: bool
    error_message: Optional[str] = None


class SSHManager:
    """
    SSH connection and command execution manager.
    
    This service manages SSH connections to cyber range VMs and hosts,
    providing secure remote command execution, file transfers, and
    key-based authentication setup.
    
    Capabilities:
    - SSH key generation and management
    - Remote command execution (single and batch)
    - File transfer (SCP/SFTP)
    - Connection pooling and reuse
    - Parallel execution across multiple hosts
    - Connection health monitoring
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on SSH operations
    - Open/Closed: Extensible authentication methods
    - Interface Segregation: Focused SSH interface
    - Dependency Inversion: Uses abstract connection interfaces
    """
    
    def __init__(
        self,
        max_connections: int = 50,
        connection_timeout: int = 30,
        command_timeout: int = 300,
        key_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize SSH manager.
        
        Args:
            max_connections: Maximum concurrent connections
            connection_timeout: Connection timeout in seconds
            command_timeout: Default command timeout in seconds
            key_dir: Directory to store SSH keys
            logger: Optional logger instance
        """
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self.key_dir = Path(key_dir) if key_dir else Path.home() / ".cyris" / "ssh_keys"
        self.logger = logger or logging.getLogger(__name__)
        
        # Ensure key directory exists
        self.key_dir.mkdir(parents=True, exist_ok=True)
        
        # Connection pool
        self._connections: Dict[str, paramiko.SSHClient] = {}
        self._connection_locks: Dict[str, threading.Lock] = {}
        self._connection_stats: Dict[str, Dict[str, Any]] = {}
        
        # Thread pool for parallel execution
        self._executor = ThreadPoolExecutor(max_workers=max_connections)
        
        self.logger.info("SSHManager initialized")
        
        # Initialize parallel-ssh support (legacy compatibility)
        self.temp_host_files: Dict[str, Path] = {}  # Track temporary host files
    
    def generate_ssh_keypair(
        self, 
        name: str,
        key_size: int = 2048,
        overwrite: bool = False
    ) -> Tuple[str, str]:
        """
        Generate SSH key pair.
        
        Args:
            name: Key pair name
            key_size: RSA key size in bits
            overwrite: Whether to overwrite existing keys
        
        Returns:
            Tuple of (private_key_path, public_key_path)
        
        Raises:
            ValueError: If keys exist and overwrite=False
            OSError: If key generation fails
        """
        private_key_path = self.key_dir / f"{name}"
        public_key_path = self.key_dir / f"{name}.pub"
        
        if not overwrite and (private_key_path.exists() or public_key_path.exists()):
            raise ValueError(f"SSH key pair '{name}' already exists. Use overwrite=True to replace.")
        
        self.logger.info(f"Generating SSH key pair: {name}")
        
        try:
            # Generate RSA private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize public key in OpenSSH format
            public_ssh = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            
            # Write private key
            with open(private_key_path, 'wb') as f:
                f.write(private_pem)
            private_key_path.chmod(0o600)  # Secure permissions
            
            # Write public key
            with open(public_key_path, 'wb') as f:
                f.write(public_ssh)
            public_key_path.chmod(0o644)
            
            self.logger.info(f"SSH key pair generated: {private_key_path}")
            return str(private_key_path), str(public_key_path)
            
        except Exception as e:
            self.logger.error(f"Failed to generate SSH key pair '{name}': {e}")
            raise OSError(f"SSH key generation failed: {e}") from e
    
    def install_public_key(
        self,
        credentials: SSHCredentials,
        public_key_path: str,
        target_user: str = None
    ) -> bool:
        """
        Install public key on remote host.
        
        Args:
            credentials: SSH connection credentials
            public_key_path: Path to public key file
            target_user: Target user (defaults to credentials.username)
        
        Returns:
            True if successful, False otherwise
        """
        target_user = target_user or credentials.username
        
        try:
            # Read public key
            with open(public_key_path, 'r') as f:
                public_key_content = f.read().strip()
            
            # Commands to install public key
            commands = [
                f"mkdir -p /home/{target_user}/.ssh",
                f"chmod 700 /home/{target_user}/.ssh",
                f"echo '{public_key_content}' >> /home/{target_user}/.ssh/authorized_keys",
                f"chmod 600 /home/{target_user}/.ssh/authorized_keys",
                f"chown -R {target_user}:{target_user} /home/{target_user}/.ssh"
            ]
            
            # Execute commands
            for command in commands:
                result = self.execute_command(credentials, SSHCommand(command, f"Install public key step"))
                if not result.success:
                    self.logger.error(f"Failed to install public key: {result.stderr}")
                    return False
            
            self.logger.info(f"Public key installed for user {target_user} on {credentials.hostname}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install public key on {credentials.hostname}: {e}")
            return False
    
    def execute_command(
        self,
        credentials: SSHCredentials,
        command: Union[str, SSHCommand]
    ) -> SSHResult:
        """
        Execute command on remote host.
        
        Args:
            credentials: SSH connection credentials
            command: Command to execute (string or SSHCommand object)
        
        Returns:
            SSH execution result
        """
        if isinstance(command, str):
            command = SSHCommand(command, "Execute command")
        
        start_time = time.time()
        
        try:
            # Get connection
            client = self._get_connection(credentials)
            
            # Execute command
            self.logger.debug(f"Executing on {credentials.hostname}: {command.command}")
            
            stdin, stdout, stderr = client.exec_command(
                command.command,
                timeout=command.timeout
            )
            
            # Wait for completion
            exit_status = stdout.channel.recv_exit_status()
            
            # Read output
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            
            execution_time = time.time() - start_time
            
            # Determine success
            success = exit_status in command.expected_return_codes or command.ignore_errors
            
            result = SSHResult(
                hostname=credentials.hostname,
                command=command.command,
                return_code=exit_status,
                stdout=stdout_data,
                stderr=stderr_data,
                execution_time=execution_time,
                success=success,
                error_message=stderr_data if not success else None
            )
            
            if success:
                self.logger.debug(f"Command succeeded on {credentials.hostname}: {command.command}")
            else:
                self.logger.warning(f"Command failed on {credentials.hostname}: {command.command} (exit: {exit_status})")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"SSH command execution failed on {credentials.hostname}: {e}")
            
            return SSHResult(
                hostname=credentials.hostname,
                command=command.command,
                return_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )
    
    def execute_commands_parallel(
        self,
        host_commands: Dict[SSHCredentials, List[Union[str, SSHCommand]]],
        max_workers: Optional[int] = None
    ) -> Dict[str, List[SSHResult]]:
        """
        Execute commands on multiple hosts in parallel.
        
        Args:
            host_commands: Dictionary mapping credentials to command lists
            max_workers: Maximum number of parallel workers
        
        Returns:
            Dictionary mapping hostname to list of results
        """
        max_workers = max_workers or min(len(host_commands), self.max_connections)
        results = {}
        
        # Flatten commands for parallel execution
        tasks = []
        for credentials, commands in host_commands.items():
            for command in commands:
                tasks.append((credentials, command))
        
        self.logger.info(f"Executing {len(tasks)} commands across {len(host_commands)} hosts")
        
        # Execute in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.execute_command, cred, cmd): (cred.hostname, cred, cmd)
                for cred, cmd in tasks
            }
            
            # Collect results
            for future in as_completed(future_to_task):
                hostname, credentials, command = future_to_task[future]
                
                try:
                    result = future.result()
                    if hostname not in results:
                        results[hostname] = []
                    results[hostname].append(result)
                    
                except Exception as e:
                    self.logger.error(f"Task execution failed for {hostname}: {e}")
                    
                    # Create error result
                    error_result = SSHResult(
                        hostname=hostname,
                        command=command.command if isinstance(command, SSHCommand) else command,
                        return_code=-1,
                        stdout="",
                        stderr=str(e),
                        execution_time=0.0,
                        success=False,
                        error_message=str(e)
                    )
                    
                    if hostname not in results:
                        results[hostname] = []
                    results[hostname].append(error_result)
        
        return results
    
    def upload_file(
        self,
        credentials: SSHCredentials,
        local_path: str,
        remote_path: str,
        create_dirs: bool = True
    ) -> bool:
        """
        Upload file to remote host using SFTP.
        
        Args:
            credentials: SSH connection credentials
            local_path: Local file path
            remote_path: Remote file path
            create_dirs: Create remote directories if needed
        
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_connection(credentials)
            sftp = client.open_sftp()
            
            # Create remote directories if requested
            if create_dirs:
                remote_dir = str(Path(remote_path).parent)
                try:
                    sftp.makedirs(remote_dir)
                except:
                    pass  # Directory might already exist
            
            # Upload file
            sftp.put(local_path, remote_path)
            sftp.close()
            
            self.logger.info(f"Uploaded {local_path} to {credentials.hostname}:{remote_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File upload failed to {credentials.hostname}: {e}")
            return False
    
    def download_file(
        self,
        credentials: SSHCredentials,
        remote_path: str,
        local_path: str
    ) -> bool:
        """
        Download file from remote host using SFTP.
        
        Args:
            credentials: SSH connection credentials
            remote_path: Remote file path
            local_path: Local file path
        
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_connection(credentials)
            sftp = client.open_sftp()
            
            # Download file
            sftp.get(remote_path, local_path)
            sftp.close()
            
            self.logger.info(f"Downloaded {credentials.hostname}:{remote_path} to {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"File download failed from {credentials.hostname}: {e}")
            return False
    
    def test_connection(self, credentials: SSHCredentials) -> bool:
        """
        Test SSH connection to host.
        
        Args:
            credentials: SSH connection credentials
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            client = self._get_connection(credentials)
            
            # Test with a simple command
            result = self.execute_command(credentials, SSHCommand("echo 'test'", "Connection test", timeout=10))
            return result.success and result.stdout.strip() == "test"
            
        except Exception as e:
            self.logger.debug(f"Connection test failed for {credentials.hostname}: {e}")
            return False
    
    def get_connection_stats(self, hostname: str) -> Optional[Dict[str, Any]]:
        """Get connection statistics for a host"""
        return self._connection_stats.get(hostname)
    
    def close_connection(self, hostname: str) -> None:
        """Close SSH connection to specific host"""
        connection_key = hostname
        
        if connection_key in self._connections:
            try:
                self._connections[connection_key].close()
                del self._connections[connection_key]
                del self._connection_locks[connection_key]
                self.logger.debug(f"Closed SSH connection to {hostname}")
            except Exception as e:
                self.logger.warning(f"Error closing connection to {hostname}: {e}")
    
    def close_all_connections(self) -> None:
        """Close all SSH connections"""
        for hostname in list(self._connections.keys()):
            self.close_connection(hostname)
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        self.logger.info("Closed all SSH connections")
    
    def get_ssh_manager_stats(self) -> Dict[str, Any]:
        """Get SSH manager statistics"""
        return {
            "active_connections": len(self._connections),
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "command_timeout": self.command_timeout,
            "key_directory": str(self.key_dir),
            "available_keys": len(list(self.key_dir.glob("*.pub"))),
            "connection_hosts": list(self._connections.keys())
        }
    
    def _get_connection(self, credentials: SSHCredentials) -> paramiko.SSHClient:
        """Get or create SSH connection"""
        connection_key = f"{credentials.hostname}:{credentials.port}:{credentials.username}"
        
        # Get or create lock for this connection
        if connection_key not in self._connection_locks:
            self._connection_locks[connection_key] = threading.Lock()
        
        with self._connection_locks[connection_key]:
            # Check if connection exists and is alive
            if connection_key in self._connections:
                client = self._connections[connection_key]
                try:
                    # Test if connection is alive
                    client.exec_command("echo test", timeout=5)
                    return client
                except:
                    # Connection is dead, remove it
                    try:
                        client.close()
                    except:
                        pass
                    del self._connections[connection_key]
            
            # Create new connection
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                # Prepare connection arguments
                connect_kwargs = {
                    "hostname": credentials.hostname,
                    "port": credentials.port,
                    "username": credentials.username,
                    "timeout": credentials.timeout
                }
                
                # Add authentication method
                if credentials.private_key_path:
                    connect_kwargs["key_filename"] = credentials.private_key_path
                elif credentials.private_key_data:
                    from io import StringIO
                    key_file = StringIO(credentials.private_key_data)
                    connect_kwargs["pkey"] = paramiko.RSAKey.from_private_key(key_file)
                elif credentials.password:
                    connect_kwargs["password"] = credentials.password
                else:
                    raise ValueError("No authentication method provided")
                
                # Connect
                client.connect(**connect_kwargs)
                
                # Store connection
                self._connections[connection_key] = client
                
                # Initialize stats
                self._connection_stats[credentials.hostname] = {
                    "created_at": time.time(),
                    "commands_executed": 0,
                    "last_used": time.time()
                }
                
                self.logger.debug(f"Created SSH connection to {credentials.hostname}")
                return client
                
            except Exception as e:
                self.logger.error(f"Failed to create SSH connection to {credentials.hostname}: {e}")
                try:
                    client.close()
                except:
                    pass
                raise
    
    def _update_connection_stats(self, hostname: str) -> None:
        """Update connection statistics"""
        if hostname in self._connection_stats:
            stats = self._connection_stats[hostname]
            stats["commands_executed"] += 1
            stats["last_used"] = time.time()
    
    def execute_with_retry(
        self,
        credentials: SSHCredentials,
        command: Union[str, SSHCommand],
        max_retries: int = 3,
        retry_delay: float = 2.0,
        backoff_factor: float = 2.0
    ) -> SSHResult:
        """
        Execute command with retry logic and exponential backoff.
        
        Args:
            credentials: SSH connection credentials
            command: Command to execute
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            backoff_factor: Multiplicative factor for delay increase
        
        Returns:
            SSH execution result
        """
        if isinstance(command, str):
            command = SSHCommand(command, "Execute with retry")
            
        last_result = None
        current_delay = retry_delay
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"SSH attempt {attempt + 1}/{max_retries + 1} to {credentials.hostname}")
                result = self.execute_command(credentials, command)
                
                if result.success:
                    if attempt > 0:
                        self.logger.info(f"SSH command succeeded on attempt {attempt + 1} to {credentials.hostname}")
                    return result
                    
                last_result = result
                
                # Check if this is a retryable error
                if not self._is_retryable_error(result):
                    self.logger.info(f"Non-retryable error on {credentials.hostname}, stopping retries")
                    break
                    
            except Exception as e:
                self.logger.warning(f"SSH attempt {attempt + 1} failed to {credentials.hostname}: {e}")
                last_result = SSHResult(
                    hostname=credentials.hostname,
                    command=command.command,
                    return_code=-1,
                    stdout="",
                    stderr=str(e),
                    execution_time=0.0,
                    success=False,
                    error_message=str(e)
                )
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                import random
                self.logger.debug(f"Waiting {current_delay:.1f}s before retry to {credentials.hostname}")
                time.sleep(current_delay + random.uniform(0, 0.5))  # Add jitter
                current_delay *= backoff_factor
        
        self.logger.error(f"SSH command failed after {max_retries + 1} attempts to {credentials.hostname}")
        return last_result
    
    def verify_connectivity(self, credentials: SSHCredentials, timeout: int = 10) -> Dict[str, Any]:
        """
        Comprehensive connectivity verification.
        
        Args:
            credentials: SSH connection credentials
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with connectivity details
        """
        from datetime import datetime
        
        result = {
            "hostname": credentials.hostname,
            "port": credentials.port,
            "reachable": False,
            "ssh_available": False,
            "auth_working": False,
            "latency_ms": None,
            "error_message": None,
            "diagnostics": {},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Step 1: Network connectivity test
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                connection_result = sock.connect_ex((credentials.hostname, credentials.port))
                if connection_result == 0:
                    result["reachable"] = True
                    result["latency_ms"] = round((time.time() - start_time) * 1000, 2)
                else:
                    result["error_message"] = f"Port {credentials.port} not reachable"
                    return result
            finally:
                sock.close()
            
            # Step 2: SSH service test
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Try connection without authentication first
                try:
                    client.connect(
                        hostname=credentials.hostname,
                        port=credentials.port,
                        username="invalid_user",
                        password="invalid_password",
                        timeout=timeout,
                        look_for_keys=False,
                        allow_agent=False
                    )
                except paramiko.AuthenticationException:
                    # SSH service is available (authentication expected to fail)
                    result["ssh_available"] = True
                except Exception as e:
                    result["error_message"] = f"SSH service not available: {e}"
                    return result
                finally:
                    try:
                        client.close()
                    except:
                        pass
                
                # Step 3: Authentication test
                test_result = self.execute_command(
                    credentials, 
                    SSHCommand("echo 'connectivity_test'", "Connectivity test", timeout=timeout)
                )
                
                if test_result.success and "connectivity_test" in test_result.stdout:
                    result["auth_working"] = True
                else:
                    result["error_message"] = f"Authentication failed: {test_result.stderr}"
                    result["diagnostics"]["auth_error"] = test_result.stderr
                
            except Exception as e:
                result["error_message"] = f"SSH connection failed: {e}"
                result["diagnostics"]["ssh_error"] = str(e)
            
        except Exception as e:
            result["error_message"] = f"Network connectivity failed: {e}"
            result["diagnostics"]["network_error"] = str(e)
        
        return result
    
    def establish_connection(self, credentials: SSHCredentials, max_retries: int = 3) -> bool:
        """
        Establish and verify SSH connection with retry logic.
        
        Args:
            credentials: SSH connection credentials
            max_retries: Maximum connection attempts
            
        Returns:
            True if connection established successfully
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Establishing SSH connection to {credentials.hostname} (attempt {attempt + 1}/{max_retries})")
                
                # Test connectivity first
                connectivity = self.verify_connectivity(credentials)
                
                if not connectivity["reachable"]:
                    self.logger.warning(f"Host {credentials.hostname} not reachable: {connectivity['error_message']}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return False
                
                if not connectivity["ssh_available"]:
                    self.logger.warning(f"SSH service not available on {credentials.hostname}: {connectivity['error_message']}")
                    return False
                
                if not connectivity["auth_working"]:
                    self.logger.warning(f"SSH authentication failed to {credentials.hostname}: {connectivity['error_message']}")
                    return False
                
                self.logger.info(f"SSH connection established to {credentials.hostname} (latency: {connectivity['latency_ms']}ms)")
                return True
                
            except Exception as e:
                self.logger.warning(f"Connection attempt {attempt + 1} failed to {credentials.hostname}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        self.logger.error(f"Failed to establish SSH connection to {credentials.hostname} after {max_retries} attempts")
        return False
    
    def create_from_vm_info(self, vm_name: str, vm_ip: str, username: str = "ubuntu", 
                           ssh_key_path: Optional[str] = None) -> SSHCredentials:
        """
        Create SSH credentials from VM information.
        
        Args:
            vm_name: VM identifier
            vm_ip: VM IP address
            username: SSH username
            ssh_key_path: Path to SSH private key
            
        Returns:
            SSH credentials object
        """
        # Use default key if not specified
        if not ssh_key_path:
            default_keys = [
                self.key_dir / "cyris",
                Path.home() / ".ssh/id_rsa",
                Path.home() / ".ssh/id_ed25519"
            ]
            
            for key_path in default_keys:
                if key_path.exists():
                    ssh_key_path = str(key_path)
                    break
        
        return SSHCredentials(
            hostname=vm_ip,
            port=22,
            username=username,
            private_key_path=ssh_key_path,
            timeout=30
        )
    
    def get_or_create_default_keypair(self, name: str = "cyris") -> Tuple[str, str]:
        """
        Get existing default keypair or create new one.
        
        Args:
            name: Key pair name
            
        Returns:
            Tuple of (private_key_path, public_key_path)
        """
        private_key_path = self.key_dir / name
        public_key_path = self.key_dir / f"{name}.pub"
        
        if private_key_path.exists() and public_key_path.exists():
            self.logger.debug(f"Using existing SSH key pair: {name}")
            return str(private_key_path), str(public_key_path)
        
        # Create new key pair
        self.logger.info(f"Creating new SSH key pair: {name}")
        return self.generate_ssh_keypair(name, overwrite=True)
    
    def _is_retryable_error(self, result: SSHResult) -> bool:
        """
        Determine if an SSH error is retryable.
        
        Args:
            result: SSH execution result
            
        Returns:
            True if error might be transient and worth retrying
        """
        retryable_indicators = [
            "connection refused",
            "connection timed out",
            "network is unreachable",
            "temporary failure",
            "resource temporarily unavailable",
            "operation timed out"
        ]
        
        error_text = (result.stderr + (result.error_message or "")).lower()
        
        return any(indicator in error_text for indicator in retryable_indicators)
    
    def execute_parallel_ssh_command(
        self,
        hosts: List[str],
        username: str,
        command: str,
        timeout: int = 300,
        temp_file_prefix: str = "cyris_hosts"
    ) -> Dict[str, SSHResult]:
        """
        Execute command on multiple hosts using parallel-ssh approach (legacy compatibility).
        
        This method provides legacy-style parallel SSH execution similar to the original
        CyRIS system's parallel-ssh integration. It creates temporary host files and
        uses either system parallel-ssh or internal parallel execution.
        
        Args:
            hosts: List of hostnames/IPs to execute command on
            username: SSH username for all hosts
            command: Command to execute on all hosts
            timeout: Command execution timeout
            temp_file_prefix: Prefix for temporary host files
        
        Returns:
            Dictionary mapping hostname to SSH execution result
        """
        if not hosts:
            return {}
        
        # Log start in legacy style  
        self.logger.info(f"Execute parallel SSH command on {len(hosts)} hosts")
        
        try:
            # Method 1: Try system parallel-ssh if available
            if self._has_parallel_ssh():
                return self._execute_system_parallel_ssh(hosts, username, command, timeout, temp_file_prefix)
            else:
                # Method 2: Fallback to internal parallel execution
                return self._execute_internal_parallel_ssh(hosts, username, command, timeout)
                
        except Exception as e:
            error_msg = f"Parallel SSH execution failed: {e}"
            self.logger.error(error_msg)
            
            # Return error results for all hosts
            return {
                host: SSHResult(
                    hostname=host,
                    command=command,
                    return_code=-1,
                    stdout="",
                    stderr=str(e),
                    execution_time=0.0,
                    success=False,
                    error_message=str(e)
                ) for host in hosts
            }
    
    def _has_parallel_ssh(self) -> bool:
        """Check if parallel-ssh is available on system"""
        try:
            result = subprocess.run(
                ["which", "parallel-ssh"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _execute_system_parallel_ssh(
        self,
        hosts: List[str],
        username: str,
        command: str,
        timeout: int,
        temp_file_prefix: str
    ) -> Dict[str, SSHResult]:
        """Execute using system parallel-ssh command (legacy approach)"""
        import tempfile
        import os
        
        # Create temporary host file (legacy pattern)
        host_file = Path(tempfile.mkdtemp()) / f"{temp_file_prefix}_{len(hosts)}.txt"
        
        try:
            # Write hosts to file
            with open(host_file, 'w') as f:
                for host in hosts:
                    f.write(f"{host}\n")
            
            # Store temp file for cleanup
            self.temp_host_files[f"{temp_file_prefix}_{len(hosts)}"] = host_file
            
            # Execute parallel-ssh command (legacy format)
            parallel_ssh_cmd = [
                "parallel-ssh",
                "-h", str(host_file),
                "-l", username,
                "-t", str(timeout),
                "-p", str(min(len(hosts), 50)),  # Max 50 concurrent (legacy PSSH_CONCURRENCY)
                command
            ]
            
            self.logger.info(f"Running parallel-ssh with {len(hosts)} hosts")
            
            start_time = time.time()
            result = subprocess.run(
                parallel_ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 30  # Add buffer time
            )
            execution_time = time.time() - start_time
            
            # Parse parallel-ssh output and create results
            return self._parse_parallel_ssh_output(hosts, command, result, execution_time)
            
        finally:
            # Cleanup temporary files
            self._cleanup_temp_files()
    
    def _execute_internal_parallel_ssh(
        self,
        hosts: List[str],
        username: str,
        command: str,
        timeout: int
    ) -> Dict[str, SSHResult]:
        """Execute using internal parallel execution (fallback)"""
        # Use existing parallel execution capability
        host_commands = {}
        
        for host in hosts:
            credentials = SSHCredentials(hostname=host, username=username, timeout=timeout)
            host_commands[credentials] = [command]
        
        # Execute in parallel using existing method
        parallel_results = self.execute_commands_parallel(host_commands)
        
        # Convert to expected format
        results = {}
        for hostname, result_list in parallel_results.items():
            if result_list:
                results[hostname] = result_list[0]  # Take first result
        
        return results
    
    def _parse_parallel_ssh_output(
        self,
        hosts: List[str],
        command: str,
        subprocess_result: subprocess.CompletedProcess,
        execution_time: float
    ) -> Dict[str, SSHResult]:
        """Parse parallel-ssh output into SSHResult objects"""
        results = {}
        
        # Basic parsing - parallel-ssh output format is complex
        # For now, create results based on overall success
        overall_success = subprocess_result.returncode == 0
        
        for host in hosts:
            results[host] = SSHResult(
                hostname=host,
                command=command,
                return_code=subprocess_result.returncode,
                stdout=subprocess_result.stdout,
                stderr=subprocess_result.stderr,
                execution_time=execution_time / len(hosts),  # Approximate per-host time
                success=overall_success,
                error_message=subprocess_result.stderr if not overall_success else None
            )
        
        return results
    
    def _cleanup_temp_files(self) -> None:
        """Cleanup temporary host files"""
        for file_key, file_path in list(self.temp_host_files.items()):
            try:
                if file_path.exists():
                    file_path.unlink()
                    # Also remove parent temp directory if empty
                    parent = file_path.parent
                    if parent != Path.cwd() and not any(parent.iterdir()):
                        parent.rmdir()
                del self.temp_host_files[file_key]
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
    
    def cleanup_parallel_resources(self) -> None:
        """Cleanup all parallel SSH resources"""
        self._cleanup_temp_files()
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)