# Tests Module

[Root Directory](../CLAUDE.md) > **tests**

## Module Responsibilities

The Tests module provides comprehensive test coverage for the CyRIS system, implementing a three-tier testing strategy: Unit Tests (isolated component testing), Integration Tests (service interaction testing), and End-to-End Tests (complete workflow validation). The module ensures system reliability, performance, and maintainability.

## Entry and Startup

- **Primary Entry**: `conftest.py` - Pytest configuration and shared fixtures
- **Test Runner**: `pytest` command with coverage reporting
- **Test Discovery**: Automatic discovery of `test_*.py` files
- **Coverage Reports**: HTML and terminal coverage reporting

### Test Architecture
```
tests/
├── conftest.py                    # Pytest fixtures and configuration
├── __init__.py                   # Test module initialization
├── unit/                         # Unit tests (isolated components)
│   ├── test_orchestrator.py      # Orchestrator logic testing
│   ├── test_cli_commands.py      # CLI command testing
│   ├── test_ssh_manager.py       # SSH manager testing
│   └── ...                       # Component-specific unit tests
├── integration/                  # Integration tests (service interactions)
│   ├── test_services_integration.py     # Service layer integration
│   ├── test_infrastructure_providers.py # Provider integration
│   └── test_network_topology.py         # Network integration
└── e2e/                          # End-to-end tests (complete workflows)
    ├── test_full_deployment.py   # Complete deployment workflows
    ├── test_cli_interface.py     # CLI workflow testing
    └── test_gw_mode_e2e.py      # Gateway mode testing
```

## External Interfaces

### Test Execution API
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only  
pytest tests/e2e/          # End-to-end tests only

# Run with coverage
pytest --cov=cyris --cov-report=html --cov-report=term-missing

# Run specific test files
pytest tests/unit/test_orchestrator.py -v

# Run tests matching pattern
pytest -k "test_ssh" -v
```

### Fixture API (conftest.py)
```python
@pytest.fixture
def temp_dir() -> Path
    # Temporary directory for test isolation

@pytest.fixture  
def sample_config() -> Dict
    # Standard test configuration

@pytest.fixture
def sample_yaml_description() -> Dict
    # Example YAML range description

@pytest.fixture
def mock_ssh_manager() -> Mock
    # Mocked SSH manager for unit tests

@pytest.fixture
def test_vm_provider() -> Mock
    # Mocked VM provider for integration tests
```

### Test Categories and Standards

#### Unit Tests (tests/unit/)
- **Scope**: Individual components in isolation
- **Dependencies**: Heavily mocked external dependencies
- **Performance**: < 1 second per test
- **Coverage Target**: 95% for critical components

#### Integration Tests (tests/integration/)  
- **Scope**: Service interactions and component integration
- **Dependencies**: Testcontainers or lightweight infrastructure
- **Performance**: < 30 seconds per test
- **Coverage Target**: 85% of integration paths

#### E2E Tests (tests/e2e/)
- **Scope**: Complete user workflows from CLI to VM deployment
- **Dependencies**: Real or simulated infrastructure  
- **Performance**: < 10 minutes per test
- **Coverage Target**: 100% of critical user journeys

## Key Dependencies and Configuration

### Testing Dependencies
```python
pytest>=8.0              # Test framework
pytest-cov>=6.0          # Coverage reporting
pytest-mock>=3.14        # Enhanced mocking capabilities
pytest-asyncio>=0.21     # Async test support
testcontainers>=3.7      # Infrastructure testing
```

### Mock Dependencies
- `unittest.mock` - Standard library mocking
- `pytest-mock` - Enhanced pytest mocking
- Custom mocks for infrastructure providers
- SSH connection mocking for reliability testing

### Test Configuration (pytest.ini / pyproject.toml)
```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --cov=cyris --cov-report=term-missing --cov-report=html"
testpaths = ["tests"]
pythonpath = ["src"]  
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Data Models

### Test Results and Reporting
```python
@dataclass
class TestExecutionResult:
    test_name: str
    status: TestStatus  # PASSED, FAILED, SKIPPED, ERROR
    duration: float
    error_message: Optional[str]
    coverage_percentage: float

class TestCategory(Enum):
    UNIT = "unit"
    INTEGRATION = "integration" 
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"
```

### Test Fixtures and Data
```python
@dataclass
class TestVMConfig:
    vm_name: str
    base_image: str
    network_config: Dict
    ssh_config: Dict
    expected_ip: Optional[str] = None

@dataclass
class TestRangeConfig:
    range_id: str
    hosts: List[TestHostConfig]
    guests: List[TestGuestConfig]
    network_topology: Dict
    tasks: List[Dict]
```

