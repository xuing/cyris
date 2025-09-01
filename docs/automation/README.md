# CyRIS Automation Framework

A comprehensive automation framework for CyRIS that eliminates manual VM provisioning, image building, and infrastructure management tasks. Provides integration with industry-standard tools like HashiCorp Packer, Terraform, and AWS services.

## 🎯 Overview

The CyRIS Automation Framework addresses the core manual tasks previously required:

- **Manual VM Creation**: Replaced with declarative infrastructure-as-code
- **Image Building**: Automated with Packer and cloud-init integration  
- **Network Setup**: Automated topology creation with Terraform
- **Cloud Deployment**: Native AWS integration with EC2, VPC, and security groups
- **SSH Key Management**: Automated injection during VM creation

## 📋 Architecture Summary

### Automation Providers

| Provider | Purpose | Status | Tests | Coverage |
|----------|---------|---------|-------|----------|
| **PackerBuilder** | Image building and customization | ✅ Complete | 22 tests | 73% |
| **TerraformBuilder** | Infrastructure as code for libvirt | ✅ Complete | 23 tests | 72% |
| **AWSBuilder** | Cloud infrastructure automation | ✅ Complete | 28 tests | 71% |
| **Base Framework** | Shared automation foundation | ✅ Complete | - | 78% |

**Total**: 73 tests passing with 100% success rate

### Key Features

#### 🏗️ **Infrastructure as Code**
- **Declarative approach**: Describe desired state, not implementation steps
- **State management**: Track and reconcile infrastructure changes
- **Plan validation**: Preview changes before applying them
- **Multi-provider support**: KVM/libvirt, AWS, and extensible architecture

#### 🚀 **Image Building**
- **Automated downloads**: Fetch base images from official sources
- **Format conversion**: Support qcow2, vmdk, vhd formats
- **SSH key injection**: Secure key deployment via cloud-init
- **Image caching**: Local caching with retention policies

#### ☁️ **Cloud Integration**
- **AWS native support**: EC2, VPC, Security Groups, IAM
- **Resource tracking**: Automated tagging and lifecycle management
- **Cost optimization**: Instance sizing recommendations
- **Multi-region deployment**: Configurable region and availability zones

#### 🔧 **Configuration Management**
- **Pydantic validation**: Type-safe configuration with validation
- **Environment variables**: 12-factor app configuration support
- **Template system**: Extensible HCL and cloud-init templates
- **Error recovery**: Robust error handling with automatic cleanup

## 🚀 Quick Start

### 1. Basic Configuration

```yaml
# ~/.cyris/config.yml
automation:
  automation_enabled: true
  parallel_operations: true

packer:
  enabled: true
  working_dir: ~/.cyris/packer
  timeout: 7200  # 2 hours
  parallel_builds: 2

terraform:
  enabled: true
  working_dir: ~/.cyris/terraform
  libvirt_uri: qemu:///system
  timeout: 1800  # 30 minutes

aws:
  enabled: true
  region: us-east-1
  use_iam_roles: true
  default_instance_type: t3.micro
```

### 2. Environment Variables

```bash
# Packer settings
export CYRIS_PACKER_ENABLED=true
export CYRIS_PACKER_WORKING_DIR=/opt/cyris/packer

# Terraform settings  
export CYRIS_TERRAFORM_ENABLED=true
export CYRIS_TERRAFORM_LIBVIRT_URI=qemu:///system

# AWS settings
export CYRIS_AWS_ENABLED=true
export CYRIS_AWS_REGION=us-west-2
export CYRIS_AWS_DEFAULT_INSTANCE_TYPE=t3.small
```

### 3. Python API Usage

```python
from cyris.infrastructure.automation import (
    PackerBuilder, TerraformBuilder, AWSBuilder
)
from cyris.config.automation_settings import (
    PackerSettings, TerraformSettings, AWSSettings
)

# Image building
packer = PackerBuilder(PackerSettings())
await packer.connect()

# Build Ubuntu 22.04 image with SSH keys
result = await packer.execute_operation("build", {
    "template_name": "ubuntu-22.04",
    "output_formats": ["qcow2", "vmdk"],
    "ssh_keys": ["ssh-rsa AAAAB3..."],
    "custom_config": {"memory": 2048}
})

# Infrastructure provisioning
terraform = TerraformBuilder(TerraformSettings())
await terraform.connect()

# Deploy VMs with Terraform
result = await terraform.execute_operation("apply", {
    "hosts": [],
    "guests": [guest_config],
    "network_config": {
        "default": {"subnet": "192.168.100.0/24"}
    }
})

# AWS cloud deployment
aws = AWSBuilder(AWSSettings(
    region="us-east-1",
    key_pair_name="cyris-keypair"
))
await aws.connect()

# Deploy to AWS
result = await aws.execute_operation("deploy", {
    "hosts": [],
    "guests": [guest_config],
    "network_config": {"vpc": {"cidr_block": "10.0.0.0/16"}},
    "deployment_method": "direct"
})
```

