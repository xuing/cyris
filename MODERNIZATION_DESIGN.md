# CyRIS 现代化重构设计文档

## 当前架构分析

### 核心模块依赖关系
```
cyris.py (主入口)
├── entities.py (实体定义)
├── modules.py (功能模块)
├── clone_environment.py (VM克隆)
├── parse_config.py (配置解析)
├── check_description.py (描述验证)
├── aws_*.py (AWS支持)
└── range_cleanup.py (清理)
```

### 问题识别
1. **单一职责违反**: 类过于庞大，承担多种责任
2. **紧耦合**: 模块间直接依赖，难以测试
3. **缺乏接口抽象**: 没有明确的接口定义
4. **缺乏测试**: 无单元测试框架
5. **配置硬编码**: 路径和配置分散在代码中

## 现代化架构设计

### 1. 分层架构
```
┌─────────────────────────────────────┐
│            CLI Layer                │  # 命令行接口
├─────────────────────────────────────┤
│          Service Layer              │  # 业务逻辑服务
├─────────────────────────────────────┤
│         Domain Layer                │  # 领域模型和业务规则
├─────────────────────────────────────┤
│      Infrastructure Layer           │  # 基础设施（VM、网络、AWS）
└─────────────────────────────────────┘
```

### 2. 核心领域模块

#### A. 配置管理模块 (config/)
- `config_parser.py` - 配置解析接口
- `yaml_parser.py` - YAML描述文件解析
- `settings.py` - 系统设置管理
- `validator.py` - 配置验证

#### B. 基础设施模块 (infrastructure/)
- `providers/` - 虚拟化提供商抽象
  - `kvm_provider.py` - KVM虚拟化
  - `aws_provider.py` - AWS云服务
  - `base_provider.py` - 提供商接口
- `network/` - 网络管理
  - `bridge_manager.py` - 网络桥接
  - `firewall_manager.py` - 防火墙规则
- `storage/` - 存储管理

#### C. 领域模型模块 (domain/)
- `entities/` - 实体定义
  - `host.py` - 主机实体
  - `guest.py` - 虚拟机实体
  - `network.py` - 网络实体
  - `range.py` - 靶场实体
- `services/` - 领域服务
  - `range_builder.py` - 靶场构建服务
  - `clone_service.py` - 克隆服务
  - `deployment_service.py` - 部署服务

#### D. 应用服务模块 (services/)
- `orchestrator.py` - 编排服务
- `monitoring.py` - 监控服务
- `cleanup_service.py` - 清理服务

#### E. 工具模块 (tools/)
- `ssh_manager.py` - SSH管理
- `user_manager.py` - 用户管理
- `malware_simulator.py` - 恶意软件模拟
- `attack_simulator.py` - 攻击模拟

### 3. 新的接口设计

#### RESTful API接口
```python
# 新增现代化REST API
POST   /api/v1/ranges          # 创建靶场
GET    /api/v1/ranges/{id}     # 获取靶场详情
DELETE /api/v1/ranges/{id}     # 删除靶场
GET    /api/v1/ranges          # 列出所有靶场
POST   /api/v1/ranges/{id}/clone  # 克隆靶场
```

#### CLI接口保持向后兼容
```bash
# 保留原始接口
main/cyris.py examples/basic.yml CONFIG

# 新增现代化CLI
cyris create --config CONFIG --description examples/basic.yml
cyris list
cyris destroy --range-id 123
cyris status --range-id 123
```

### 4. 测试策略

#### 测试金字塔
```
┌─────────────────┐
│   E2E Tests     │  # 端到端测试
├─────────────────┤
│Integration Tests│  # 集成测试
├─────────────────┤
│  Unit Tests     │  # 单元测试（重点）
└─────────────────┘
```

#### 测试框架选择
- **单元测试**: pytest
- **模拟框架**: unittest.mock
- **测试覆盖率**: pytest-cov
- **集成测试**: testcontainers (Docker容器测试)

### 5. 部署现代化

#### 容器化部署
```yaml
# Docker Compose 部署
version: '3.8'
services:
  cyris-api:
    build: .
    ports:
      - "8000:8000"
  cyris-worker:
    build: .
    command: celery worker
```

#### 分步骤部署脚本
```bash
scripts/
├── 01-prepare-host.sh      # 主机准备
├── 02-install-deps.sh      # 依赖安装
├── 03-setup-network.sh     # 网络配置
├── 04-configure-kvm.sh     # KVM配置
├── 05-test-deployment.sh   # 部署测试
└── deploy.sh               # 主部署脚本
```

## 重构实施计划

### 第一阶段：测试框架建立
1. 创建测试结构
2. 为核心类编写单元测试
3. 建立CI/CD管道

### 第二阶段：领域模型重构
1. 提取实体类
2. 创建领域服务
3. 实现依赖注入

### 第三阶段：基础设施抽象
1. 创建提供商接口
2. 重构KVM和AWS模块
3. 网络和存储抽象

### 第四阶段：服务层重构
1. 编排服务实现
2. 监控和日志集成
3. 错误处理标准化

### 第五阶段：接口现代化
1. REST API实现
2. 新CLI工具
3. 向后兼容保证

## 技术选型

### 开发工具
- **依赖管理**: Poetry
- **代码质量**: Black, Flake8, mypy
- **文档**: Sphinx
- **监控**: Prometheus + Grafana
- **日志**: structlog

### 架构模式
- **依赖注入**: dependency-injector
- **事件驱动**: 领域事件模式
- **异步处理**: asyncio/Celery
- **配置管理**: Pydantic Settings