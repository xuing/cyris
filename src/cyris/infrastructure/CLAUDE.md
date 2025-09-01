# Infrastructure Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **infrastructure**

## Module Responsibilities

The Infrastructure module provides provider abstractions and low-level infrastructure management for virtualization and networking. It implements the adapter pattern to support multiple virtualization platforms (KVM/QEMU, AWS) and handles network topology creation, bridge management, and tunneling.

## Entry and Startup

- **Primary Entry**: `providers/base_provider.py` - Abstract provider interface
- **KVM Provider**: `providers/kvm_provider.py` - KVM/QEMU virtualization implementation  
- **AWS Provider**: `providers/aws_provider.py` - AWS cloud infrastructure implementation
- **Network Manager**: `network/topology_manager.py` - Network topology orchestration

### Infrastructure Architecture
```
infrastructure/
├── providers/
│   ├── base_provider.py      # Abstract provider interface
│   ├── kvm_provider.py       # KVM/QEMU implementation
│   ├── aws_provider.py       # AWS cloud implementation
│   └── virsh_client.py       # Virsh command-line client
├── network/
│   ├── topology_manager.py   # Network topology management
│   ├── bridge_manager.py     # Linux bridge management
│   ├── firewall_manager.py   # Iptables/firewall rules
│   └── tunnel_manager.py     # SSH tunnel management
└── permissions.py            # System permission management
```

## External Interfaces

### Provider Interface
```python
class InfrastructureProvider(ABC):
    @abstractmethod
    def create_vm(self, vm_config: Dict) -> VMInfo
    
    @abstractmethod  
    def destroy_vm(self, vm_id: str) -> bool
    
    @abstractmethod
    def list_vms(self, range_id: Optional[str] = None) -> List[VMInfo]
    
    @abstractmethod
    def get_vm_status(self, vm_id: str) -> VMStatus
    
    @abstractmethod
    def get_vm_ip(self, vm_id: str) -> Optional[str]
```

### KVM Provider API
```python
class KVMProvider(InfrastructureProvider):
    def create_vm(self, vm_config: Dict) -> VMInfo
    def destroy_vm(self, vm_id: str) -> bool
    def clone_vm(self, base_vm: str, new_name: str) -> VMInfo
    def inject_ssh_keys(self, vm_id: str, public_keys: List[str]) -> bool
    def create_cloud_init_iso(self, vm_id: str, user_data: str) -> Path
```

### AWS Provider API  
```python
class AWSProvider(InfrastructureProvider):
    def create_instance(self, instance_config: Dict) -> VMInfo
    def terminate_instance(self, instance_id: str) -> bool
    def create_security_group(self, group_config: Dict) -> str
    def setup_vpc_networking(self, vpc_config: Dict) -> VPCInfo
```

### Network Management API
```python
class NetworkTopologyManager:
    def create_topology(self, topology_config: Dict) -> NetworkTopology
    def assign_ip_addresses(self, guests: List[Guest]) -> Dict[str, str]
    def discover_vm_ips(self, vm_names: List[str]) -> Dict[str, str]
    def synchronize_metadata(self, range_id: str, ip_mappings: Dict) -> None

class BridgeManager:
    def create_bridge(self, bridge_name: str, subnet: str) -> bool
    def destroy_bridge(self, bridge_name: str) -> bool  
    def add_vm_to_bridge(self, vm_name: str, bridge_name: str) -> bool
```

## Key Dependencies and Configuration

### External Dependencies
```python
libvirt-python>=9.0   # KVM virtualization (optional, falls back to virsh)
boto3>=1.40          # AWS cloud services
psutil>=7.0          # System resource monitoring
xml.etree.ElementTree # XML configuration parsing (standard library)
```

### System Dependencies
- **KVM/QEMU**: `qemu-kvm`, `libvirt-daemon-system`, `virtinst`
- **Network Tools**: `bridge-utils`, `iptables`, `dnsmasq`  
- **Cloud Tools**: `cloud-init`, `genisoimage`

### Internal Dependencies
- `domain.entities` - Host/Guest entity models
- `config.settings` - Provider configuration
- `core.exceptions` - Infrastructure-specific exceptions
- `tools.vm_ip_manager` - IP discovery utilities

### Provider Configuration
```python
class KVMConfig(BaseSettings):
    libvirt_uri: str = "qemu:///system"
    base_vm_path: Path = Path("/var/lib/libvirt/images")
    bridge_prefix: str = "cr-br"
    storage_pool: str = "default"
    enable_cloud_init: bool = True

class AWSConfig(BaseSettings):
    region: str = "us-west-2"
    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    key_pair_name: str = "cyris-keypair"
    instance_type: str = "t3.micro"
```

## Data Models

