# Domain Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **domain**

## Module Responsibilities

The Domain module contains the core business entities and data models that represent the fundamental concepts of cyber range infrastructure. Built on Pydantic for validation and serialization, this module defines the contract between different layers and ensures data consistency across the system.

## Entry and Startup

- **Primary Entry**: `entities/__init__.py` - Entity exports and domain model registration
- **Base Entities**: `entities/base.py` - Abstract base classes for Entity and ValueObject
- **Host Model**: `entities/host.py` - Physical/virtual host representation
- **Guest Model**: `entities/guest.py` - Virtual machine entity definition

### Domain Architecture
```
domain/
├── entities/
│   ├── __init__.py           # Entity exports and registration
│   ├── base.py              # Abstract base Entity and ValueObject
│   ├── host.py              # Host entity (physical/virtual hosts)
│   ├── guest.py             # Guest entity (virtual machines)
│   └── ...                  # Additional domain entities
└── __init__.py              # Domain module exports
```

## External Interfaces

### Entity Base Classes
```python
class Entity(BaseModel, ABC):
    """Base class for domain entities with identity"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Configuration for Pydantic v2
    model_config = {
        "arbitrary_types_allowed": True,
        "use_enum_values": True
    }

class ValueObject(BaseModel, ABC):
    """Base class for immutable value objects"""
    model_config = {
        "frozen": True,
        "arbitrary_types_allowed": True
    }
```

### Host Entity API
```python
class Host(Entity):
    """Physical or virtual host configuration"""
    host_id: str = Field(..., description="Host unique identifier")
    mgmt_addr: str = Field(..., description="Management address")
    virbr_addr: str = Field(..., description="Virtual bridge address")
    account: str = Field(..., description="Host account name")
    
    # Methods
    def get_host_id(self) -> str
    def get_mgmt_addr(self) -> str
    def get_virbr_addr(self) -> str
    def get_account(self) -> str
```

### Guest Entity API
```python
class BaseVMType(str, Enum):
    KVM = "kvm"
    AWS = "aws" 
    DOCKER = "docker"

class OSType(str, Enum):
    UBUNTU = "ubuntu"
    UBUNTU_16 = "ubuntu_16"
    UBUNTU_18 = "ubuntu_18"
    UBUNTU_20 = "ubuntu_20"
    CENTOS = "centos"
    WINDOWS_7 = "windows.7"
    WINDOWS_8_1 = "windows.8.1"
    WINDOWS_10 = "windows.10"
    AMAZON_LINUX = "amazon_linux"
    AMAZON_LINUX2 = "amazon_linux2"
    RED_HAT = "red_hat"

class Guest(Entity):
    """Virtual machine configuration and state"""
    guest_id: str = Field(..., description="VM unique identifier")
    ip_addr: Optional[str] = Field(default=None, description="IP address for the VM")
    basevm_addr: Optional[str] = Field(default=None, description="Base virtual machine address")
    root_passwd: Optional[str] = Field(default=None, description="Root password")
    basevm_host: str = Field(..., description="Host where base VM is located")
    basevm_config_file: str = Field(..., description="Base VM configuration file path")
    basevm_os_type: OSType = Field(..., description="Operating system type")
    basevm_type: BaseVMType = Field(..., description="Virtualization platform type")
    basevm_name: Optional[str] = Field(default=None, description="Base virtual machine name")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Task list")
    
    # Properties and utility methods
    @property
    def id(self) -> str  # Alias for guest_id
    def get_guest_id(self) -> str
    def get_basevm_addr(self) -> Optional[str]
    def set_basevm_addr(self, addr: str) -> None
    def get_root_passwd(self) -> Optional[str]
    def set_root_passwd(self, passwd: str) -> None
    def get_basevm_host(self) -> str
    def get_basevm_config_file(self) -> str
    def get_basevm_type(self) -> BaseVMType
    def get_tasks(self) -> List[Dict[str, Any]]
    def add_task(self, task: Dict[str, Any]) -> None
```

## Key Dependencies and Configuration

### External Dependencies
```python
pydantic>=2.0           # Data validation and serialization
uuid                   # Unique identifier generation (standard library)  
enum                   # Enumeration support (standard library)
typing                 # Type hints (standard library)
```

### Internal Dependencies
- No internal CyRIS dependencies (domain is the core layer)
- Designed to be independent and reusable across different contexts

### Domain Configuration
```python
class DomainConfig:
    """Domain layer configuration"""
    enable_strict_validation: bool = True
    use_uuid4_for_ids: bool = True
    serialize_enums_by_value: bool = True
    allow_arbitrary_types: bool = True  # For compatibility
```

## Data Models

### Base VM Types and OS Support
```python
class BaseVMType(str, Enum):
    """Supported virtualization platforms"""
    KVM = "kvm"
    AWS = "aws"
    DOCKER = "docker"

class OSType(str, Enum):
    """Supported operating system types"""
    UBUNTU = "ubuntu"
    UBUNTU_16 = "ubuntu_16"
    UBUNTU_18 = "ubuntu_18"
    UBUNTU_20 = "ubuntu_20"
    CENTOS = "centos"
    WINDOWS_7 = "windows.7"
    WINDOWS_8_1 = "windows.8.1"
    WINDOWS_10 = "windows.10"
    AMAZON_LINUX = "amazon_linux"
    AMAZON_LINUX2 = "amazon_linux2"
    RED_HAT = "red_hat"
```

