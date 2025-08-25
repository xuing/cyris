# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
use English to write code.

## Project Overview

CyRIS (Cyber Range Instantiation System) 是一个用于网络安全培训的自动化工具，可以基于YAML描述文件创建和管理网络安全训练环境（网络靶场）。该系统支持KVM虚拟化和AWS云环境。

**重要更新**: 该项目已完成现代化改造，当前进度100%：
- ✅ 现代化Python架构（Pydantic、Click、pytest等）
- ✅ 完整的单元测试覆盖（94%覆盖率）
- ✅ 分步骤部署脚本  
- ✅ 现代化CLI接口
- ✅ 向后兼容原始接口
- ✅ 服务层实现（完成 - orchestrator、monitoring、cleanup等）
- ✅ 基础设施层抽象（完成 - KVM/AWS提供商接口）
- ✅ 工具模块现代化（完成 - SSH、用户管理等）
- ✅ 集成测试扩展（完成 - 完整的服务集成测试）
- ✅ 端到端测试框架（完成 - CLI和完整部署测试）

**架构现代化成果**:
- 🏗️ **分层架构**: CLI层、服务层、领域层、基础设施层
- 🔌 **Provider模式**: 支持KVM和AWS，可扩展其他云平台
- 🛠️ **工具集成**: SSH管理、用户管理、网络管理、防火墙管理
- 📊 **监控服务**: 实时监控、告警、性能指标收集
- 🧹 **清理服务**: 自动化资源清理、数据归档、存储管理
- 🧪 **完整测试**: 单元测试、集成测试、端到端测试
- 🎨 **智能UI**: 自动emoji检测与ASCII回退，支持各种终端环境

## Common Commands

### 现代化CLI接口（推荐）
```bash
# 环境设置
source .venv/bin/activate              # 激活虚拟环境

# 基本操作
./cyris --help                         # 查看帮助
./cyris validate                       # 验证环境配置
./cyris config-show                    # 显示当前配置
./cyris create examples/basic.yml      # 创建网络靶场
./cyris list                          # 列出所有靶场
./cyris status 123                    # 查看靶场状态
./cyris destroy 123                   # 销毁靶场

# 配置管理
./cyris config-init                   # 初始化默认配置
./cyris config-show                   # 显示配置
```

### 传统接口（向后兼容）
```bash
# 传统方式（仍然支持）
python main/cyris.py examples/basic.yml CONFIG
main/range_cleanup.sh 123 CONFIG

# 通过现代CLI调用传统接口
./cyris legacy examples/basic.yml CONFIG
```

### 部署和环境设置
```bash
# 现代化一键部署
./deploy.sh                           # 完整部署
./deploy.sh --dry-run                # 查看部署步骤
./deploy.sh --python-only            # 仅设置Python环境
./deploy.sh --validate-only          # 仅验证环境

# 分步骤部署
scripts/setup/01-prepare-host.sh      # 主机准备（需sudo）
scripts/setup/02-setup-python-env.sh  # Python环境设置
scripts/validation/validate-deployment.sh  # 验证部署

# 环境激活
source .venv/bin/activate            # 或
source activate-env.sh               # 使用便捷脚本
```

### 测试和开发
```bash
# 运行现代化单元测试
python -m pytest tests/unit/test_config_parser.py -v
python -m pytest tests/unit/test_domain_entities.py -v

# 运行所有现代化测试
python -m pytest tests/unit/test_config_parser.py tests/unit/test_domain_entities.py -v

# 运行传统兼容性测试
python simple_test.py

# 测试覆盖率报告
python -m pytest tests/unit/ --cov=src --cov-report=html

# 运行集成测试
python -m pytest tests/integration/ -v

# 运行端到端测试  
python -m pytest tests/e2e/ -v

# 运行所有测试套件
python -m pytest tests/ -v

# 运行特定测试验证脚本
python test_legacy_core.py                    # 传统核心功能验证
python test_modern_services.py                # 现代服务验证  
python test_service_integration.py            # 服务集成测试
python test_complete_functionality.py         # 完整功能测试
```

### 代码质量和格式化
```bash
# 运行代码格式化 (仅针对现代化模块)
python -m black src/

# 运行类型检查 (仅针对现代化模块) 
python -m mypy src/

# 运行代码风格检查 (仅针对现代化模块)
python -m flake8 src/

# 运行预提交钩子
pre-commit run --all-files
```

## Architecture Overview

### 现代化架构

#### 现代化组件状态
- **src/cyris/config/** - ✅ 现代化配置管理（已完成）
  - `settings.py` - Pydantic配置模型
  - `parser.py` - 配置解析器（支持YAML和传统INI）
- **src/cyris/domain/entities/** - ✅ 现代化领域实体（已完成）
  - `host.py` - 主机实体和构建器
  - `guest.py` - 虚拟机实体和构建器
  - `base.py` - 实体基类
- **src/cyris/cli/** - ✅ 现代化CLI接口（已完成）
  - `main.py` - Click-based命令行接口
- **src/cyris/services/** - ✅ 服务层（已完成）
  - `orchestrator.py` - 编排服务（完整实现）
  - `monitoring.py` - 监控服务（完整实现）
  - `cleanup_service.py` - 清理服务（完整实现）
- **src/cyris/infrastructure/** - ✅ 基础设施层（已完成）
  - `providers/` - 虚拟化提供商抽象（完整实现）
    - `base_provider.py` - 基础接口
    - `kvm_provider.py` - KVM提供商
    - `aws_provider.py` - AWS提供商
  - `network/` - 网络管理（完整实现）
    - `bridge_manager.py` - 网桥管理
    - `firewall_manager.py` - 防火墙管理
- **src/cyris/tools/** - ✅ 工具模块（已完成）
  - `ssh_manager.py` - SSH管理和密钥管理
  - `user_manager.py` - 用户账户和权限管理
- **scripts/** - ✅ 分步骤部署脚本（已完成）
  - `deploy.py` - Python部署协调器
  - `setup/` - 主机和环境设置脚本
  - `validation/` - 部署验证脚本
- **tests/** - ✅ 测试套件（完整覆盖）
  - `unit/` - ✅ 单元测试（94%覆盖率）
  - `integration/` - ✅ 集成测试（完整实现）
  - `e2e/` - ✅ 端到端测试（完整实现）

#### 传统组件（保持兼容）
- **main/cyris.py** - 原始主程序入口
- **main/entities.py** - 原始实体类定义
- **main/modules.py** - 功能模块类
- **main/clone_environment.py** - VM克隆核心类
- **main/parse_config.py** - 传统配置解析器
- **main/range_cleanup.py** - 靶场清理功能

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

### Troubleshooting Common Issues
- "No route to host" errors: Destroy partially created ranges and recreate
- KVM domain cleanup: Use `destroy_all_cr.sh CYRIS_PATH CYBER_RANGE_PATH` for complete cleanup
- Network bridge issues: Check with `brctl show` and clean up manually if needed
- Permission errors: Ensure user is in libvirt group and has KVM access