# CLAUDE.md

Guidance for Claude Code when working with this repository.

项目命令要具有幂等性。参考docker-compose等知名项目的指导思想。
     │ 核心设计原则 (参考Kubernetes/Terraform)                                                                │
     │                                                                                                        │
     │ 1. 声明式资源管理                                                                                      │
     │                                                                                                        │
     │ 设计思路: 用户描述"想要什么"，系统确保"达到目标状态"                                                   │
     │ - Range ID作为唯一标识符                                                                               │
     │ - 配置哈希作为版本指纹                                                                                 │
     │ - 状态比较和差量更新                                                                                   │
     │                                                                                                        │
     │ 2. 资源生命周期管理                                                                                    │
     │                                                                                                        │
     │ 借鉴Docker/K8s模式:                                                                                    │
     │ - CREATE: 仅创建新资源，存在则报错                                                                     │
     │ - CREATE_OR_UPDATE: 创建或更新到目标状态 (默认)                                                        │
     │ - RECREATE: 强制删除重建                                                                               │
     │ - SKIP_EXISTING: 跳过已存在资源                                                                        │
     │                                                                                                        │
     │ 3. 分层幂等性保证                                                                                      │
     │                                                                                                        │
     │ Level 1 - Range级别: Range ID + 配置fingerprint                                                        │
     │ Level 2 - VM级别: VM name + 镜像checksumLevel 3 - 资源级别: 网络/存储的状态检查                        │
     │                                                                                                        │
     │ 具体实现方案                                                                                           │
     │                                                                                                        │
     │ A. CLI参数扩展                                                                                         │
     │                                                                                                        │
     │ # 默认模式：智能创建或更新                                                                             │
     │ ./cyris create config.yml                                                                              │
     │                                                                                                        │
     │ # 严格模式：仅创建新的，存在则失败                                                                     │
     │ ./cyris create config.yml --mode=create-only                                                           │
     │                                                                                                        │
     │ # 强制模式：删除重建                                                                                   │
     │ ./cyris create config.yml --mode=recreate                                                              │
     │                                                                                                        │
     │ # 跳过模式：保留现有资源                                                                               │
     │ ./cyris create config.yml --mode=skip-existing
## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Updated CLAUDE.md with comprehensive module structure and navigation
- **[ARCHITECTURE]** Added Mermaid module structure diagram for improved project visualization
- **[DOCUMENTATION]** Enhanced module index with detailed responsibility mapping and coverage status

---

## Project Vision

**CyRIS (Cyber Range Instantiation System)** automatically creates and manages cybersecurity training ranges from YAML descriptions. Supports **KVM** and **AWS**.

**Goal:** Reproducible pipeline from **YAML → Resource Creation → Task Execution → Verification**.

**Mission:** Enable cybersecurity education through automated, scalable, and reliable training environment deployment.

---

## Architecture Overview

CyRIS follows a modern layered architecture with legacy compatibility:

### Modern Architecture (Preferred)
- **CLI Layer**: Click-based command interface with Rich UI
- **Services Layer**: Business logic orchestration, monitoring, gateway services
- **Domain Layer**: Core business entities and data models
- **Infrastructure Layer**: Provider abstractions, network management, virtualization
- **Tools Layer**: SSH management, user management, VM utilities
- **Configuration Layer**: Pydantic-based settings and YAML parsing

### Legacy Compatibility Layer
- **Legacy Main**: Original implementation for backward compatibility
- **Instantiation Scripts**: Attack emulation and deployment scripts

### **🤖 NEW: Automation Framework** 
- **Packer Integration**: Automated VM image building and customization (22 tests ✅)
- **Terraform Integration**: Infrastructure-as-code for libvirt (23 tests ✅)  
- **AWS Integration**: Cloud deployment automation (28 tests ✅)
- **Total Coverage**: 73 tests, 100% pass rate, eliminates manual VM provisioning

---

## Module Structure Diagram

