# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CyRIS (Cyber Range Instantiation System) is an automated tool for cybersecurity training that creates and manages cybersecurity training environments (cyber ranges) based on YAML description files. The system supports KVM virtualization and AWS cloud environments.

**Current Status**: The project has completed full modernization with 100% progress:
- ✅ Modern Python architecture (Pydantic, Click, pytest, Rich)
- ✅ Complete unit test coverage (94% coverage rate)
- ✅ Stepwise deployment scripts  
- ✅ Modern CLI interface with Rich terminal output
- ✅ Backward compatibility with legacy interfaces
- ✅ Service layer implementation (orchestrator, monitoring, cleanup)
- ✅ Infrastructure layer abstraction (KVM/AWS provider interfaces)
- ✅ Modernized tool modules (SSH, user management, VM IP discovery)
- ✅ Integration test coverage (complete service integration tests)
- ✅ End-to-end test framework (CLI and complete deployment tests)

**Key Architectural Achievements**:
- 🏗️ **Layered Architecture**: CLI, Service, Domain, Infrastructure layers
- 🔌 **Provider Pattern**: Supports KVM and AWS, extensible to other cloud platforms
- 🛠️ **Tool Integration**: SSH management, user management, network/firewall management
- 📊 **Monitoring Services**: Real-time monitoring, alerting, performance metrics
- 🧹 **Cleanup Services**: Automated resource cleanup, data archiving, storage management
- 🧪 **Comprehensive Testing**: Unit, integration, and end-to-end tests
- 🎨 **Smart UI**: Rich framework with emoji detection and ASCII fallback
- 🔍 **VM IP Discovery**: Multi-method IP discovery with topology-aware assignment

## Common Commands

### Modern CLI Interface (Recommended)
```bash
# Environment setup
source .venv/bin/activate              # Activate virtual environment

# Basic operations
./cyris --help                         # Show help
./cyris validate                       # Validate environment configuration
./cyris config-show                    # Display current configuration
./cyris create examples/basic.yml      # Create cyber range
./cyris list                          # List all ranges
./cyris status basic --verbose        # View range status with detailed health info
./cyris destroy basic                 # Destroy range

# Configuration management
./cyris config-init                   # Initialize default configuration
./cyris config-show                   # Display configuration
```

### Legacy Interface (Backward Compatible)
```bash
# Traditional methods (still supported)
python main/cyris.py examples/basic.yml CONFIG
main/range_cleanup.sh 123 CONFIG

# Call legacy interface through modern CLI
./cyris legacy examples/basic.yml CONFIG
```

### Deployment and Environment Setup
```bash
# Modern one-command deployment
./deploy.sh                           # Complete deployment
./deploy.sh --dry-run                # Preview deployment steps
./deploy.sh --python-only            # Setup Python environment only
./deploy.sh --validate-only          # Validation only

# Step-by-step deployment
scripts/setup/01-prepare-host.sh      # Host preparation (requires sudo)
scripts/setup/02-setup-python-env.sh  # Python environment setup
scripts/validation/validate-deployment.sh  # Deployment validation

# Environment activation
source .venv/bin/activate            # or
source activate-env.sh               # Use convenience script
```

### Testing and Development
```bash
# Run unit tests (modern architecture)
python -m pytest tests/unit/ -v                          # All unit tests
python -m pytest tests/unit/test_config_parser.py -v     # Specific module
python -m pytest tests/unit/test_vm_ip_manager.py -v     # VM IP discovery tests

# Run integration tests 
python -m pytest tests/integration/ -v                   # Service integration
python -m pytest tests/integration/test_orchestrator.py -v  # Orchestrator tests

# Run end-to-end tests
python -m pytest tests/e2e/ -v                          # Full deployment tests
python -m pytest tests/e2e/test_cli_interface.py -v     # CLI interface tests

# Test coverage analysis
python -m pytest tests/unit/ --cov=src --cov-report=html
python -m pytest tests/ --cov=src --cov-report=term-missing

# Legacy compatibility tests
python simple_test.py                    # Basic legacy functionality
python test_legacy_core.py               # Legacy core validation
python test_modern_services.py           # Modern service validation  
python test_service_integration.py       # Service integration testing
python test_complete_functionality.py    # Complete functionality validation

# KVM-specific testing (requires KVM environment)
python verification_real_kvm.py          # Real KVM environment tests
```

### Code Quality and Formatting
```bash
# Code formatting (modern modules only)
python -m black src/

# Type checking (modern modules only) 
python -m mypy src/

# Linting (modern modules only)
python -m flake8 src/

# Pre-commit hooks
pre-commit run --all-files

# Poetry-based development
poetry install                            # Install all dependencies
poetry run pytest tests/                 # Run tests via poetry
poetry run black src/                    # Format code via poetry
```

