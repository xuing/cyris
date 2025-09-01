# Legacy Main Module

[Root Directory](../../CLAUDE.md) > [legacy](./) > **main**

## Module Responsibilities

The Legacy Main module contains the original CyRIS implementation, providing backward compatibility with existing YAML configurations and deployment scripts. This module implements the complete cyber range creation workflow using the original architecture, supporting both KVM and AWS providers with full task execution and verification capabilities.

## Entry and Startup

- **Primary Entry**: `cyris.py` - Main legacy cyber range creation system
- **Configuration**: `parse_config.py` - INI configuration file parsing
- **Entities**: `entities.py` - Legacy entity definitions (Host, Guest, Clone objects)
- **VM Management**: `clone_environment.py` - VM cloning and environment setup
- **Modules**: `modules.py` - Task execution modules (SSH, attacks, users, etc.)

### Legacy Architecture
```
legacy/main/
├── cyris.py              # Main cyber range creation engine
├── entities.py           # Legacy entity definitions
├── clone_environment.py  # VM cloning and environment management  
├── parse_config.py       # INI configuration parsing
├── check_description.py  # YAML description validation
├── storyboard.py         # Range creation workflow
├── modules.py           # Task execution modules
├── cyvar.py             # Variable management system
└── aws_*.py             # AWS provider implementation
```

## External Interfaces

### Main Legacy API
```python
class CyberRangeCreation:
    """Main legacy cyber range creation class"""
    def main(self, description_file: str, config_file: str) -> bool
    def create_cyber_range(self, clone_settings: List[CloneSetting]) -> bool
    def destroy_cyber_range(self, range_id: str) -> bool
    def notify_cyber_range_created(self, range_info: Dict) -> None

# Global entry point
def main(argv: List[str]) -> None:
    """Legacy command-line entry point"""
```

### Entity System (Legacy)
```python
class Host:
    """Physical host representation"""
    def __init__(self, id: str, mgmt_addr: str, virbr_addr: str, account: str)

class Guest:  
    """Virtual machine representation"""
    def __init__(self, id: str, basevm_host: str, basevm_config_file: str, ...)

class CloneSetting:
    """Range cloning configuration"""
    def __init__(self, range_id: str, hosts: List, guests: List, topology: List)

class CloneInstance:
    """Individual range instance"""
    def __init__(self, range_id: str, instance_number: int)
```

### Task Execution Modules
```python
# Available task modules from modules.py
class SSHKeygenHostname:
    """SSH key generation and hostname setup"""

class ManageUsers:
    """User account management (add/modify users)"""

class EmulateAttacks:  
    """Attack emulation (SSH, DoS, DDoS)"""

class EmulateMalware:
    """Malware emulation and deployment"""

class InstallTools:
    """Package installation and tool setup"""

class ModifyRuleset:
    """Firewall ruleset modification"""

class CopyContent:
    """File and content copying"""

class ExecuteProgram:
    """Program execution and verification"""
```

### AWS Provider Integration
```python
# AWS-specific modules
from aws_instances import create_instances, stop_instances, clone_instances
from aws_sg import create_security_group, edit_ingress
from aws_image import create_img, describe_image
from aws_info import edit_tags, get_info

# AWS configuration support
AWS_REGION = "us-west-2"
AWS_VPC_ID = None
AWS_SUBNET_ID = None
```

## Key Dependencies and Configuration

### External Dependencies
```python
PyYAML>=6.0           # YAML parsing for range descriptions
boto3>=1.34          # AWS SDK for cloud deployment
paramiko>=3.0        # SSH operations and file transfer
psutil>=5.9          # System resource monitoring
```

### Legacy Configuration Format (INI)
```ini
[config]
abs_path = /opt/cyris
cr_dir = /opt/cyris/cyber_range
gw_mode = no
gw_account = 
gw_mgmt_addr = 
gw_inside_addr = 
user_email = admin@example.com
```

### System Constants and Settings
```python
# SSH and connectivity settings
CHECK_SSH_TIMEOUT_TOTAL = 1000  # Total timeout for SSH connectivity
CHECK_SSH_TIMEOUT_ONCE = 20     # Single attempt timeout
PSSH_TIMEOUT = 1000            # Parallel SSH timeout
PSSH_CONCURRENCY = 50          # Max concurrent SSH connections

# Default credentials and paths
BASEIMG_ROOT_PASSWD = "theroot"
MSTNODE_ACCOUNT = ""
INSTANTIATION_DIR = "instantiation"

# Email notification settings (optional)
EMAIL_SERVER = "server_hostname"
EMAIL_SENDER = "Sender Name <sender@domain>"
```

## Data Models

### Legacy Entity Structure
```python
class Host:
    """Legacy host entity"""
    id: str
    mgmt_addr: str           # Management address
    virbr_addr: str          # Virtual bridge address
    account: str             # SSH account name

class Guest:
    """Legacy guest entity"""  
    id: str
    ip_addr: Optional[str]   # Assigned IP address
    basevm_host: str         # Host where base VM resides
    basevm_config_file: str  # VM configuration file path
    basevm_os_type: str      # Operating system type
    basevm_type: str         # Virtualization type (kvm/aws)
    tasks: List[Dict]        # Task list for execution
```