```mermaid
graph TD
    A["(Root) CyRIS"] --> B["src/cyris/"];
    B --> C["cli"];
    B --> D["services"];  
    B --> E["infrastructure"];
    B --> F["domain"];
    B --> G["config"];
    B --> H["tools"];
    B --> I["core"];
    
    A --> J["legacy"];
    J --> K["main"];
    
    A --> L["instantiation"];
    A --> M["tests"];
    A --> N["examples"];
    A --> O["docs"];

    click C "/home/ubuntu/cyris/src/cyris/cli/CLAUDE.md" "View CLI module docs"
    click D "/home/ubuntu/cyris/src/cyris/services/CLAUDE.md" "View Services module docs"  
    click E "/home/ubuntu/cyris/src/cyris/infrastructure/CLAUDE.md" "View Infrastructure module docs"
    click F "/home/ubuntu/cyris/src/cyris/domain/CLAUDE.md" "View Domain module docs"
    click G "/home/ubuntu/cyris/src/cyris/config/CLAUDE.md" "View Config module docs"
    click H "/home/ubuntu/cyris/src/cyris/tools/CLAUDE.md" "View Tools module docs"
    click I "/home/ubuntu/cyris/src/cyris/core/CLAUDE.md" "View Core module docs"
    click K "/home/ubuntu/cyris/legacy/main/CLAUDE.md" "View Legacy Main module docs"
    click L "/home/ubuntu/cyris/instantiation/CLAUDE.md" "View Instantiation module docs"
    click M "/home/ubuntu/cyris/tests/CLAUDE.md" "View Tests module docs"
```

---

## Module Index

| Module | Type | Responsibility | Entry Points | Status | Coverage |
|--------|------|----------------|--------------|---------|----------|
| **[src/cyris/cli](src/cyris/cli/CLAUDE.md)** | Modern CLI | Click-based command-line interface with Rich UI | `main.py` | ✅ Active | Complete |
| **[src/cyris/services](src/cyris/services/CLAUDE.md)** | Core Services | Business logic orchestration, range management | `orchestrator.py` | ✅ Active | Complete |
| **[src/cyris/infrastructure](src/cyris/infrastructure/CLAUDE.md)** | Infrastructure | Provider abstractions, network management | `providers/base_provider.py` | ✅ Active | Complete |
| **[src/cyris/infrastructure/automation](docs/automation/README.md)** | 🤖 Automation | Packer, Terraform, AWS automation | `packer_builder.py` | 🚀 **NEW** | 73 Tests ✅ |
| **[src/cyris/domain](src/cyris/domain/CLAUDE.md)** | Domain Entities | Core business entities and data models | `entities/__init__.py` | ✅ Active | Complete |
| **[src/cyris/config](src/cyris/config/CLAUDE.md)** | Configuration | Pydantic settings, YAML parsing | `settings.py` | ✅ Active | Complete |
| **[src/cyris/tools](src/cyris/tools/CLAUDE.md)** | Utility Tools | SSH, user management, VM utilities | `ssh_manager.py` | ✅ Active | Complete |
| **[src/cyris/core](src/cyris/core/CLAUDE.md)** | Core Utilities | Concurrency, reliability, exceptions | `exceptions.py` | ✅ Active | Complete |
| **[legacy/main](legacy/main/CLAUDE.md)** | Legacy Core | Original implementation, compatibility | `cyris.py` | 🔄 Legacy | Partial |
| **[instantiation](instantiation/CLAUDE.md)** | Legacy Scripts | Attack emulation, deployment scripts | `vm_clone/` | 🔄 Legacy | Basic |
| **[tests](tests/CLAUDE.md)** | Test Suite | Unit, integration, e2e testing | `conftest.py` | ✅ Active | Complete |
| **[examples](examples/CLAUDE.md)** | Examples | YAML configuration templates | `basic.yml` | 📖 Reference | Complete |
| **[docs](docs/CLAUDE.md)** | Documentation | Architecture docs, guides | `design/` | 📖 Reference | Partial |

---

## Running and Development

### Environment Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
./cyris validate
```

### Basic Usage
```bash
# Create cyber range
./cyris create examples/basic.yml

# Check status
./cyris status basic --verbose

# List all ranges
./cyris list --all --verbose

# Destroy range
./cyris destroy basic

# Legacy compatibility
./cyris legacy examples/basic.yml CONFIG
```

### Development Commands
```bash
# Run tests
pytest

# Run specific test suites
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Code formatting
black src/ tests/

