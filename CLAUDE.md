# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

项目命令要具有幂等性。参考docker-compose等知名项目的指导思想。

## Project Overview

**CyRIS (Cyber Range Instantiation System)** v1.4.0 automatically creates and manages cybersecurity training ranges from YAML descriptions. Supports **KVM/libvirt** and **AWS** cloud platforms.

**Core Design Principle**: Idempotent operations following Kubernetes/Terraform patterns:
- Declarative resource management with Range ID as unique identifier
- Resource lifecycle management: CREATE, CREATE_OR_UPDATE, RECREATE, SKIP_EXISTING
- Multi-layer reliability guarantees at Range/VM/Resource levels

## Architecture

Modern layered architecture with legacy compatibility:

### Modern Stack (src/cyris/)
- **CLI Layer**: Click-based interface with Rich UI (`src/cyris/cli/main.py`)
- **Services Layer**: Orchestration and monitoring (`src/cyris/services/orchestrator.py`)
- **Infrastructure Layer**: Provider abstractions (`src/cyris/infrastructure/providers/`)
- **Domain Layer**: Pydantic entities (`src/cyris/domain/entities/`)
- **Tools Layer**: SSH, user, VM utilities (`src/cyris/tools/`)
- **Configuration Layer**: Settings and YAML parsing (`src/cyris/config/`)
- **Core Layer**: Exceptions, logging, concurrency (`src/cyris/core/`)


### Legacy Compatibility
- **Legacy Main**: Original implementation (`legacy/main/cyris.py`)
- **Instantiation Scripts**: Attack emulation (`instantiation/`)

## Development Setup

### Environment Activation (Required)
```bash
# CRITICAL: Always activate virtual environment before any Python operations
source .venv/bin/activate

# Verify Python path points to virtual environment
which python3
# Should show: /home/ubuntu/cyris/.venv/bin/python3
```

### Dependency Management

The project uses **dual dependency management**:

#### Poetry (Preferred for Development)
```bash
# Install dependencies with Poetry
poetry install

# Add new dependency
poetry add <package_name>

# Add development dependency
poetry add --group dev <package_name>

# Update dependencies
poetry update

# Run commands in Poetry environment
poetry run pytest
poetry run black src/
```

#### Pip (Fallback/Production)
```bash
# Alternative: Install with pip (after activating .venv)
pip install -r requirements.txt

# Minimal installation
pip install -r requirements-minimal.txt
```

## Command Line Usage

### Unified Entry Script Routing

The `./cyris` script automatically routes between modern and legacy interfaces:

```bash
# Modern commands (routed to src/cyris/cli/main.py)
./cyris create examples/basic.yml
./cyris list --all --verbose
./cyris status <range_id> --verbose
./cyris destroy <range_id>
./cyris validate
./cyris --help

# Legacy commands (routed to legacy/main/cyris.py)  
./cyris examples/basic.yml CONFIG
./cyris <yaml_file> config.ini

# Direct legacy access
python legacy/main/cyris.py examples/basic.yml CONFIG
```

### CLI Debug Information

The unified entry script logs detailed debug information to `debug_main.log`:
- Command routing decisions (modern vs legacy)
- Python path modifications
- Import success/failure details
- Useful for troubleshooting CLI issues

### Modern CLI Operations

```bash
# Environment validation
./cyris validate

# Range lifecycle management
./cyris create examples/basic.yml --mode=create-only
./cyris create examples/basic.yml --mode=recreate
./cyris create examples/basic.yml --mode=skip-existing

# Status and monitoring
./cyris status <range_id> --verbose  # Shows IP, reachability, task summaries
./cyris list --all --verbose         # All ranges with details

# Configuration management
./cyris config-show
./cyris config-init
./cyris ssh-info <range_id>
```

## Testing Strategy

### Real Test Structure

Tests are organized in a mixed structure (not the idealized unit/integration/e2e folders):

```bash
# Root-level integration tests
test_kvm_auto_comprehensive.py    # Comprehensive KVM automation
test_fixed_cyris_workflow.py      # End-to-end workflow testing
test_sudo_workflow.py             # Sudo management testing
test_comprehensive_verification.py # Full system validation

# Organized test directory
tests/conftest.py                  # Shared fixtures
tests/unit/test_*.py              # Unit tests
tests/integration/                 # Service integration tests
tests/e2e/                        # End-to-end tests
tests/test_*.py                   # Mixed integration tests
```

### Test Execution

```bash
# Run all tests (requires activated .venv)
pytest

# Root-level integration tests (real infrastructure)
pytest test_kvm_auto_comprehensive.py -v
pytest test_fixed_cyris_workflow.py -v

# Organized test suites  
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v

# With coverage (configured in pyproject.toml)
pytest --cov=cyris --cov-report=html --cov-report=term-missing

# Run specific test patterns
pytest -k "test_ssh" -v
pytest -k "test_automation" -v

# Single test file with maximum verbosity
pytest tests/unit/test_entities.py -v -s
```

