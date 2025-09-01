# Core Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **core**

## Module Responsibilities

The Core module provides foundational utilities and cross-cutting concerns for the entire CyRIS system. It implements reliability patterns, concurrency utilities, exception handling, security measures, and resource management that are used across all other modules. This module ensures system robustness and maintainability.

## Entry and Startup

- **Primary Entry**: `exceptions.py` - Centralized exception handling and error management
- **Concurrency**: `concurrency.py` - Thread-safe utilities and async operations
- **Network Reliability**: `network_reliability.py` - Network validation and SSH reliability
- **Security**: `security.py` - Security utilities and command validation
- **Resource Management**: `resource_manager.py` - Resource lifecycle management

### Core Architecture
```
core/
├── exceptions.py           # Centralized exception handling system
├── concurrency.py         # Thread-safe utilities and async operations
├── network_reliability.py # Network validation and SSH reliability  
├── security.py           # Security utilities and validation
├── resource_manager.py   # Resource lifecycle management
└── __init__.py           # Core module exports
```

## External Interfaces

### Exception Handling API
```python
class CyRISException(Exception):
    """Base exception for all CyRIS errors"""
    def __init__(self, message: str, error_code: CyRISErrorCode, context: Dict[str, Any] = None)

# Specialized exceptions
class CyRISVirtualizationError(CyRISException)
class CyRISNetworkError(CyRISException)  
class CyRISSecurityError(CyRISException)
class CyRISResourceError(CyRISException)

# Exception handling utilities
@handle_exception
def safe_operation() -> Any:
    """Decorator for automatic exception handling"""

def safe_execute(func, *args, **kwargs) -> ExecutionResult:
    """Safe function execution with error capture"""
```

### Error Code System
```python
@unique
class CyRISErrorCode(Enum):
    """Standardized error codes"""
    # General errors (1000-1099)
    UNKNOWN_ERROR = 1000
    VALIDATION_ERROR = 1001
    CONFIGURATION_ERROR = 1002
    
    # Infrastructure errors (1100-1199)
    VIRTUALIZATION_ERROR = 1100
    NETWORK_ERROR = 1101
    STORAGE_ERROR = 1102
    
    # Service errors (1200-1299)
    ORCHESTRATOR_ERROR = 1200
    TASK_EXECUTION_ERROR = 1201
    
    # Security errors (1300-1399)
    SECURITY_ERROR = 1300
    AUTHENTICATION_ERROR = 1301
```

### Concurrency API
```python
class ThreadSafeCounter:
    """Thread-safe atomic counter"""
    def increment(self, amount: int = 1) -> int
    def decrement(self, amount: int = 1) -> int
    def reset(self, value: int = 0) -> int

class ResourceLock:
    """Resource-specific locking mechanism"""
    @contextmanager
    def acquire(self, resource_id: str, timeout: float = 30.0)

class AsyncTaskManager:
    """Async task lifecycle management"""
    async def execute_concurrent_tasks(self, tasks: List[Callable]) -> List[Any]
    async def execute_with_timeout(self, coro: Awaitable, timeout: float) -> Any
```

### Network Reliability API
```python
@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0

class NetworkValidator:
    """Network configuration validation"""
    def validate_ip_address(self, ip: str) -> NetworkValidationResult
    def validate_network_range(self, cidr: str) -> NetworkValidationResult
    def test_connectivity(self, host: str, port: int) -> NetworkTestResult

class SSHConnectionPool:
    """SSH connection pooling and health management"""
    def get_connection(self, host: str, username: str) -> SSHConnection
    def release_connection(self, connection: SSHConnection) -> None
    def health_check_all(self) -> Dict[str, bool]
```

### Security API
```python
class CommandValidator:
    """Command injection prevention"""
    def validate_command(self, command: str) -> bool
    def sanitize_command(self, command: str) -> str
    def is_safe_path(self, path: str) -> bool

class CryptographyUtils:
    """Cryptographic utilities"""
    def generate_ssh_keypair(self) -> Tuple[str, str]  # (private, public)
    def hash_password(self, password: str) -> str
    def verify_password(self, password: str, hashed: str) -> bool
```

### Resource Management API
```python
class ResourceManager:
    """System resource management"""
    def monitor_resources(self) -> ResourceStatus
    def cleanup_orphaned_resources(self) -> int
    def enforce_resource_limits(self) -> bool
    
class TemporaryResourceManager:
    """Temporary resource lifecycle"""
    @contextmanager
    def temporary_directory(self) -> Path
    @contextmanager  
    def temporary_vm(self, config: Dict) -> VMInfo
```

## Key Dependencies and Configuration

### External Dependencies
```python
paramiko>=4.0          # SSH connections and cryptography
psutil>=7.0           # System resource monitoring
cryptography>=45.0    # Cryptographic operations
asyncio              # Async programming (standard library)
threading            # Thread synchronization (standard library)
concurrent.futures   # Parallel execution (standard library)
```

### Internal Dependencies
- No dependencies on other CyRIS modules (foundational layer)
- Used by all other modules for reliability and safety

### Core Configuration
```python
class CoreConfig(BaseSettings):
    """Core module configuration"""
    
    # Exception handling
    log_exceptions: bool = True
    exception_detail_level: str = "INFO"  # DEBUG, INFO, WARNING
    
    # Concurrency
    max_concurrent_operations: int = 10
    default_timeout: float = 300.0
    thread_pool_size: int = 4
    
    # Network reliability
    default_retry_attempts: int = 3
    connection_timeout: float = 30.0
    ssh_keepalive_interval: int = 30
    
    # Security
    enable_command_validation: bool = True
    allow_privileged_commands: bool = False
    ssh_strict_host_key_checking: bool = True
    
    # Resource management
    resource_monitoring_interval: int = 60
    cleanup_orphaned_resources: bool = True
    temporary_resource_ttl: int = 3600  # 1 hour
```

