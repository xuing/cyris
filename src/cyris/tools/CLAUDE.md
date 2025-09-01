# Tools Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **tools**

## Module Responsibilities

The Tools module provides specialized utility components for SSH management, user account management, and VM IP discovery. These tools bridge the gap between high-level services and low-level infrastructure operations, offering reliable and reusable functionality across the system.

## Entry and Startup

- **Primary Entry**: `ssh_manager.py` - SSH connection management and execution
- **User Management**: `user_manager.py` - User account and permission management
- **IP Discovery**: `vm_ip_manager.py` - Multi-method VM IP address discovery
- **SSH Reliability**: `ssh_reliability_integration.py` - Enhanced SSH reliability features

### Tools Architecture
```
tools/
├── ssh_manager.py                    # SSH connection and task execution
├── user_manager.py                   # User account management
├── vm_ip_manager.py                  # VM IP discovery utilities
├── ssh_reliability_integration.py   # SSH reliability enhancements
└── __init__.py                      # Tool exports
```

## External Interfaces

### SSH Manager API
```python
class SSHManager:
    def __init__(self, host: str, username: str, auth_method: str = "key")
    
    def connect(self, timeout: int = 30) -> bool
    def execute_command(self, command: str, timeout: int = 300) -> SSHResult
    def copy_file(self, local_path: str, remote_path: str) -> bool
    def copy_directory(self, local_dir: str, remote_dir: str) -> bool
    def disconnect(self) -> None
    
    # Reliability features
    def execute_with_retry(self, command: str, max_retries: int = 3) -> SSHResult
    def test_connectivity(self) -> bool
```

### User Manager API
```python
class UserManager:
    def create_user(self, ssh_manager: SSHManager, user_config: Dict) -> UserResult
    def modify_user(self, ssh_manager: SSHManager, user_config: Dict) -> UserResult
    def verify_user_exists(self, ssh_manager: SSHManager, username: str) -> bool
    def verify_user_permissions(self, ssh_manager: SSHManager, user_config: Dict) -> bool
    
    # Advanced user management
    def setup_ssh_keys(self, ssh_manager: SSHManager, username: str, public_keys: List[str]) -> bool
    def configure_sudo_access(self, ssh_manager: SSHManager, user_config: Dict) -> bool
```

### VM IP Manager API
```python
class VMIPManager:
    def discover_vm_ip(self, vm_name: str) -> Optional[str]
    def discover_multiple_ips(self, vm_names: List[str]) -> Dict[str, str]
    def get_vm_ip_info(self, vm_name: str) -> Optional[VMIPInfo]
    def synchronize_metadata(self, range_id: str) -> Dict[str, str]
    
    # Discovery methods (priority order):
    # 1. topology → 2. libvirt → 3. virsh → 4. arp → 5. dhcp → 6. bridge
```

## Key Dependencies and Configuration

### External Dependencies
```python
paramiko>=4.0       # SSH client and server functionality
psutil>=7.0         # System process and network monitoring  
cryptography>=45.0  # SSH key handling and cryptographic operations
```

### System Dependencies
- **SSH Tools**: `openssh-client`, `ssh-keygen`, `ssh-copy-id`
- **Network Tools**: `arp`, `ip`, `bridge-utils`, `nmap` (optional)
- **User Management**: `useradd`, `usermod`, `passwd`, `sudo`

### Internal Dependencies  
- `config.settings` - Authentication and connection configuration
- `core.network_reliability` - Network validation and retry policies
- `core.exceptions` - Structured error handling
- `infrastructure.network` - Network topology information

### Tool Configuration
```python
class ToolsConfig(BaseSettings):
    # SSH Configuration
    ssh_timeout: int = 30
    ssh_retry_count: int = 3
    ssh_retry_delay: int = 5
    default_ssh_user: str = "ubuntu"
    ssh_key_path: Path = Path.home() / ".ssh/id_rsa"
    
    # IP Discovery Configuration  
    ip_discovery_timeout: int = 60
    ip_cache_ttl: int = 300  # 5 minutes
    enable_arp_discovery: bool = True
    enable_dhcp_discovery: bool = True
    
    # User Management Configuration
    default_shell: str = "/bin/bash"  
    create_home_dir: bool = True
    enable_sudo_group: bool = True
```

## Data Models

### SSH Operations
```python
@dataclass
class SSHResult:
    success: bool
    stdout: str
    stderr: str  
    exit_code: int
    execution_time: float
    timestamp: datetime

@dataclass
class SSHConnectionInfo:
    host: str
    port: int
    username: str
    auth_method: str  # "key", "password", "agent"
    connected: bool
    last_used: datetime
```