### Test Configuration

Coverage automatically excludes legacy code:
```toml
[tool.coverage.run]
omit = [
    "*/main/*",        # Legacy main code
    "*/instantiation/*", # Legacy scripts  
    "*/cleanup/*"      # Legacy cleanup
]
```

## Code Quality

### Formatting and Linting

```bash
# Black formatting (excludes legacy directories)
black src/ tests/

# Type checking with MyPy (legacy excluded)
mypy src/

# Flake8 linting
flake8 src/ tests/

# Pre-commit hooks (if configured)
pre-commit run --all-files
```

### Legacy Code Boundaries

**Modern Code** (format with Black, type-check with MyPy):
- `src/cyris/` - All modern architecture layers
- `tests/` - Test code

**Legacy Code** (maintain as-is, minimal changes):
- `legacy/main/` - Original implementation
- `instantiation/` - Attack emulation scripts
- `cleanup/` - Cleanup utilities

## Critical Implementation Areas

### 1. Task Orchestration (HIGH PRIORITY)
**Location**: `src/cyris/services/orchestrator.py`
- Connect YAML `tasks` to real VM execution
- Must include post-execution verification
- Results must be strongly typed (`TaskResult`)

### 2. SSH Key Management
**Location**: `src/cyris/tools/ssh_manager.py`
- Public key injection at VM creation (cloud-init)
- Unified retry/timeout strategy
- Configurable authentication (password vs key)

### 3. IP Address Synchronization
**Location**: `src/cyris/tools/vm_ip_manager.py`, `src/cyris/infrastructure/network/topology_manager.py`
- Exact VM name → IP mapping (no fuzzy matching)
- Priority: topology → libvirt → virsh → arp → dhcp → bridge
- Sync discovered IPs to `ranges_metadata.json`

### 4. CLI Status Accuracy
**Location**: `src/cyris/cli/commands/`
- `cyris status` must show real backend state
- Display VM state, IP, reachability, task summaries
- Provide actionable error messages

## YAML Configuration Contract

```yaml
host_settings:      # Physical host configuration
guest_settings:     # VM template definitions
clone_settings:     # Cloned instances with tasks
```

**Key Requirements**:
- Use modern field names (`gw_mgmt_addr`, `gw_account`)
- Merge tasks from `clone_settings` into guest objects
- Maintain stable guest identifiers (VM name → IP → results)
- Task results format: `{vm_name, vm_ip, task_id, task_type, success, message, evidence}`

## Entry Points and Key Files

### Primary Entry Points
- `/home/ubuntu/cyris/cyris` - Unified CLI with routing logic
- `/home/ubuntu/cyris/src/cyris/cli/main.py` - Modern CLI implementation
- `/home/ubuntu/cyris/legacy/main/cyris.py` - Legacy compatibility

### Configuration
- `/home/ubuntu/cyris/pyproject.toml` - Poetry configuration, test settings
- `/home/ubuntu/cyris/src/cyris/config/settings.py` - Modern configuration
- `/home/ubuntu/cyris/CONFIG` - Legacy configuration format

### Key Implementation Files
- `/home/ubuntu/cyris/src/cyris/services/orchestrator.py` - Core orchestration logic
- `/home/ubuntu/cyris/src/cyris/tools/ssh_manager.py` - SSH operations
- `/home/ubuntu/cyris/src/cyris/tools/vm_ip_manager.py` - IP discovery and management
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/base_provider.py` - Provider abstraction

## Security Notes

- Attack/emulation scripts are **for isolated training only**
- Never run attack scripts in production environments
- Cleanup scripts must fully remove domains, bridges, and disks
- SSH keys must be properly managed and rotated

## Common Development Tasks

### Adding a New CLI Command
1. Add command in `src/cyris/cli/commands/`
2. Register in `src/cyris/cli/main.py`
3. Add tests in `tests/unit/test_cli_commands.py`
4. Update help documentation

### Adding a New Provider
1. Implement in `src/cyris/infrastructure/providers/`
2. Inherit from `base_provider.BaseProvider`
3. Add provider tests in `tests/integration/`
4. Register provider in configuration

### Running End-to-End Tests
1. Ensure libvirt/KVM is properly configured
2. Run: `pytest test_kvm_auto_comprehensive.py -v -s`
3. Check `debug_main.log` for routing issues
4. Verify VMs are properly cleaned up after tests

### Debugging CLI Issues
1. Check `debug_main.log` for entry script routing
2. Verify virtual environment activation
3. Test direct CLI import: `python -c "from cyris.cli.main import main; main()"`
4. Check Poetry environment: `poetry run ./cyris --help`

---

**Note**: Always ensure `.venv` is activated before running any Python operations. The project requires specific dependency versions and path configurations that are managed by the virtual environment.