## Data Models

### Exception Information
```python
@dataclass
class ErrorContext:
    """Additional context for errors"""
    component: str
    operation: str
    resource_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ExecutionResult:
    """Result of safe operation execution"""
    success: bool
    result: Any = None
    error: Optional[CyRISException] = None
    execution_time: float = 0.0
```

### Network and Connectivity
```python
@dataclass
class NetworkTestResult:
    """Network connectivity test result"""
    success: bool
    response_time: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SSHConnectionInfo:
    """SSH connection metadata"""
    host: str
    port: int
    username: str
    connection_id: str
    established_at: datetime
    last_used: datetime
    is_healthy: bool = True
```

### Resource Monitoring
```python
@dataclass
class ResourceStatus:
    """Current system resource status"""
    cpu_percent: float
    memory_percent: float
    disk_usage: Dict[str, float]  # path -> usage_percent
    active_processes: int
    network_connections: int
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ResourceLimit:
    """Resource usage limits"""
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 85.0
    max_disk_usage: float = 90.0
    max_processes: int = 1000
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_exceptions.py` - Exception handling system testing
- `/home/ubuntu/cyris/tests/unit/test_concurrency.py` - Thread safety and concurrency testing
- `/home/ubuntu/cyris/tests/unit/test_network_reliability.py` - Network reliability testing
- `/home/ubuntu/cyris/tests/unit/test_security.py` - Security utilities testing
- `/home/ubuntu/cyris/tests/unit/test_resource_manager.py` - Resource management testing

### Integration Tests
- `/home/ubuntu/cyris/tests/integration/test_core_reliability.py` - End-to-end reliability testing
- Test real network conditions, SSH connections, and resource constraints
- Validate exception propagation across module boundaries

### Reliability Testing
```python
class TestReliabilityPatterns:
    """Core reliability pattern testing"""
    
    def test_retry_with_exponential_backoff(self):
        """Test retry policies under failure conditions"""
        
    def test_circuit_breaker_behavior(self):
        """Test circuit breaker pattern implementation"""
        
    def test_timeout_handling(self):
        """Test operation timeout and cancellation"""
        
    def test_resource_cleanup_on_failure(self):
        """Test resource cleanup in failure scenarios"""
        
    def test_exception_context_preservation(self):
        """Test exception context and stack trace preservation"""
```

### Quality Requirements
- **Exception Handling**: 100% of exceptions must have proper context and error codes
- **Thread Safety**: All shared data structures must be thread-safe
- **Performance**: Core utilities must add < 5ms overhead to operations
- **Reliability**: Network operations must succeed 95% of the time with proper retry

## Frequently Asked Questions (FAQ)

### Q: How does the exception handling system work across modules?
A: All CyRIS modules use the centralized exception classes with standardized error codes. The system provides automatic context capture, structured logging, and consistent error reporting.

### Q: Are the concurrency utilities safe for multi-process deployment?
A: The concurrency utilities are designed for multi-threaded single-process operation. For multi-process scenarios, use external coordination like Redis or database locks.

### Q: How does network reliability improve SSH operations?
A: The network reliability module provides connection pooling, automatic retry with exponential backoff, health monitoring, and connection validation to improve SSH success rates.

### Q: What security measures are implemented for command execution?
A: Command validation prevents injection attacks, path validation ensures safe file operations, and SSH operations use strict host key checking with proper authentication.

### Q: How are system resources monitored and managed?
A: Resource monitoring tracks CPU, memory, disk, and network usage. The system enforces limits and automatically cleans up orphaned resources to prevent resource exhaustion.

### Q: Can I extend the core utilities with custom functionality?
A: Yes, core utilities are designed for extension. Create subclasses or implement the provided interfaces while maintaining thread safety and error handling patterns.

## Related File List

### Core Utilities
- `/home/ubuntu/cyris/src/cyris/core/exceptions.py` - Centralized exception handling and error codes
- `/home/ubuntu/cyris/src/cyris/core/concurrency.py` - Thread-safe utilities and async operations
- `/home/ubuntu/cyris/src/cyris/core/network_reliability.py` - Network validation and SSH reliability
- `/home/ubuntu/cyris/src/cyris/core/security.py` - Security utilities and command validation
- `/home/ubuntu/cyris/src/cyris/core/resource_manager.py` - Resource lifecycle management
- `/home/ubuntu/cyris/src/cyris/core/__init__.py` - Core module exports

### Core Tests
- `/home/ubuntu/cyris/tests/unit/test_exceptions.py` - Exception handling system tests
- `/home/ubuntu/cyris/tests/unit/test_concurrency.py` - Concurrency utilities tests
- `/home/ubuntu/cyris/tests/unit/test_network_reliability.py` - Network reliability tests
- `/home/ubuntu/cyris/tests/unit/test_security.py` - Security utilities tests
- `/home/ubuntu/cyris/tests/unit/test_resource_manager.py` - Resource management tests

### Integration Points
- Used by all CyRIS modules for exception handling and reliability
- Integrated with logging system for structured error reporting
- Network reliability used by tools and infrastructure modules
- Security utilities used throughout the system for safe operations

### Configuration
- Core configuration integrated with main CyRIS settings
- Runtime configuration for retry policies and resource limits
- Security configuration for command validation and SSH settings

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Core module documentation with comprehensive utility coverage
- **[RELIABILITY]** Documented exception handling, concurrency, and network reliability patterns
- **[SECURITY]** Outlined security utilities and safe operation practices for system robustness