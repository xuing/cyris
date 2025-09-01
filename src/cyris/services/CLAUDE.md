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
    def create_range(
        self,
        range_id: str,
        name: str,
        description: str,
        hosts: List[Host],
        guests: List[Guest],
        topology_config: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> RangeMetadata
    
    def get_range(self, range_id: str) -> Optional[RangeMetadata]
    def list_ranges(
        self,
        owner: Optional[str] = None,
        status: Optional[RangeStatus] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[RangeMetadata]
    
    def update_range_status(self, range_id: str) -> Optional[RangeStatus]
    def destroy_range(self, range_id: str) -> bool
    def remove_range(self, range_id: str, force: bool = False) -> bool
    
    def create_range_from_yaml(
        self,
        description_file: Path,
        range_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Optional[str]
    
    def create_range_from_yaml_enhanced(
        self,
        yaml_config_path: str,
        range_id: Optional[str] = None
    ) -> RangeMetadata
    
    def get_range_status_detailed(self, range_id: str) -> Optional[Dict[str, Any]]
    def get_range_resources(self, range_id: str) -> Optional[Dict[str, List[str]]]
    def get_statistics(self) -> Dict[str, Any]
```

### Task Executor API
```python
class TaskExecutor:
    def execute_guest_tasks(
        self, 
        guest: Any, 
        guest_ip: str,
        tasks: List[Dict[str, Any]]
    ) -> List[TaskResult]
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]

class TaskType(Enum):
    ADD_ACCOUNT = "add_account"
    MODIFY_ACCOUNT = "modify_account"
    INSTALL_PACKAGE = "install_package" 
    COPY_CONTENT = "copy_content"
    EXECUTE_PROGRAM = "execute_program"
    EMULATE_ATTACK = "emulate_attack"
    EMULATE_MALWARE = "emulate_malware"
    EMULATE_TRAFFIC_CAPTURE = "emulate_traffic_capture_file"
    FIREWALL_RULES = "firewall_rules"
```

### Network Service API
```python
class NetworkService:
    def validate_network_configuration(self, config: Dict[str, Any]) -> NetworkValidationResult
    def test_ssh_connectivity(
        self, 
        hostname: str, 
        port: int = 22, 
        timeout: float = 5.0
    ) -> NetworkTestResult
    def create_ssh_connection(
        self,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        timeout: float = 30.0
    ) -> bool
    def get_ssh_connection(self, hostname: str) -> Optional[Any]
    def check_ssh_health(self, hostname: str) -> bool
    def cleanup_ssh_connections(self) -> None
    def get_network_statistics(self) -> Dict[str, Any]
```

### Gateway Service API  
```python
@dataclass
class EntryPointInfo:
    range_id: int
    instance_id: int
    guest_id: str
    port: int
    target_host: str
    target_port: int
    account: str
    password: str
    tunnel_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

class GatewayService:
    def validate_gateway_settings(self) -> None
    def create_entry_point(
        self, 
        entry_point: EntryPointInfo, 
        local_user: str, 
        host_address: str
    ) -> Dict[str, Any]
    def destroy_entry_point(self, range_id: int, instance_id: int) -> None
    def get_entry_points_for_range(self, range_id: int) -> List[EntryPointInfo]
    def generate_access_notification(self, range_id: int) -> str
    def generate_random_credentials(self, length: int = 12) -> str
    def get_available_port(self, start_port: int = 60000, end_port: int = 65000) -> int
    def get_service_status(self) -> Dict[str, Any]
    def cleanup_range(self, range_id: int) -> None
    def cleanup_all(self) -> None
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
class RangeMetadata:
    range_id: str
    name: str
    description: str
    created_at: datetime
    status: RangeStatus = RangeStatus.CREATING
    last_modified: datetime = field(default_factory=datetime.now)
    owner: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    config_path: Optional[str] = None
    logs_path: Optional[str] = None
    provider_config: Optional[Dict[str, Any]] = None
    
    def update_status(self, status: RangeStatus) -> None
    def to_dict(self) -> Dict[str, Any]
    def from_dict(cls, data: Dict[str, Any]) -> 'RangeMetadata'

class RangeStatus(Enum):
    CREATING = "creating"
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"
```

### Task Execution
```python
@dataclass 
class TaskResult:
    task_id: str
    task_type: TaskType
    success: bool
    message: str
    execution_time: float = 0.0
    output: Optional[str] = None
    error: Optional[str] = None
    # Enhanced fields for verification
    vm_name: Optional[str] = None
    vm_ip: Optional[str] = None
    evidence: Optional[str] = None  # Verification evidence
    verification_passed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

### Network Services
```python
@dataclass
class NetworkValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class NetworkTestResult:
    success: bool
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class NetworkServiceConfig:
    max_ssh_connections: int = 10
    default_ssh_timeout: int = 30
    health_check_interval: int = 60
    enable_connection_pooling: bool = True
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