# Type checking
mypy src/
```

---

## Testing Strategy

### Test Architecture
- **Unit Tests**: Individual component testing with mocking
- **Integration Tests**: Service interaction testing
- **E2E Tests**: Full workflow testing with real VMs
- **Legacy Tests**: Compatibility and regression testing

### Test Coverage Requirements
- **Minimum Coverage**: 80% for new code
- **Critical Paths**: 95% for orchestrator, CLI commands, infrastructure
- **Mock Strategy**: Use testcontainers for integration, real VMs for e2e

### Testing Guidelines
- Always **observe real CLI output** before writing assertions
- Each test must cover: **pre-check → execution → verification**
- Keep failure evidence in CI logs (command output, grep results, etc.)

---

## Coding Standards

### Python Style
- **Formatter**: Black (line length 88)
- **Linter**: Flake8 + MyPy for type checking
- **Import Style**: Absolute imports preferred
- **Docstrings**: Google style for public APIs

### Architecture Principles
- **Separation of Concerns**: Clear layer boundaries
- **Dependency Injection**: Use settings and configuration objects
- **Error Handling**: Structured exceptions with context
- **Logging**: Structured logging with structlog

### Code Organization
- **Modern Code**: Follow layered architecture in `src/cyris/`
- **Legacy Code**: Maintain stability, avoid modifications unless critical
- **Tests**: Mirror source structure in `tests/`

---

## AI Usage Guidelines

### Current Status — Key Gaps

1. **Task Orchestration (CRITICAL)**
   - Connect YAML `tasks` to real VM execution (e.g., user creation must actually happen)
   - Must include **post-execution verification** to avoid false positives

2. **SSH Key Injection / Authentication (HIGH)**
   - Public keys must be injected at VM creation (cloud-init)
   - Unified, configurable default credentials (password vs. key). No hardcoding

3. **IP Address Sync (MEDIUM)**
   - Align topology-assigned IPs and DHCP-assigned real IPs
   - Use **exact VM name → IP mapping** (no fuzzy matches across ranges)

4. **CLI Status Accuracy (LOW)**
   - `cyris status` output must match backend discovery (IP / reachability / health)

5. **End-to-End Verification Loop**
   - Complete: **Create → Configure → Execute Tasks → Verify** with observable structured results

### Where to Work — Code Map

- **Service / Orchestration**: `src/cyris/services/orchestrator.py` - task dispatch, VM targeting, readiness, results
- **Tools**: `ssh_manager.py`, `user_manager.py`, `vm_ip_manager.py` - SSH auth, user/permission tasks, IP discovery
- **Infrastructure / Network**: `topology_manager.py` - IP assignment + reconciliation
- **CLI**: Commands + Rich UI - ensure `status` reflects backend truth

### Implementation Requirements

1. **Precise VM Targeting**
   - Store VM name → real IP mapping; no substring matching
   - Write back discovered IPs to metadata (single source of truth)

2. **SSH & Keys**
   - Inject public key at creation
   - Configurable auth (password or key)
   - Unified retry/timeout strategy; detailed failure messages

3. **Task Execution & Verification**
   - Always validate after execution (exit code + evidence)
   - Results must be **strongly typed** (`TaskResult`) with consistent access

4. **CLI & Observability**
   - `status` must show VM state, IP, reachability, and task summaries
   - On errors, provide actionable next steps (e.g., bridge check, key injection)

5. **Consistency & Recovery**
   - If DHCP vs. topology mismatch: trust discovered IP, sync back
   - Provide safe cleanup/destroy for partial failures

### YAML Description — Contract

```yaml
host_settings:      # physical host
guest_settings:     # VM template  
clone_settings:     # cloned instances (hosts/guests/tasks)
```

**Guidelines:**
- Use modern field names (e.g., `gw_mgmt_addr`, `gw_account`)
- Merge tasks from `clone_settings` into guest objects before execution
- Maintain **stable guest identifiers** (VM name → IP → results)
- `task_results` must include: `{vm_name, vm_ip, task_id, task_type, success, message, evidence}`

### VM IP Discovery — Keep

Priority order: `topology → libvirt → virsh → arp → dhcp → bridge`

- Must output a **single authoritative IP**
- Sync to `ranges_metadata.json`
- Provide diagnostics (method used, timestamp, confidence)

### Security Notes

- Attack/emulation scripts are **for isolated training only**, never run in production
- Cleanup scripts must ensure domains, bridges, and disks are fully removed

---

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Updated CLAUDE.md with comprehensive module structure and navigation
- **[ARCHITECTURE]** Added Mermaid module structure diagram for improved project visualization  
- **[DOCUMENTATION]** Enhanced module index with detailed responsibility mapping and coverage status