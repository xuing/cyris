# Services Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **services**

## Module Responsibilities

The Services module contains the core business logic layer of CyRIS, orchestrating cyber range lifecycle management, task execution, monitoring, and network services. This layer coordinates between the infrastructure providers and the CLI/API interfaces.

## Entry and Startup

- **Primary Entry**: `orchestrator.py` - Main range orchestration service
- **Task Execution**: `task_executor.py` - Task execution and verification service
- **Network Services**: `network_service.py` - Network topology and connectivity management
- **Gateway Services**: `gateway_service.py` - Entry point and tunneling management

### Service Architecture
```
services/
├── orchestrator.py        # Range lifecycle orchestration
├── task_executor.py       # YAML task execution engine  
├── monitoring.py          # Health monitoring and status
├── network_service.py     # Network topology management
├── gateway_service.py     # Entry point and tunnel management
├── cleanup_service.py     # Resource cleanup coordination
└── range_discovery.py     # Existing range discovery
```

## External Interfaces

### Orchestrator Service API
```python
class RangeOrchestrator:
    def create_range(self, config_path: Path, range_id: Optional[str]) -> RangeResult
    def destroy_range(self, range_id: str, force: bool = False) -> bool
    def get_range_status(self, range_id: str) -> RangeStatus
    def list_ranges(self) -> List[RangeInfo]
    def execute_tasks(self, range_id: str, tasks: List[Dict]) -> List[TaskResult]
```

### Task Executor API
```python
class TaskExecutor:
    def execute_task(self, vm_info: VMInfo, task: Dict) -> TaskResult
    def verify_task_result(self, vm_info: VMInfo, task_result: TaskResult) -> bool
    
# Supported Task Types:
# - add_account, modify_account
# - install_package, copy_content, execute_program  
# - emulate_attack, emulate_malware, emulate_traffic_capture_file
# - firewall_rules
```

### Network Service API
```python
class NetworkService:
    def create_topology(self, topology_config: Dict) -> NetworkTopology
    def assign_ips(self, guests: List[Guest]) -> Dict[str, str]
    def validate_connectivity(self, range_id: str) -> ConnectivityReport
```

### Gateway Service API  
```python
class GatewayService:
    def setup_entry_points(self, range_config: Dict) -> List[EntryPointInfo]
    def create_tunnels(self, gateway_config: Dict) -> TunnelManager
    def get_connection_info(self, range_id: str) -> Dict[str, ConnectionInfo]
```

## Key Dependencies and Configuration

### External Dependencies
```python
paramiko>=4.0      # SSH connections and task execution
boto3>=1.40        # AWS provider integration
psutil>=7.0        # System monitoring and resource management
structlog>=25.0    # Structured logging
pydantic>=2.11     # Configuration validation
```

### Internal Dependencies
- `infrastructure.providers` - VM provider abstractions (KVM, AWS)
- `infrastructure.network` - Network topology and bridge management
- `domain.entities` - Host/Guest entity models
- `config.settings` - Configuration management
- `tools.ssh_manager` - SSH connection management
- `tools.user_manager` - User and permission management
- `core.exceptions` - Structured error handling

### Service Configuration
```python
class ServiceConfig(BaseSettings):
    task_timeout: int = 300          # Task execution timeout
    ssh_retry_count: int = 3         # SSH connection retries
    health_check_interval: int = 30  # Monitoring interval
    cleanup_orphaned_resources: bool = True
    enable_gateway_mode: bool = False
```

## Data Models

### Range Management
```python
@dataclass
class RangeInfo:
    range_id: str
    status: RangeStatus
    created_at: datetime
    hosts: List[HostInfo]
    guests: List[GuestInfo]
    network_topology: Optional[NetworkTopology]

class RangeStatus(Enum):
    CREATING = "creating"
    ACTIVE = "active"
    FAILED = "failed"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
```

### Task Execution
```python
@dataclass 
class TaskResult:
    task_id: str
    task_type: TaskType
    vm_name: str
    vm_ip: str
    success: bool
    message: str
    evidence: Optional[str]  # Verification evidence
    execution_time: float
    timestamp: datetime
```

