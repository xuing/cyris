# Instantiation Module

[Root Directory](../CLAUDE.md) > **instantiation**

## Module Responsibilities

The Instantiation module contains specialized scripts and utilities for cyber range deployment tasks. These scripts handle VM creation, network setup, user management, attack emulation, malware deployment, and security configuration. This module provides the low-level implementation for task execution requested through YAML configurations.

## Entry and Startup

- **VM Management**: `vm_clone/` - Virtual machine cloning and lifecycle scripts
- **Attack Emulation**: `attacks_emulation/` - Cybersecurity attack simulation scripts  
- **User Management**: `users_managing/` - User account creation and modification
- **Network Config**: `sshkey_hostname_setup/` - SSH key deployment and hostname configuration
- **Security Tools**: `ruleset_modification/` - Firewall rules and security policies
- **Content Management**: `content_copy_program_run/` - File copying and program execution
- **Log Generation**: `logs_preparation/` - Network traffic and log generation

### Instantiation Architecture
```
instantiation/
├── vm_clone/                    # VM creation and destruction
│   ├── create_vms.sh           # VM cloning and setup
│   ├── create_bridges.sh       # Network bridge creation
│   ├── vm_clone_xml.sh         # XML-based VM cloning
│   └── vm_destroy_xml.sh       # VM cleanup and destruction
├── attacks_emulation/           # Cybersecurity attack simulation
│   ├── attack_paramiko_ssh.py  # SSH brute force attacks
│   ├── launch_dos.sh          # Denial of Service attacks
│   └── launch_ddos.sh         # Distributed DoS attacks
├── users_managing/             # User account management
│   ├── add_user.sh            # User creation script
│   └── modify_user.sh         # User modification script
├── sshkey_hostname_setup/      # SSH and hostname configuration
│   ├── sshkey_setup.sh        # SSH key deployment
│   └── hostname_setup.sh      # Hostname configuration
├── ruleset_modification/       # Firewall and security rules
│   ├── firewall_ruleset.sh    # Firewall configuration
│   └── append_ruleset.py      # Dynamic rule management
├── content_copy_program_run/   # File operations and execution
│   ├── copy_content.sh        # File copying utilities
│   └── run_program.py         # Program execution management
└── logs_preparation/           # Log and traffic generation
    ├── mergePcap.py          # PCAP file merging
    └── pcap_*_generator.sh   # Traffic generation scripts
```

## External Interfaces

### VM Management Scripts
```bash
# VM cloning and setup
./instantiation/vm_clone/create_vms.sh <base_vm> <new_vm_name> <config>

# Network bridge management  
./instantiation/vm_clone/create_bridges.sh <bridge_name> <subnet>

# VM destruction and cleanup
./instantiation/vm_clone/vm_destroy_xml.sh <vm_name>
```

### User Management Scripts
```bash
# User creation
./instantiation/users_managing/add_user.sh <username> <password> [groups]

# User modification  
./instantiation/users_managing/modify_user.sh <username> <modifications>
```

### Attack Emulation Scripts
```bash
# SSH brute force attack
python3 ./instantiation/attacks_emulation/attack_paramiko_ssh.py <target> <wordlist>

# DoS attack simulation
./instantiation/attacks_emulation/launch_dos.sh <target_ip> <duration>

# DDoS attack simulation  
./instantiation/attacks_emulation/launch_ddos.sh <target_ip> <node_list>
```

### Security Configuration Scripts
```bash
# SSH key deployment
./instantiation/sshkey_hostname_setup/sshkey_setup.sh <target> <public_key>

# Firewall configuration
./instantiation/ruleset_modification/firewall_ruleset.sh <rules_file>

# Hostname setup
./instantiation/sshkey_hostname_setup/hostname_setup.sh <new_hostname>
```

### Content and Program Management
```bash
# File copying operations
./instantiation/content_copy_program_run/copy_content.sh <source> <dest> <target>

# Program execution
python3 ./instantiation/content_copy_program_run/run_program.py <program> <args>
```

## Key Dependencies and Configuration

