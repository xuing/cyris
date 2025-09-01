# Examples Module

[Root Directory](../CLAUDE.md) > **examples**

## Module Responsibilities

The Examples module provides comprehensive YAML configuration templates and sample cyber range descriptions that demonstrate CyRIS capabilities. These examples serve as starting points for creating custom training environments, showcasing different deployment scenarios, task configurations, and network topologies.

## Entry and Startup

- **Basic Example**: `basic.yml` - Simple single-VM range for getting started
- **Multi-Host**: `basic-multi_host.yml` - Multiple physical hosts configuration
- **Cloud Deployment**: `basic-aws.yml` - AWS cloud deployment example
- **Advanced Networks**: `dmz.yml` - DMZ network topology with multiple zones
- **Full Featured**: `full.yml` - Comprehensive example with all features
- **Windows Support**: `basic-windows7.yml` - Windows VM configuration example

### Examples Architecture
```
examples/
├── basic.yml                 # Simple single-VM range
├── basic-multi_host.yml      # Multi-host deployment
├── basic-aws.yml            # AWS cloud deployment
├── basic-windows7.yml       # Windows VM example
├── dmz.yml                  # DMZ network topology
├── full.yml                 # Comprehensive feature demo
├── full_comprehensive_test.yml  # Testing configuration
├── arch_test.yml            # Architecture testing
└── test_*.yml               # Additional test configurations
```

## External Interfaces

### YAML Configuration Structure
```yaml
# Standard CyRIS YAML format
---
- host_settings:
  - id: host_1
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu

- guest_settings:
  - id: desktop
    basevm_host: host_1
    basevm_config_file: /path/to/basevm.xml
    basevm_type: kvm
    basevm_os_type: ubuntu

- clone_settings:
  - range_id: example_range
    hosts:
    - host_id: host_1
      instance_number: 1
      guests:
      - guest_id: desktop
        number: 1
        entry_point: yes
        tasks:
        - type: add_account
          parameters:
            account_name: trainee
            account_password: training123
```

### Basic Configuration Template
```yaml
# Minimal working configuration
---
- host_settings:
  - id: localhost
    mgmt_addr: localhost
    virbr_addr: 192.168.122.1
    account: ubuntu

- guest_settings:
  - id: ubuntu_desktop
    basevm_host: localhost
    basevm_config_file: /var/lib/libvirt/images/ubuntu-base.xml
    basevm_type: kvm
    basevm_os_type: ubuntu

- clone_settings:
  - range_id: training_basic
    hosts:
    - host_id: localhost
      instance_number: 1
      guests:
      - guest_id: ubuntu_desktop
        number: 1
        entry_point: yes
      topology:
      - type: custom
        networks:
        - name: internal
          members: ubuntu_desktop.eth0
```

### Advanced Network Topology
```yaml
# DMZ network configuration example
topology:
- type: custom
  networks:
  - name: dmz
    subnet: 192.168.10.0/24
    members:
    - web_server.eth0
    - mail_server.eth0
  - name: internal
    subnet: 192.168.20.0/24  
    members:
    - workstation.eth0
    - database.eth0
  - name: management
    subnet: 192.168.30.0/24
    members:
    - firewall.eth1
    - monitoring.eth0
```

## Key Dependencies and Configuration

### Example Prerequisites
- **Base VM Images**: Pre-configured base virtual machine templates
- **Network Configuration**: Proper libvirt network setup
- **Storage Space**: Sufficient disk space for VM clones
- **System Resources**: Adequate CPU and memory for concurrent VMs

### Supported Configurations
```yaml
# Supported base VM types
basevm_type:
  - kvm      # KVM/QEMU virtualization
  - aws      # AWS EC2 instances

# Supported operating systems  
basevm_os_type:
  - ubuntu          # Ubuntu Linux (any version)
  - ubuntu_20       # Ubuntu 20.04 LTS
  - centos         # CentOS Linux
  - windows.7      # Windows 7
  - windows.10     # Windows 10
  - amazon_linux   # Amazon Linux (AWS)
```

### Task Type Examples
```yaml
# User management tasks
tasks:
  - type: add_account
    parameters:
      account_name: student
      account_password: password123
      account_groups: [users, sudo]

# Attack simulation tasks
  - type: emulate_attack_ssh
    parameters:
      target_host: 192.168.1.100
      username_list: [admin, user, guest]
      password_list: [123456, password, admin]

# Software installation tasks  
  - type: install_package
    parameters:
      package_manager: apt
      packages: [wireshark, nmap, tcpdump]

# Content deployment tasks
  - type: copy_content
    parameters:
      source_path: /host/training/materials
      dest_path: /home/student/materials
      
# Program execution tasks
  - type: execute_program
    parameters:
      program_path: /usr/local/bin/setup_lab.sh
      arguments: [--scenario, basic]
```

## Data Models