### VM IP Discovery
```python
@dataclass  
class VMIPInfo:
    vm_name: str
    vm_id: str
    ip_addresses: List[str]
    mac_addresses: List[str]
    interface_names: List[str]
    discovery_method: str  # "topology", "libvirt", "virsh", "arp", "dhcp", "bridge"
    last_updated: str
    status: str  # "active", "inactive", "unknown"

@dataclass
class IPDiscoveryResult:
    vm_name: str
    discovered_ip: Optional[str]
    method_used: str
    confidence: float  # 0.0 to 1.0
    diagnostics: Dict[str, Any]
```

### User Management
```python
@dataclass
class UserResult:
    username: str
    success: bool
    message: str
    evidence: Optional[str]  # Verification evidence
    created: bool
    home_dir: Optional[str]
    groups: List[str]
    sudo_access: bool

@dataclass
class UserConfig:
    username: str
    password: Optional[str] = None
    public_keys: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    sudo_access: bool = False
    shell: str = "/bin/bash"
    create_home: bool = True
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_ssh_manager.py` - SSH manager functionality
- `/home/ubuntu/cyris/tests/unit/test_user_manager.py` - User management operations
- `/home/ubuntu/cyris/tests/unit/test_ssh_reliability_integration.py` - SSH reliability features
- Mock SSH connections and system commands for isolated testing

### Integration Tests
- `/home/ubuntu/cyris/tests/integration/test_tools_integration.py` - Tool interaction testing
- Use testcontainers or dedicated test VMs for SSH integration testing
- Test real user creation and IP discovery operations

### Reliability Testing
- Network interruption simulation and recovery testing
- SSH connection timeout and retry behavior validation
- IP discovery method fallback and accuracy testing

### Quality Requirements
- **SSH Reliability**: 99%+ success rate with proper retry mechanisms
- **IP Discovery**: < 60 seconds discovery time with 95%+ accuracy
- **User Management**: Atomic operations with rollback on failure
- **Error Handling**: Detailed diagnostics and actionable error messages

## Frequently Asked Questions (FAQ)

### Q: How does SSH key authentication work with different VM types?
A: The SSH manager supports multiple authentication methods: SSH keys (preferred), password authentication, and SSH agent forwarding. Keys are automatically injected during VM creation via cloud-init.

### Q: What happens when IP discovery methods fail?
A: The system uses a priority-based fallback strategy: topology metadata → libvirt DHCP → virsh domifaddr → ARP table → DHCP logs → bridge inspection. Each method has timeout and error handling.

### Q: How are user creation operations verified?
A: After creating a user, the system verifies by attempting to login, checking home directory existence, validating group memberships, and testing sudo access if configured.

### Q: Can SSH connections be reused across multiple operations?
A: Yes, SSH connections are pooled and reused within the same session. Connections auto-reconnect on failures and are properly cleaned up on completion.

### Q: How does the system handle network partitions or VM unreachability?
A: SSH operations use progressive backoff retry with health checking. IP discovery falls back to cached information and provides diagnostic information about connectivity issues.

### Q: What security measures are implemented for SSH operations?
A: Host key verification, secure key storage, connection timeout enforcement, command sanitization, and audit logging of all SSH operations.

## Related File List

### Core Tools
- `/home/ubuntu/cyris/src/cyris/tools/ssh_manager.py` - SSH connection and execution management
- `/home/ubuntu/cyris/src/cyris/tools/user_manager.py` - User account and permission management  
- `/home/ubuntu/cyris/src/cyris/tools/vm_ip_manager.py` - Multi-method VM IP discovery
- `/home/ubuntu/cyris/src/cyris/tools/ssh_reliability_integration.py` - Enhanced SSH reliability
- `/home/ubuntu/cyris/src/cyris/tools/__init__.py` - Tools module exports

### Tool Tests
- `/home/ubuntu/cyris/tests/unit/test_ssh_manager.py` - SSH manager unit tests
- `/home/ubuntu/cyris/tests/unit/test_user_manager.py` - User manager unit tests
- `/home/ubuntu/cyris/tests/unit/test_ssh_reliability_integration.py` - SSH reliability tests
- `/home/ubuntu/cyris/tests/unit/test_ssh_reliability_integration_simple.py` - Simplified reliability tests

### Integration Tests
- Tests integrated within service and infrastructure test suites
- Real SSH and user management testing in E2E test scenarios

### Configuration
- SSH key management integrated with system configuration
- User management templates and defaults in configuration layer

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Tools module documentation with comprehensive utility coverage
- **[RELIABILITY]** Documented SSH reliability features and multi-method IP discovery strategy
- **[INTEGRATION]** Outlined testing approach for tool reliability and integration patterns