### System Dependencies
```bash
# Virtualization tools
qemu-kvm
libvirt-daemon-system
virtinst
virt-manager

# Network tools
bridge-utils
iptables
dnsmasq
nmap

# SSH and security tools
openssh-server
openssh-client
ssh-copy-id

# Attack simulation tools  
hping3
tcpdump
wireshark-common
```

### Python Dependencies
```python
paramiko>=3.0        # SSH operations for attack simulation
psutil>=5.9         # System monitoring and process management
scapy>=2.4          # Network packet manipulation
```

### Script Configuration
```bash
# VM cloning configuration
BASE_VM_PATH="/var/lib/libvirt/images"
CLONE_PATH="/var/lib/libvirt/images/clones"
BRIDGE_PREFIX="cr-br"

# Attack simulation configuration
SSH_TIMEOUT=30
ATTACK_DURATION=300
WORDLIST_PATH="/usr/share/wordlists"

# User management configuration
DEFAULT_SHELL="/bin/bash"
DEFAULT_GROUPS="users"
SUDO_GROUP="sudo"
```

## Data Models

### Script Execution Results
```python
@dataclass
class ScriptResult:
    """Result of instantiation script execution"""
    script_name: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: datetime

@dataclass  
class VMCloneResult:
    """Result of VM cloning operation"""
    base_vm: str
    cloned_vm: str
    vm_uuid: str
    ip_address: Optional[str]
    success: bool
    error_message: Optional[str]
```

### Attack Simulation Models
```python
@dataclass
class AttackConfig:
    """Configuration for attack simulation"""
    attack_type: str  # "ssh_bruteforce", "dos", "ddos"
    target_host: str
    target_port: int = 22
    duration: int = 300  # seconds
    intensity: str = "medium"  # "low", "medium", "high"
    
@dataclass
class AttackResult:
    """Result of attack simulation"""
    attack_type: str
    target: str
    success_rate: float
    packets_sent: int
    connections_attempted: int
    duration: float
```

### User Management Models
```bash
# User creation parameters
USERNAME="testuser"
PASSWORD="securepass123"
GROUPS="users,sudo"
HOME_DIR="/home/testuser"
SHELL="/bin/bash"
CREATE_HOME=true
```

## Testing and Quality

### Script Testing Strategy
```bash
# Test VM operations in isolated environment
TEST_BASE_VM="test-ubuntu-base"
TEST_CLONE_PREFIX="test-clone"
TEST_BRIDGE="test-br0"

# Test user operations with temporary accounts
TEST_USERNAME="cyris-test-user"
TEST_CLEANUP=true

# Test attacks against controlled targets
TEST_TARGET_VM="test-target"
TEST_ATTACK_DURATION=30  # Short duration for testing
```

### Safety and Security Testing
- **Isolation Testing**: Verify scripts work in isolated test environments
- **Privilege Testing**: Ensure proper privilege handling and escalation  
- **Cleanup Testing**: Verify complete cleanup after script execution
- **Error Handling**: Test script behavior under failure conditions

### Quality Requirements
- **Safety**: All scripts must be safe for isolated training environments only
- **Cleanup**: Scripts must clean up resources and processes on completion
- **Error Handling**: Proper exit codes and error messages for all failure modes
- **Documentation**: Each script must have clear usage documentation

## Frequently Asked Questions (FAQ)

### Q: Are these scripts safe to run in production environments?
A: **NO**. These scripts are designed exclusively for isolated cybersecurity training environments. They contain attack simulation and potentially destructive operations.

### Q: How do I safely test instantiation scripts?
A: Use isolated test VMs, dedicated test networks, and always run cleanup scripts after testing. Never test on production systems.

### Q: Can I modify the attack simulation scripts?
A: Yes, but maintain the same interface and safety measures. All modifications should be tested thoroughly in isolated environments.

### Q: How do the scripts handle failures and cleanup?
A: Each script includes error handling and cleanup routines. Failed operations attempt automatic cleanup, but manual verification is recommended.