### Range Creation Workflow
```python
@dataclass
class RangeCreationResult:
    """Result of legacy range creation"""
    success: bool
    range_id: str
    created_vms: List[str]
    execution_log: List[str]
    error_message: Optional[str]
    creation_time: datetime
    
class WorkflowStep(Enum):
    """Legacy creation workflow steps"""
    PARSE_DESCRIPTION = "parse_description"
    VALIDATE_CONFIG = "validate_config" 
    CREATE_VMS = "create_vms"
    SETUP_NETWORK = "setup_network"
    EXECUTE_TASKS = "execute_tasks"
    VERIFY_DEPLOYMENT = "verify_deployment"
    SEND_NOTIFICATION = "send_notification"
```

### Task Execution Format
```python
# Legacy YAML task format
tasks:
  - type: "add_account"
    parameters:
      account_name: "user1"
      account_password: "password123"
      account_groups: ["sudo"]
      
  - type: "emulate_attack_ssh"
    parameters:
      target_host: "192.168.1.100"
      username: "victim"
      password_list: ["123456", "password"]
```

## Testing and Quality

### Legacy Compatibility Testing
- `/home/ubuntu/cyris/tests/test_legacy_core.py` - Core legacy functionality testing
- `/home/ubuntu/cyris/tests/integration/test_legacy_compatibility.py` - Integration with modern system
- Focus on backward compatibility and regression prevention

### YAML Description Testing
- Test parsing of all legacy YAML format variations
- Validate entity creation from legacy descriptions
- Ensure task execution compatibility

### Legacy Quality Requirements
- **Backward Compatibility**: 100% compatibility with existing YAML configurations
- **Task Execution**: All legacy task types must function correctly
- **Error Handling**: Maintain existing error handling behavior
- **Performance**: Legacy workflows should complete within historical time limits

## Frequently Asked Questions (FAQ)

### Q: Should I use the legacy system for new deployments?
A: No, use the modern CLI (`./cyris create`) for new deployments. The legacy system is maintained for backward compatibility only.

### Q: How does the legacy system integrate with the modern CLI?
A: The modern CLI can invoke legacy functionality through the `./cyris legacy` command while providing a consistent interface.

### Q: Are all original CyRIS features supported in the legacy system?
A: Yes, the legacy system maintains complete feature parity with the original CyRIS implementation, including all task types and AWS support.

### Q: Can I migrate legacy YAML descriptions to the modern format?
A: Most legacy YAML descriptions work directly with the modern system. Complex configurations may need minor adjustments.

### Q: How are errors handled in the legacy system?
A: The legacy system uses traditional exception handling with detailed logging. Errors are logged to files and optionally sent via email notification.

### Q: What is the migration path from legacy to modern architecture?
A: Continue using legacy for existing ranges, use modern CLI for new ranges, gradually migrate configurations as needed.

## Related File List

### Core Legacy Files
- `/home/ubuntu/cyris/legacy/main/cyris.py` - Main legacy cyber range creation engine
- `/home/ubuntu/cyris/legacy/main/entities.py` - Legacy entity definitions and data models
- `/home/ubuntu/cyris/legacy/main/clone_environment.py` - VM cloning and environment setup
- `/home/ubuntu/cyris/legacy/main/parse_config.py` - INI configuration file parsing
- `/home/ubuntu/cyris/legacy/main/check_description.py` - YAML description validation
- `/home/ubuntu/cyris/legacy/main/storyboard.py` - Range creation workflow management
- `/home/ubuntu/cyris/legacy/main/modules.py` - Task execution modules and utilities
- `/home/ubuntu/cyris/legacy/main/cyvar.py` - Variable management system

### AWS Integration
- `/home/ubuntu/cyris/legacy/main/aws_instances.py` - AWS EC2 instance management
- `/home/ubuntu/cyris/legacy/main/aws_sg.py` - AWS security group management
- `/home/ubuntu/cyris/legacy/main/aws_image.py` - AWS AMI management
- `/home/ubuntu/cyris/legacy/main/aws_info.py` - AWS resource information and tagging
- `/home/ubuntu/cyris/legacy/main/aws_cleanup.py` - AWS resource cleanup utilities

### Legacy Tests
- `/home/ubuntu/cyris/tests/test_legacy_core.py` - Legacy core functionality tests
- `/home/ubuntu/cyris/tests/integration/test_legacy_compatibility.py` - Legacy integration tests
- `/home/ubuntu/cyris/tests/unit/test_legacy_entities.py` - Legacy entity testing

### Configuration and Templates
- `/home/ubuntu/cyris/CONFIG` - Default legacy configuration file
- `/home/ubuntu/cyris/legacy/settings/` - Legacy configuration templates
- `/home/ubuntu/cyris/legacy/main/mail_template` - Email notification template

### Integration Points
- Invoked by `/home/ubuntu/cyris/src/cyris/cli/commands/legacy_command.py`
- Uses `/home/ubuntu/cyris/instantiation/` scripts for task execution
- Integrates with modern configuration through compatibility layer

## Change Log (Changelog)

### 2025-09-01  
- **[INITIALIZATION]** Created Legacy Main module documentation with comprehensive backward compatibility coverage
- **[COMPATIBILITY]** Documented integration with modern CLI and migration strategies
- **[MAINTENANCE]** Outlined legacy system maintenance and support approach for existing deployments