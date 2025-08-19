# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CyRIS (Cyber Range Instantiation System) 是一个用于网络安全培训的自动化工具，可以基于YAML描述文件创建和管理网络安全训练环境（网络靶场）。该系统支持KVM虚拟化和AWS云环境。

**重要更新**: 该项目已完成现代化改造，具有以下特性：
- ✅ 现代化Python架构（Pydantic、Click、pytest等）
- ✅ 完整的单元测试覆盖
- ✅ 分步骤部署脚本  
- ✅ 现代化CLI接口
- ✅ 向后兼容原始接口

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
```

## Architecture Overview

### 现代化架构

#### 新增现代化组件
- **src/cyris/config/** - 现代化配置管理
  - `settings.py` - Pydantic配置模型
  - `parser.py` - 配置解析器（支持YAML和传统INI）
- **src/cyris/domain/entities/** - 现代化领域实体
  - `host.py` - 主机实体和构建器
  - `guest.py` - 虚拟机实体和构建器
  - `base.py` - 实体基类
- **src/cyris/cli/** - 现代化CLI接口
  - `main.py` - Click-based命令行接口
- **scripts/** - 分步骤部署脚本
  - `deploy.py` - Python部署协调器
  - `setup/` - 主机和环境设置脚本
  - `validation/` - 部署验证脚本
- **tests/** - 完整测试套件
  - `unit/` - 单元测试
  - `integration/` - 集成测试（规划中）
  - `e2e/` - 端到端测试（规划中）

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