### VM Information
```python
@dataclass
class VMInfo:
    vm_id: str
    vm_name: str
    status: VMStatus
    ip_address: Optional[str]
    provider: str
    created_at: datetime
    metadata: Dict[str, Any]

class VMStatus(Enum):
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DESTROYING = "destroying"
```

### Network Models
```python
@dataclass
class NetworkTopology:
    networks: List[NetworkInfo]
    ip_assignments: Dict[str, str]  # vm_name -> ip_address
    bridge_mappings: Dict[str, str]  # network_name -> bridge_name

@dataclass 
class NetworkInfo:
    name: str
    subnet: str
    gateway: str
    members: List[str]  # VM interface names
```

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_kvm_provider.py` - KVM provider testing with mocks
- `/home/ubuntu/cyris/tests/unit/test_network_reliability.py` - Network service testing
- `/home/ubuntu/cyris/tests/unit/test_tunnel_manager.py` - Tunnel management testing
- Mock libvirt and AWS services for isolated testing

### Integration Tests
- `/home/ubuntu/cyris/tests/integration/test_infrastructure_providers.py` - Provider integration
- `/home/ubuntu/cyris/tests/integration/test_network_topology.py` - Network topology testing
- Use testcontainers for isolated infrastructure testing

### E2E Tests
- `/home/ubuntu/cyris/tests/e2e/test_full_deployment.py` - Complete infrastructure workflows
- `/home/ubuntu/cyris/tests/e2e/test_resource_management_e2e.py` - Resource management testing
- Test with real VMs and network creation

### Quality Requirements
- **Reliability**: Automatic retry for transient virtualization failures
- **Resource Management**: Proper cleanup of VMs, networks, and storage
- **Performance**: VM creation < 5 minutes, network setup < 1 minute
- **Fault Tolerance**: Graceful degradation when providers unavailable

## Frequently Asked Questions (FAQ)

### Q: How does KVM provider handle libvirt unavailability?
A: The system uses a fallback strategy: python-libvirt → virsh command-line → mock mode for testing. This ensures functionality even without full libvirt python bindings.

### Q: How are VM IP addresses discovered and synchronized?  
A: The system uses a multi-method approach: libvirt DHCP leases → virsh domifaddr → ARP table → bridge inspection → DHCP server logs, with results synchronized to metadata.

### Q: What happens when a VM fails to create?
A: The provider implements progressive retry with exponential backoff, detailed error logging, and automatic resource cleanup for partial failures.

### Q: Can I add support for other virtualization platforms?
A: Yes, implement the `InfrastructureProvider` abstract interface and register the new provider in the provider factory.

### Q: How does network isolation work between ranges?
A: Each range gets dedicated bridges with unique names (cr-br-{range_id}-{network_name}) and isolated subnets, with optional firewall rules for additional security.

### Q: How are SSH keys injected into VMs?
A: For KVM: cloud-init ISO injection at boot. For AWS: key-pair association and user-data scripts. Both methods ensure secure key deployment.

## Related File List

### Provider Implementations
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/base_provider.py` - Abstract provider interface
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/kvm_provider.py` - KVM/QEMU implementation  
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/aws_provider.py` - AWS cloud implementation
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/virsh_client.py` - Virsh command wrapper
- `/home/ubuntu/cyris/src/cyris/infrastructure/providers/__init__.py` - Provider factory

### Network Management
- `/home/ubuntu/cyris/src/cyris/infrastructure/network/topology_manager.py` - Network topology orchestration
- `/home/ubuntu/cyris/src/cyris/infrastructure/network/bridge_manager.py` - Linux bridge management
- `/home/ubuntu/cyris/src/cyris/infrastructure/network/firewall_manager.py` - Firewall rule management
- `/home/ubuntu/cyris/src/cyris/infrastructure/network/tunnel_manager.py` - SSH tunnel management
- `/home/ubuntu/cyris/src/cyris/infrastructure/network/__init__.py` - Network module exports

### System Integration
- `/home/ubuntu/cyris/src/cyris/infrastructure/permissions.py` - System permission management
- `/home/ubuntu/cyris/src/cyris/infrastructure/__init__.py` - Infrastructure module exports

### Infrastructure Tests
- `/home/ubuntu/cyris/tests/unit/test_kvm_provider.py` - KVM provider unit tests
- `/home/ubuntu/cyris/tests/unit/test_network_reliability.py` - Network reliability tests
- `/home/ubuntu/cyris/tests/integration/test_infrastructure_providers.py` - Provider integration tests
- `/home/ubuntu/cyris/tests/integration/test_network_topology.py` - Network topology tests

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created Infrastructure module documentation with provider abstraction coverage
- **[ARCHITECTURE]** Documented multi-provider support strategy and fallback mechanisms  
- **[INTEGRATION]** Outlined testing approach for infrastructure reliability and resource management