### Configuration Templates
```python
@dataclass
class ExampleConfig:
    """Example configuration metadata"""
    name: str
    description: str  
    difficulty: str  # "beginner", "intermediate", "advanced"
    vm_count: int
    network_complexity: str  # "simple", "moderate", "complex"
    features: List[str]  # List of demonstrated features
    estimated_resources: Dict[str, str]  # CPU, RAM, Disk requirements

# Example configuration catalog
EXAMPLE_CATALOG = {
    "basic": ExampleConfig(
        name="Basic Single VM",
        description="Simple single-VM range for getting started",
        difficulty="beginner",
        vm_count=1,
        network_complexity="simple",
        features=["user_management", "basic_networking"],
        estimated_resources={"cpu": "1 core", "ram": "2GB", "disk": "10GB"}
    ),
    
    "dmz": ExampleConfig(
        name="DMZ Network Topology", 
        description="Multi-zone network with DMZ configuration",
        difficulty="advanced",
        vm_count=5,
        network_complexity="complex",
        features=["multi_zone_network", "firewall_rules", "attack_simulation"],
        estimated_resources={"cpu": "4 cores", "ram": "8GB", "disk": "40GB"}
    )
}
```

### Validation Schemas
```python
class YAMLValidator:
    """YAML configuration validation"""
    
    def validate_structure(self, config: Dict) -> ValidationResult:
        """Validate overall YAML structure"""
        
    def validate_hosts(self, hosts: List[Dict]) -> ValidationResult:
        """Validate host configuration section"""
        
    def validate_guests(self, guests: List[Dict]) -> ValidationResult:
        """Validate guest configuration section"""
        
    def validate_tasks(self, tasks: List[Dict]) -> ValidationResult:
        """Validate task configuration syntax"""
```

## Testing and Quality

### Example Validation Testing
```python
class TestExampleConfigurations:
    """Example configuration testing"""
    
    def test_basic_yaml_parsing(self):
        """Test basic YAML can be parsed without errors"""
        
    def test_multi_host_configuration(self):
        """Test multi-host example deploys correctly"""
        
    def test_aws_configuration(self):
        """Test AWS example has valid configuration"""
        
    def test_all_task_types_represented(self):
        """Ensure examples cover all supported task types"""
```

### Quality Requirements
- **Syntax Validation**: All YAML examples must be syntactically valid
- **Deployment Testing**: Examples should deploy successfully in test environments
- **Documentation**: Each example must have clear documentation and use cases
- **Resource Estimation**: Accurate resource requirements for each example

## Frequently Asked Questions (FAQ)

### Q: Which example should I start with?
A: Start with `basic.yml` for a simple single-VM setup, then progress to `basic-multi_host.yml` or `dmz.yml` based on your needs.

### Q: Can I modify the examples for my own use?
A: Yes, examples are templates designed to be customized. Copy and modify them for your specific training scenarios.

### Q: How do I adapt examples for AWS deployment?
A: Use `basic-aws.yml` as a reference, updating the `basevm_type` to `aws` and configuring AWS-specific parameters.

### Q: What base VM images do I need for the examples?
A: You'll need base VM images for the operating systems referenced in the examples. Check the `basevm_config_file` paths and create corresponding base VMs.

### Q: How can I estimate resource requirements for my modified examples?
A: Consider VM count × resource per VM + overhead. Use the example metadata as a starting point and test in your environment.

### Q: Can examples be combined or merged?
A: Yes, you can combine network topologies and task configurations from different examples to create complex training scenarios.

## Related File List

### Basic Examples
- `/home/ubuntu/cyris/examples/basic.yml` - Simple single-VM training range
- `/home/ubuntu/cyris/examples/basic-multi_host.yml` - Multi-host deployment example
- `/home/ubuntu/cyris/examples/basic-aws.yml` - AWS cloud deployment configuration
- `/home/ubuntu/cyris/examples/basic-windows7.yml` - Windows VM configuration example

### Advanced Examples
- `/home/ubuntu/cyris/examples/dmz.yml` - DMZ network topology with multiple security zones
- `/home/ubuntu/cyris/examples/full.yml` - Comprehensive feature demonstration
- `/home/ubuntu/cyris/examples/full_comprehensive_test.yml` - Full testing configuration
- `/home/ubuntu/cyris/examples/full_adapted.yml` - Adapted comprehensive configuration

### Testing Configurations
- `/home/ubuntu/cyris/examples/arch_test.yml` - Architecture testing configuration
- `/home/ubuntu/cyris/examples/full_test.yml` - Full feature testing
- `/home/ubuntu/cyris/examples/test_add_account.yml` - User management testing
- `/home/ubuntu/cyris/examples/full_fixed.yml` - Fixed configuration for testing

### Usage Integration
- Used by `/home/ubuntu/cyris/src/cyris/cli/main.py` for `create` command examples
- Referenced in `/home/ubuntu/cyris/src/cyris/config/parser.py` for YAML parsing validation
- Tested by `/home/ubuntu/cyris/tests/e2e/test_full_deployment.py` for end-to-end validation

### Documentation References
- Examples referenced throughout `/home/ubuntu/cyris/CLAUDE.md` for usage instructions
- Configuration patterns used in module documentation
- Testing scenarios derived from example configurations

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Examples module documentation with comprehensive configuration template coverage
- **[TEMPLATES]** Documented YAML structure patterns and task configuration examples  
- **[GUIDANCE]** Outlined example selection and customization guidelines for different training scenarios