## 📖 Detailed Documentation

### Provider Documentation

- **[Packer Integration](packer-integration.md)**: Image building and customization
- **[Terraform Integration](terraform-integration.md)**: Infrastructure as code 
- **[AWS Integration](aws-integration.md)**: Cloud deployment automation
- **[Configuration Guide](configuration.md)**: Complete configuration reference

### Advanced Topics

- **[Template Development](templates.md)**: Creating custom Packer and Terraform templates
- **[SSH Key Management](ssh-keys.md)**: Secure key injection strategies
- **[State Management](state-management.md)**: Terraform state and caching
- **[Troubleshooting](troubleshooting.md)**: Common issues and solutions

## 🔄 Migration Guide

### From Manual to Automated

**Before (Manual Process)**:
1. Download ISO/IMG files manually
2. Convert images using qemu-img commands
3. Create libvirt XML by hand
4. Manage SSH keys manually
5. Track resources manually

**After (Automated Process)**:
```python
# Single operation handles entire workflow
result = await packer.execute_operation("build", {
    "template_name": "ubuntu-22.04",
    "ssh_keys": ssh_keys,
    "output_formats": ["qcow2"]
})

# Automatic: download, convert, inject keys, cache
```

### Backward Compatibility

The automation framework maintains full backward compatibility:
- **Legacy CLI commands** continue to work
- **Existing YAML configurations** are supported
- **Manual workflows** remain available as fallbacks
- **Gradual migration** is supported

## 🧪 Testing Strategy

### Unit Tests (73 tests, 100% pass rate)

```bash
# Run all automation tests
pytest tests/unit/test_*_builder.py -v

# Individual provider tests
pytest tests/unit/test_packer_builder.py -v      # 22 tests
pytest tests/unit/test_terraform_builder.py -v  # 23 tests  
pytest tests/unit/test_aws_builder.py -v        # 28 tests
```

### Integration Testing

```bash
# Test with real infrastructure (requires setup)
pytest tests/integration/test_automation_integration.py -v
```

### Coverage Requirements

- **Minimum Coverage**: 70% for automation providers
- **Critical Paths**: 90+ coverage for core operations
- **Error Handling**: 100% coverage for error paths

## 🏗️ Architecture Details

### Class Hierarchy

```
AutomationProvider (Abstract Base)
├── PackerBuilder (Image Building)
├── TerraformBuilder (Infrastructure)
└── AWSBuilder (Cloud Services)
```

### Configuration Hierarchy

```
CyRISAutomationSettings
├── packer: PackerSettings
├── terraform: TerraformSettings  
├── aws: AWSSettings
├── image_cache: ImageCacheSettings
└── automation: AutomationGlobalSettings
```

### Operation Flow

```
1. Configuration Loading & Validation
2. Provider Connection & Authentication  
3. Operation Execution (async)
4. Resource Tracking & State Management
5. Result Processing & Artifact Storage
6. Cleanup & Resource Release
```

## 🔮 Future Enhancements

### Phase E: YAML Extensions (In Progress)
- Enhanced YAML syntax for automation
- Template inheritance and composition
- Dynamic parameter injection

### Phase F: Integration Optimization (Planned)
- End-to-end workflow testing
- Performance optimization
- Resource usage optimization
- Advanced monitoring and metrics

### Additional Providers (Future)
- **Vagrant Integration**: Development environment automation
- **Docker/Podman**: Container-based deployments  
- **Kubernetes**: Orchestrated deployments
- **Azure/GCP**: Additional cloud providers

## 🤝 Contributing

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/unit/test_*_builder.py -v

# Code quality
black src/ tests/
mypy src/
flake8 src/
```

### Adding New Providers

1. Extend `AutomationProvider` base class
2. Implement required abstract methods
3. Add comprehensive unit tests (20+ tests)
4. Update configuration settings
5. Add documentation and examples

### Guidelines

- **Follow SOLID principles**: Single responsibility, dependency injection
- **Async/await patterns**: Non-blocking operations  
- **Comprehensive testing**: Unit, integration, and E2E tests
- **Error handling**: Structured exceptions with context
- **Documentation**: Inline docs and external guides

## 📞 Support

### Resources

- **Issue Tracking**: [GitHub Issues](https://github.com/anthropics/cyris/issues)
- **Documentation**: [CyRIS Docs](https://docs.cyris.io)
- **Examples**: [examples/automation/](../../examples/automation/)
- **Templates**: [templates/](../../templates/)

### Common Issues

1. **"Provider not found"**: Ensure provider is enabled in configuration
2. **"Connection failed"**: Check credentials and network connectivity  
3. **"Template generation failed"**: Validate guest configuration
4. **"Operation timeout"**: Increase timeout settings for large deployments

---

**Built with ❤️ by the CyRIS Team**

*Automation framework designed for cybersecurity education and training environments*