### Q: What happens if a VM clone operation fails?
A: Partial VMs and resources are cleaned up automatically. Check logs for specific failure reasons and ensure sufficient disk space and permissions.

### Q: How are SSH keys managed securely?
A: SSH keys are generated with secure permissions, deployed using secure channels, and cleaned up after use. Private keys are never transmitted.

## Related File List

### VM Management Scripts
- `/home/ubuntu/cyris/instantiation/vm_clone/create_vms.sh` - VM cloning and configuration
- `/home/ubuntu/cyris/instantiation/vm_clone/create_bridges.sh` - Network bridge creation
- `/home/ubuntu/cyris/instantiation/vm_clone/vm_clone_xml.sh` - XML-based VM cloning
- `/home/ubuntu/cyris/instantiation/vm_clone/vm_destroy_xml.sh` - VM cleanup and destruction
- `/home/ubuntu/cyris/instantiation/vm_clone/check_ping.py` - Network connectivity testing

### Attack Emulation Scripts
- `/home/ubuntu/cyris/instantiation/attacks_emulation/attack_paramiko_ssh.py` - SSH brute force simulation
- `/home/ubuntu/cyris/instantiation/attacks_emulation/launch_dos.sh` - DoS attack simulation
- `/home/ubuntu/cyris/instantiation/attacks_emulation/launch_ddos.sh` - DDoS attack simulation
- `/home/ubuntu/cyris/instantiation/attacks_emulation/install_paramiko.sh` - Attack tool installation

### User Management Scripts
- `/home/ubuntu/cyris/instantiation/users_managing/add_user.sh` - User account creation
- `/home/ubuntu/cyris/instantiation/users_managing/modify_user.sh` - User account modification

### SSH and Hostname Configuration
- `/home/ubuntu/cyris/instantiation/sshkey_hostname_setup/sshkey_setup.sh` - SSH key deployment
- `/home/ubuntu/cyris/instantiation/sshkey_hostname_setup/hostname_setup.sh` - Hostname configuration  
- `/home/ubuntu/cyris/instantiation/sshkey_hostname_setup/sshkey_setup_win_unix.sh` - Cross-platform SSH setup
- `/home/ubuntu/cyris/instantiation/sshkey_hostname_setup/create_ch_acl.ps1` - Windows ACL configuration

### Security Configuration Scripts  
- `/home/ubuntu/cyris/instantiation/ruleset_modification/firewall_ruleset.sh` - Firewall configuration
- `/home/ubuntu/cyris/instantiation/ruleset_modification/append_ruleset.py` - Dynamic rule management
- `/home/ubuntu/cyris/instantiation/ruleset_modification/iptables_template` - Firewall rule templates

### Content and Program Management
- `/home/ubuntu/cyris/instantiation/content_copy_program_run/copy_content.sh` - File copying utilities
- `/home/ubuntu/cyris/instantiation/content_copy_program_run/run_program.py` - Program execution
- `/home/ubuntu/cyris/instantiation/content_copy_program_run/limitedstringqueue.py` - Output management

### Log and Traffic Generation
- `/home/ubuntu/cyris/instantiation/logs_preparation/mergePcap.py` - PCAP file merging
- `/home/ubuntu/cyris/instantiation/logs_preparation/pcap_sshattack_generator.sh` - SSH attack traffic
- `/home/ubuntu/cyris/instantiation/logs_preparation/pcap_dosattack_generator.sh` - DoS traffic generation
- `/home/ubuntu/cyris/instantiation/logs_preparation/noise_*.pcap` - Background traffic samples

### Malware Simulation
- `/home/ubuntu/cyris/instantiation/malware_creation/malware_launch.sh` - Malware deployment
- `/home/ubuntu/cyris/instantiation/malware_creation/dummy_malware.c` - Sample malware source
- `/home/ubuntu/cyris/instantiation/malware_creation/dummy_malware` - Compiled malware binary

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Instantiation module documentation with comprehensive script coverage
- **[SECURITY]** Documented safety guidelines and isolated training environment requirements
- **[FUNCTIONALITY]** Outlined all major script categories and their cybersecurity training applications