### Task and Configuration Models
```python
@dataclass
class TaskConfig:
    """Configuration for VM tasks"""
    task_type: str
    parameters: Dict[str, Any]
    verification: Optional[Dict[str, Any]] = None
    timeout: int = 300
    retry_count: int = 3

@dataclass
class NetworkInterface:
    """Network interface configuration"""
    name: str
    ip_address: Optional[str] = None
    network_name: str
    mac_address: Optional[str] = None
```

### Validation and Serialization
```python
class DomainEntity(Entity):
    """Enhanced base entity with domain-specific validation"""
    
    @field_validator('*', mode='before')
    @classmethod
    def validate_not_empty_string(cls, v):
        """Ensure string fields are not empty"""
        if isinstance(v, str) and len(v.strip()) == 0:
            raise ValueError("String fields cannot be empty")
        return v.strip() if isinstance(v, str) else v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create entity from dictionary"""
        return cls(**data)
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_domain_entities.py` - Entity validation and behavior testing
- `/home/ubuntu/cyris/tests/unit/test_host_entity.py` - Host entity specific testing
- `/home/ubuntu/cyris/tests/unit/test_guest_entity.py` - Guest entity specific testing
- Focus on validation logic, serialization, and business rules

### Integration Tests
- `/home/ubuntu/cyris/tests/integration/test_entity_serialization.py` - YAML/JSON serialization testing
- Test entity interactions with configuration parsers and service layers
- Validate backward compatibility with legacy entity formats

### Domain Testing Strategy
```python
class TestDomainEntity:
    """Domain entity testing patterns"""
    
    def test_entity_validation(self):
        """Test Pydantic validation rules"""
        
    def test_entity_serialization(self):
        """Test JSON/YAML serialization"""
        
    def test_entity_equality(self):
        """Test entity identity and equality"""
        
    def test_value_object_immutability(self):
        """Test value object immutability"""
```

### Quality Requirements
- **Validation Coverage**: 100% of field validation rules tested
- **Serialization**: Round-trip serialization must be lossless
- **Compatibility**: Backward compatibility with legacy YAML formats
- **Performance**: Entity operations < 1ms for typical use cases

## Frequently Asked Questions (FAQ)

### Q: How are domain entities different from DTOs or configuration objects?
A: Domain entities represent core business concepts with identity and behavior, while DTOs are simple data transfer objects. Entities encapsulate business rules and validation logic.

### Q: Why use Pydantic instead of dataclasses or plain classes?
A: Pydantic provides built-in validation, serialization, and type checking. This ensures data consistency and reduces boilerplate code while maintaining type safety.

### Q: How does the domain layer maintain independence from infrastructure?
A: Domain entities have no dependencies on infrastructure or external libraries (except Pydantic). This allows the domain to evolve independently and be tested in isolation.

### Q: Can I extend entities with custom fields or behavior?
A: Yes, entities inherit from Pydantic BaseModel and can be extended. Use field validators for custom validation and methods for behavior.

### Q: How are enums handled for backward compatibility?
A: Enums use string values with `use_enum_values=True` configuration, allowing seamless serialization to/from YAML while maintaining type safety.

### Q: What happens when entity validation fails?
A: Pydantic raises `ValidationError` with detailed information about which fields failed validation and why, enabling precise error handling.

## Related File List

### Core Entities
- `/home/ubuntu/cyris/src/cyris/domain/entities/base.py` - Abstract base classes for entities and value objects
- `/home/ubuntu/cyris/src/cyris/domain/entities/host.py` - Host entity definition with validation
- `/home/ubuntu/cyris/src/cyris/domain/entities/guest.py` - Guest/VM entity with OS and platform support
- `/home/ubuntu/cyris/src/cyris/domain/entities/__init__.py` - Entity exports and registration

### Domain Module
- `/home/ubuntu/cyris/src/cyris/domain/__init__.py` - Domain module exports and public API

### Domain Tests  
- `/home/ubuntu/cyris/tests/unit/test_domain_entities.py` - Comprehensive entity testing
- `/home/ubuntu/cyris/tests/unit/test_host_entity.py` - Host entity specific tests
- `/home/ubuntu/cyris/tests/unit/test_guest_entity.py` - Guest entity specific tests

### Configuration Integration
- Domain entities integrate with `/home/ubuntu/cyris/src/cyris/config/parser.py` for YAML parsing
- Used by `/home/ubuntu/cyris/src/cyris/services/orchestrator.py` for business logic
- Serialized in `/home/ubuntu/cyris/cyber_range/ranges_metadata.json` for persistence

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Domain module documentation with comprehensive entity coverage
- **[ARCHITECTURE]** Documented Pydantic-based domain model strategy and validation approach
- **[COMPATIBILITY]** Outlined entity evolution and backward compatibility strategy