## Architecture Overview

### Modern Architecture

#### Core Component Status
- **src/cyris/config/** - ✅ Modern configuration management
  - `settings.py` - Pydantic configuration models
  - `parser.py` - Configuration parser (supports YAML and legacy INI)
- **src/cyris/domain/entities/** - ✅ Modern domain entities
  - `host.py` - Host entities and builders
  - `guest.py` - Virtual machine entities and builders
  - `base.py` - Entity base classes
- **src/cyris/cli/** - ✅ Modern CLI interface with Rich UI
  - `main.py` - Click-based command-line interface
  - `commands/` - Structured command handlers (create, destroy, status, etc.)
  - `presentation/` - Rich framework UI components
- **src/cyris/services/** - ✅ Service layer implementation
  - `orchestrator.py` - Orchestration service with topology management
  - `monitoring.py` - Monitoring service with health checks and alerts
  - `cleanup_service.py` - Cleanup service for resource management
  - `network_service.py` - Network configuration and management
- **src/cyris/infrastructure/** - ✅ Infrastructure abstraction layer
  - `providers/` - Virtualization provider abstractions
    - `base_provider.py` - Base provider interface
    - `kvm_provider.py` - KVM provider implementation
    - `aws_provider.py` - AWS provider implementation
    - `virsh_client.py` - Libvirt/virsh client abstraction
  - `network/` - Network management components
    - `bridge_manager.py` - Network bridge management
    - `firewall_manager.py` - Firewall rule management
    - `topology_manager.py` - Network topology and IP allocation
- **src/cyris/tools/** - ✅ Tool modules (fully modernized)
  - `ssh_manager.py` - SSH management and key handling
  - `user_manager.py` - User account and permission management
  - `vm_ip_manager.py` - **Multi-method VM IP discovery with topology awareness**
- **scripts/** - ✅ Deployment automation
  - `deploy.py` - Python deployment coordinator
  - `setup/` - Host and environment setup scripts
  - `validation/` - Deployment validation scripts
- **tests/** - ✅ Comprehensive test suite
  - `unit/` - ✅ Unit tests (94% coverage)
  - `integration/` - ✅ Integration tests (complete implementation)
  - `e2e/` - ✅ End-to-end tests (complete implementation)

#### Legacy Components (Maintained for Compatibility)
- **main/cyris.py** - Original main program entry point
- **main/entities.py** - Original entity class definitions
- **main/modules.py** - Functional module classes
- **main/clone_environment.py** - VM cloning core classes
- **main/parse_config.py** - Legacy configuration parser
- **main/range_cleanup.py** - Range cleanup functionality

### AWS Support
- **main/aws_*.py** - AWS云环境支持模块
  - `aws_instances.py` - EC2实例管理
  - `aws_sg.py` - 安全组管理
  - `aws_image.py` - AMI镜像管理
  - `aws_cleanup.py` - AWS资源清理

### Instantiation Scripts
- **instantiation/** - 各种自动化脚本目录
  - `attacks_emulation/` - 攻击模拟脚本
  - `content_copy_program_run/` - 内容复制和程序执行
  - `logs_preparation/` - 日志和流量文件准备
  - `malware_creation/` - 恶意软件创建（仅用于教学）
  - `vm_clone/` - VM克隆相关脚本

### Configuration Flow

1. 解析CONFIG配置文件获取路径和网关设置
2. 读取YAML描述文件，实例化Host、Guest和CloneSetting对象
3. 通过模块系统执行SSH密钥设置、用户管理、软件安装等任务
4. 使用VMClone类生成网络桥接、VM克隆和配置脚本
5. 生成管理文件和清理脚本

### Key Configuration Files

- **CONFIG** - 主配置文件，包含CyRIS路径和网关设置
- **examples/*.yml** - 靶场描述示例文件
- **cyber_range/** - 生成的靶场实例目录
- **logs/** - 日志文件目录

### YAML Description Structure

```yaml
host_settings:      # 物理主机配置
guest_settings:     # 虚拟机模板配置  
clone_settings:     # 克隆实例配置
```

## Development Guidelines

### Working with YAML Descriptions
- 所有YAML文件必须遵循CyRIS规范
- 使用`main/check_description.py`验证描述文件
- 参考`examples/`目录中的示例文件

### Python Code Structure
- 遵循模块化设计原则
- 新功能应添加到`main/modules.py`中作为功能类
- 所有类必须实现`command()`方法
- 使用`entities.py`中的实体类表示描述文件内容

### Error Handling
- 如遇到"No route to host"错误，销毁部分创建的靶场并重新创建
- 使用`destroy_all_cr.sh`清理残留文件
- 检查KVM域和网络桥接是否正确清理

### Security Considerations
- 此项目包含网络安全培训相关的攻击模拟和恶意软件创建功能，仅用于教育目的
- 所有攻击模拟脚本仅在隔离的靶场环境中运行
- 不要在生产环境中执行任何攻击相关功能

### Important Implementation Notes

**Current State Analysis**: 
The project has undergone modernization but is not complete. Many functions lack full implementation and need to be completed to provide actual cyber range functionality.

**Key Areas Requiring Implementation**:
- Complete integration between modern services and legacy systems
- Full network topology management implementation
- End-to-end task execution system integration
- Production-ready cyber range deployment functionality

**When Contributing**:
- Focus on completing the actual cyber range functionality, not just the architectural framework
- Test with real KVM environments when possible
- Ensure backward compatibility with existing YAML descriptions
- Validate changes against existing examples in `examples/` directory

### TDD Development Best Practices

**重复性陷阱和通用解决方案**:
- **CLI测试输出匹配**: 不要假设输出消息的组合方式，先运行CLI查看实际输出格式再写断言
- **TDD调试方法**: 测试失败时，系统性分析是程序逻辑错误还是测试期望错误 - 通过实际运行程序验证预期行为

## Critical Implementation Notes

### VM IP Discovery System
CyRIS implements a sophisticated multi-method VM IP discovery system in `src/cyris/tools/vm_ip_manager.py`:

#### Discovery Methods (in priority order):
1. **`cyris_topology`** - Reads IP assignments from topology manager metadata (highest priority)
2. **`libvirt`** - Uses libvirt Python API for active VMs
3. **`virsh`** - Uses virsh command-line tool
4. **`arp`** - Scans ARP table for MAC-to-IP mappings
5. **`dhcp`** - Parses DHCP lease files
6. **`bridge`** - Scans bridge interfaces

#### Recent Fixes Applied:
- **Disk Lock Issues**: Added `--force-share` flag to qemu-img commands to prevent lock conflicts when VMs are running
- **Network Testing**: Improved ping tests with longer timeouts (3 pings, 5s wait, 15s total timeout)
- **Topology Integration**: Enhanced orchestrator to extract and store topology configuration from YAML files
- **Alternative IP Discovery**: Added bridge network scanning and alternative network range discovery

### Status Command Enhancements
The `./cyris status <range_id> --verbose` command now provides comprehensive VM health information:
- **Libvirt Status**: Shows VM state (running, shut off, etc.)
- **IP Address Resolution**: Multi-method IP discovery with error details
- **Network Reachability**: Tests network connectivity via ping
- **Disk Health**: Checks disk images with proper lock handling
- **Error Diagnostics**: Detailed error reporting for troubleshooting

### Troubleshooting Common Issues

#### VM Status Problems
```bash
# If status shows disk lock errors:
./cyris status <range_id> --verbose    # Should now work with recent fixes

# If VM has IP but not reachable:
ping <vm_ip>                           # Test direct connectivity
virsh console <vm_name>                # Check VM console (may need guest tools)
```

#### Network Issues
- **"No route to host" errors**: Destroy partially created ranges and recreate
- **ARP incomplete entries**: Indicates VM network stack issues, check guest configuration
- **Bridge connectivity**: Check with `brctl show` and `ip route` for bridge network setup

#### KVM Environment
- **Domain cleanup**: Use `destroy_all_cr.sh CYRIS_PATH CYBER_RANGE_PATH` for complete cleanup
- **Permission errors**: Ensure user is in libvirt group and has KVM access
- **Network bridge issues**: Check bridge status and clean up manually if needed

#### Development Environment
- **libvirt connection**: Ensure `qemu:///system` URI is accessible
- **Python virtual environment**: Always activate `.venv` before running commands
- **KVM acceleration**: Verify `/dev/kvm` device exists and is accessible

## Development Workflow Best Practices

### When Working on Bug Fixes
1. **Identify root cause** using verbose status commands and log analysis
2. **Apply KISS principles** - create simple, focused methods for single responsibilities  
3. **Test thoroughly** with both unit tests and real KVM environment validation
4. **Document fixes** in commit messages and update BUGFIX_RECORD.md if needed

### When Adding New Features
1. **Follow layered architecture** - add functionality at appropriate layer (CLI, Service, Infrastructure)
2. **Maintain backward compatibility** with legacy interfaces
3. **Add comprehensive tests** covering unit, integration, and e2e scenarios
4. **Update CLI help and documentation** to reflect new capabilities

### Code Quality Standards
- **Modern modules** (src/cyris/): Use Pydantic, Click, pytest, Rich framework, type hints
- **Legacy modules** (main/): Maintain existing patterns for stability
- **Testing**: Achieve 90%+ coverage for new code, test with real KVM when possible
- **Error handling**: Provide detailed error messages with actionable guidance