### Network Services
```python
@dataclass
class NetworkTopology:
    networks: List[NetworkInfo]
    ip_assignments: Dict[str, str]  # vm_name -> ip_address
    gateway_info: Optional[GatewayInfo]
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_orchestrator.py` - Orchestrator logic testing
- `/home/ubuntu/cyris/tests/unit/test_network_service.py` - Network service testing
- `/home/ubuntu/cyris/tests/unit/test_gateway_service.py` - Gateway service testing
- Mock infrastructure providers and external dependencies

### Integration Tests  
- `/home/ubuntu/cyris/tests/integration/test_services_integration.py` - Service interaction testing
- `/home/ubuntu/cyris/tests/integration/test_task_executor.py` - Task execution testing
- Use testcontainers for integration testing

### E2E Tests
- `/home/ubuntu/cyris/tests/e2e/test_full_deployment.py` - Complete deployment workflows
- `/home/ubuntu/cyris/tests/e2e/test_gw_mode_e2e.py` - Gateway mode testing
- Test with real VM creation and task execution

### Quality Requirements
- **Coverage Target**: 95% for orchestrator and task executor
- **Performance**: Task execution < 5 minutes, range creation < 15 minutes
- **Reliability**: Automatic retry for transient failures, graceful degradation

## Frequently Asked Questions (FAQ)

### Q: How does task execution verification work?
A: After executing each task (e.g., user creation), the system performs verification by checking the actual state (user exists, has correct permissions) and records evidence in the TaskResult.

### Q: What happens if a VM becomes unreachable during task execution?
A: The orchestrator uses progressive backoff retry with SSH health checking. If VM remains unreachable, it marks tasks as failed and provides detailed diagnostics.

### Q: How are network topologies synchronized with actual DHCP assignments?
A: The NetworkService discovers actual VM IPs and synchronizes them back to the topology metadata, maintaining a single source of truth in `ranges_metadata.json`.

### Q: Can I extend the system with custom task types?
A: Yes, implement new task types in `TaskExecutor` and add corresponding verification logic. The system uses enum-based task type registration.

### Q: How does gateway mode work for remote access?
A: Gateway mode creates SSH tunnels and entry points for accessing VMs from external networks, with proper authentication and access control.

## Related File List

### Core Services
- `/home/ubuntu/cyris/src/cyris/services/orchestrator.py` - Main range orchestration
- `/home/ubuntu/cyris/src/cyris/services/task_executor.py` - Task execution engine
- `/home/ubuntu/cyris/src/cyris/services/monitoring.py` - Health monitoring service
- `/home/ubuntu/cyris/src/cyris/services/network_service.py` - Network management
- `/home/ubuntu/cyris/src/cyris/services/gateway_service.py` - Gateway and tunneling
- `/home/ubuntu/cyris/src/cyris/services/cleanup_service.py` - Resource cleanup
- `/home/ubuntu/cyris/src/cyris/services/range_discovery.py` - Range discovery
- `/home/ubuntu/cyris/src/cyris/services/__init__.py` - Module exports

### Service Tests
- `/home/ubuntu/cyris/tests/unit/test_orchestrator.py` - Orchestrator unit tests
- `/home/ubuntu/cyris/tests/unit/test_network_service.py` - Network service tests
- `/home/ubuntu/cyris/tests/unit/test_gateway_service.py` - Gateway service tests
- `/home/ubuntu/cyris/tests/integration/test_services_integration.py` - Integration tests
- `/home/ubuntu/cyris/tests/integration/test_task_executor.py` - Task executor tests
- `/home/ubuntu/cyris/tests/e2e/test_gw_mode_e2e.py` - Gateway mode e2e tests

### Configuration
- `/home/ubuntu/cyris/cyber_range/ranges_metadata.json` - Range instance metadata
- `/home/ubuntu/cyris/cyber_range/ranges_resources.json` - Resource tracking

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Services module documentation with comprehensive API coverage
- **[ARCHITECTURE]** Documented service layer interactions and data flow patterns
- **[INTEGRATION]** Outlined testing strategy for service reliability and performance