## Testing and Quality

### Test Coverage Requirements
- **Overall Coverage**: 85% minimum across all modules
- **Critical Components**: 95% coverage for orchestrator, CLI, infrastructure
- **New Code**: 90% coverage required for new features
- **Legacy Code**: Maintain existing coverage, improve incrementally

### Test Execution Strategy
```bash
# Fast feedback loop (unit tests)
pytest tests/unit/ --maxfail=1 -x

# Integration validation  
pytest tests/integration/ --tb=short

# Complete validation (CI pipeline)
pytest --cov=cyris --cov-report=html --junitxml=test-results.xml

# Performance baseline testing
pytest tests/e2e/ --durations=10
```

### Quality Gates
1. **All Tests Pass**: No failing unit or integration tests
2. **Coverage Threshold**: Meet minimum coverage requirements  
3. **Performance Regression**: E2E tests complete within time limits
4. **Code Quality**: No critical linting or type checking errors

### Test Data Management
- **Isolation**: Each test uses isolated temporary directories
- **Cleanup**: Automatic cleanup of test artifacts and VMs
- **Determinism**: Tests produce consistent results across environments
- **Parallelization**: Safe parallel execution for unit tests

## Frequently Asked Questions (FAQ)

### Q: How are real VMs used in testing without conflicts?
A: E2E tests use isolated test ranges with unique naming conventions (test-{timestamp}-{range_id}) and automatic cleanup to prevent conflicts.

### Q: What happens when infrastructure dependencies are unavailable?
A: Tests gracefully degrade using mocks and skip marks. Integration tests require testcontainers, E2E tests need real infrastructure.

### Q: How is SSH testing performed without real VMs?
A: Unit tests mock SSH connections. Integration tests use testcontainers with SSH servers. E2E tests use real VM deployment.

### Q: Can tests be run on developer machines safely?
A: Yes, unit and integration tests are safe. E2E tests require careful configuration to avoid conflicts with existing VMs.

### Q: How are test failures debugged effectively?
A: Tests capture detailed logs, VM states, and network configurations. Failed E2E tests preserve VMs for manual inspection with `--keep-failed` option.

### Q: What is the test execution time budget?
A: Unit tests: < 5 minutes total, Integration tests: < 15 minutes total, E2E tests: < 30 minutes total for full suite.

## Related File List

### Test Configuration
- `/home/ubuntu/cyris/tests/conftest.py` - Pytest fixtures and configuration
- `/home/ubuntu/cyris/tests/__init__.py` - Test module initialization  
- `/home/ubuntu/cyris/pyproject.toml` - Test configuration in project settings

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_orchestrator.py` - Orchestrator logic testing
- `/home/ubuntu/cyris/tests/unit/test_cli_commands.py` - CLI command testing
- `/home/ubuntu/cyris/tests/unit/test_ssh_manager.py` - SSH manager testing
- `/home/ubuntu/cyris/tests/unit/test_user_manager.py` - User management testing
- `/home/ubuntu/cyris/tests/unit/test_kvm_provider.py` - KVM provider testing
- `/home/ubuntu/cyris/tests/unit/test_network_service.py` - Network service testing
- `/home/ubuntu/cyris/tests/unit/test_exceptions.py` - Exception handling testing

### Integration Tests  
- `/home/ubuntu/cyris/tests/integration/test_services_integration.py` - Service interaction testing
- `/home/ubuntu/cyris/tests/integration/test_infrastructure_providers.py` - Provider integration testing
- `/home/ubuntu/cyris/tests/integration/test_network_topology.py` - Network topology testing
- `/home/ubuntu/cyris/tests/integration/test_task_executor.py` - Task execution testing

### E2E Tests
- `/home/ubuntu/cyris/tests/e2e/test_full_deployment.py` - Complete deployment workflows
- `/home/ubuntu/cyris/tests/e2e/test_cli_interface.py` - CLI workflow testing  
- `/home/ubuntu/cyris/tests/e2e/test_gw_mode_e2e.py` - Gateway mode testing
- `/home/ubuntu/cyris/tests/e2e/test_full_yml_support.py` - YAML configuration testing

### Legacy and Compatibility Tests
- `/home/ubuntu/cyris/tests/test_legacy_core.py` - Legacy system compatibility
- `/home/ubuntu/cyris/tests/test_modern_services.py` - Modern service validation
- `/home/ubuntu/cyris/tests/test_comprehensive_verification.py` - Comprehensive system validation

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created comprehensive Tests module documentation with three-tier testing strategy
- **[QUALITY]** Documented testing standards, coverage requirements, and quality gates
- **[INFRASTRUCTURE]** Outlined test execution strategy and debugging approaches for reliable testing