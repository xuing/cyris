"""
KVM Infrastructure Provider

This module provides KVM/QEMU virtualization support for CyRIS,
implementing the infrastructure provider interface for local virtualization.
"""

import logging
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import time
import uuid

try:
    import libvirt
    LIBVIRT_AVAILABLE = True
except ImportError:
    LIBVIRT_AVAILABLE = False
    # Mock libvirt for testing purposes
    class MockLibvirt:
        VIR_DOMAIN_RUNNING = 1
        VIR_DOMAIN_SHUTOFF = 5
        VIR_DOMAIN_PAUSED = 3
        
        class virDomain:
            """Mock domain class"""
            pass
            
        @staticmethod
        def open(uri=None):
            return None
    
    libvirt = MockLibvirt()

from .base_provider import (
    InfrastructureProvider, ResourceInfo, ResourceStatus,
    InfrastructureError, ConnectionError, ResourceCreationError,
    ResourceDestructionError, ResourceNotFoundError
)
from ...domain.entities.host import Host
from ...domain.entities.guest import Guest


class KVMProvider(InfrastructureProvider):
    """
    KVM/QEMU infrastructure provider implementation.
    
    This provider manages KVM virtual machines and associated resources
    on local physical infrastructure.
    
    Capabilities:
    - VM creation and management
    - Network bridge configuration
    - Storage volume management
    - VM cloning and templates
    - Resource monitoring
    
    Configuration:
    - libvirt_uri: Connection URI for libvirt (default: qemu:///system)
    - storage_pool: Default storage pool name
    - network_prefix: Prefix for created networks
    - vm_template_dir: Directory containing VM templates
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize KVM provider.
        
        Args:
            config: Provider configuration dictionary
        """
        super().__init__("kvm", config)
        
        # Configuration with defaults
        self.libvirt_uri = config.get("libvirt_uri", "qemu:///system")
        self.storage_pool = config.get("storage_pool", "default")
        self.network_prefix = config.get("network_prefix", "cyris")
        self.vm_template_dir = Path(config.get("vm_template_dir", "/var/lib/libvirt/templates"))
        self.base_image_dir = Path(config.get("base_image_dir", "/var/lib/libvirt/images"))
        
        # Connection state
        self._connection: Optional[libvirt.virConnect] = None
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"KVMProvider initialized with URI: {self.libvirt_uri}")
    
    def connect(self) -> None:
        """
        Establish connection to libvirt daemon.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            if self._connection is not None:
                # Test existing connection
                if self._connection.isAlive():
                    return
                else:
                    self._connection.close()
            
            self.logger.info(f"Connecting to libvirt at {self.libvirt_uri}")
            self._connection = libvirt.open(self.libvirt_uri)
            
            if self._connection is None:
                raise ConnectionError(f"Failed to connect to libvirt at {self.libvirt_uri}")
            
            # Verify connection and basic functionality
            hostname = self._connection.getHostname()
            self.logger.info(f"Connected to hypervisor: {hostname}")
            
        except libvirt.libvirtError as e:
            self.logger.error(f"Libvirt connection failed: {e}")
            raise ConnectionError(f"Libvirt connection failed: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to libvirt: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Clean up and close connections"""
        if self._connection is not None:
            try:
                self._connection.close()
                self.logger.info("Disconnected from libvirt")
            except Exception as e:
                self.logger.warning(f"Error closing libvirt connection: {e}")
            finally:
                self._connection = None
    
    def is_connected(self) -> bool:
        """Check if provider is connected and ready"""
        return self._connection is not None and self._connection.isAlive()
    
    def create_hosts(self, hosts: List[Host]) -> List[str]:
        """
        Create physical hosts (for KVM, this is mainly network setup).
        
        Args:
            hosts: List of host configurations
        
        Returns:
            List of created host resource IDs
        
        Raises:
            InfrastructureError: If creation fails
        """
        if not self.is_connected():
            self.connect()
        
        host_ids = []
        
        for host in hosts:
            try:
                self.logger.info(f"Setting up host environment for {host.id}")
                
                # For KVM, host creation mainly involves network setup
                # Create networks defined in host configuration
                for network_config in getattr(host, 'networks', []):
                    network_id = self._create_network(host.id, network_config)
                    self.logger.info(f"Created network {network_id} for host {host.id}")
                
                # Register host resource
                host_resource = ResourceInfo(
                    resource_id=host.id,
                    resource_type="host",
                    name=host.id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "kvm",
                        "host_type": "physical",
                        "networks": getattr(host, 'networks', [])
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self._register_resource(host_resource)
                host_ids.append(host.id)
                
            except Exception as e:
                self.logger.error(f"Failed to create host {host.id}: {e}")
                raise ResourceCreationError(f"Host creation failed: {e}", "kvm", host.id)
        
        return host_ids
    
    def create_guests(self, guests: List[Guest], host_mapping: Dict[str, str]) -> List[str]:
        """
        Create virtual machines.
        
        Args:
            guests: List of guest configurations
            host_mapping: Mapping of guest host references to actual host IDs
        
        Returns:
            List of created guest resource IDs
        
        Raises:
            InfrastructureError: If creation fails
        """
        if not self.is_connected():
            self.connect()
        
        guest_ids = []
        
        for guest in guests:
            try:
                self.logger.info(f"Creating VM for guest {guest.id}")
                
                # Generate unique VM name
                vm_name = f"{self.network_prefix}-{guest.id}-{str(uuid.uuid4())[:8]}"
                
                # Create VM disk from base image
                disk_path = self._create_vm_disk(vm_name, guest)
                
                # Generate VM XML configuration
                vm_xml = self._generate_vm_xml(vm_name, guest, disk_path, host_mapping)
                
                # Define and start VM
                domain = self._connection.defineXML(vm_xml)
                if domain is None:
                    raise ResourceCreationError(f"Failed to define VM {vm_name}")
                
                # Start the VM
                if domain.create() < 0:
                    raise ResourceCreationError(f"Failed to start VM {vm_name}")
                
                # Wait for VM to be running
                self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_RUNNING)
                
                # Register guest resource
                guest_resource = ResourceInfo(
                    resource_id=vm_name,
                    resource_type="guest",
                    name=guest.id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "kvm",
                        "guest_id": guest.id,
                        "vm_name": vm_name,
                        "disk_path": disk_path,
                        "os_type": guest.os_type,
                        "memory_mb": guest.memory_mb,
                        "vcpus": guest.vcpus
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self._register_resource(guest_resource)
                guest_ids.append(vm_name)
                
                self.logger.info(f"Successfully created VM {vm_name} for guest {guest.id}")
                
            except Exception as e:
                self.logger.error(f"Failed to create guest {guest.id}: {e}")
                raise ResourceCreationError(f"Guest creation failed: {e}", "kvm", guest.id)
        
        return guest_ids
    
    def destroy_hosts(self, host_ids: List[str]) -> None:
        """
        Destroy physical hosts (cleanup networks for KVM).
        
        Args:
            host_ids: List of host resource IDs to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        if not self.is_connected():
            self.connect()
        
        for host_id in host_ids:
            try:
                self.logger.info(f"Cleaning up host {host_id}")
                
                # Get host resource info
                host_resource = self._resources.get(host_id)
                if host_resource and "networks" in host_resource.metadata:
                    # Cleanup networks
                    for network_config in host_resource.metadata["networks"]:
                        network_name = f"{self.network_prefix}-{host_id}-{network_config.get('name', 'default')}"
                        self._destroy_network(network_name)
                
                # Unregister resource
                self._unregister_resource(host_id)
                
                self.logger.info(f"Successfully cleaned up host {host_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to destroy host {host_id}: {e}")
                raise ResourceDestructionError(f"Host destruction failed: {e}", "kvm", host_id)
    
    def destroy_guests(self, guest_ids: List[str]) -> None:
        """
        Destroy virtual machines.
        
        Args:
            guest_ids: List of guest resource IDs to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        if not self.is_connected():
            self.connect()
        
        for guest_id in guest_ids:
            try:
                self.logger.info(f"Destroying VM {guest_id}")
                
                # Get the domain
                try:
                    domain = self._connection.lookupByName(guest_id)
                except libvirt.libvirtError:
                    self.logger.warning(f"VM {guest_id} not found, may already be destroyed")
                    self._unregister_resource(guest_id)
                    continue
                
                # Force stop if running
                if domain.isActive():
                    domain.destroy()  # Force stop
                
                # Wait for VM to stop
                self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_SHUTOFF, timeout=30)
                
                # Get disk paths before undefining
                guest_resource = self._resources.get(guest_id)
                disk_path = None
                if guest_resource and "disk_path" in guest_resource.metadata:
                    disk_path = guest_resource.metadata["disk_path"]
                
                # Undefine the VM
                domain.undefine()
                
                # Remove disk file
                if disk_path and Path(disk_path).exists():
                    Path(disk_path).unlink()
                    self.logger.info(f"Removed disk file {disk_path}")
                
                # Unregister resource
                self._unregister_resource(guest_id)
                
                self.logger.info(f"Successfully destroyed VM {guest_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to destroy guest {guest_id}: {e}")
                raise ResourceDestructionError(f"Guest destruction failed: {e}", "kvm", guest_id)
    
    def get_status(self, resource_ids: List[str]) -> Dict[str, str]:
        """
        Get status of resources.
        
        Args:
            resource_ids: List of resource IDs to check
        
        Returns:
            Dictionary mapping resource ID to status string
        
        Raises:
            InfrastructureError: If status check fails
        """
        if not self.is_connected():
            self.connect()
        
        status_map = {}
        
        for resource_id in resource_ids:
            try:
                resource = self._resources.get(resource_id)
                if not resource:
                    status_map[resource_id] = "not_found"
                    continue
                
                if resource.resource_type == "host":
                    # For hosts, we just return active if registered
                    status_map[resource_id] = "active"
                
                elif resource.resource_type == "guest":
                    # For guests, check actual VM status
                    try:
                        domain = self._connection.lookupByName(resource_id)
                        state, _ = domain.state()
                        
                        if state == libvirt.VIR_DOMAIN_RUNNING:
                            status_map[resource_id] = "active"
                        elif state == libvirt.VIR_DOMAIN_SHUTOFF:
                            status_map[resource_id] = "stopped"
                        elif state == libvirt.VIR_DOMAIN_PAUSED:
                            status_map[resource_id] = "paused"
                        else:
                            status_map[resource_id] = "unknown"
                    
                    except libvirt.libvirtError:
                        status_map[resource_id] = "error"
                
                else:
                    status_map[resource_id] = "unknown"
            
            except Exception as e:
                self.logger.error(f"Failed to get status for {resource_id}: {e}")
                status_map[resource_id] = "error"
        
        return status_map
    
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """
        Get detailed information about a resource.
        
        Args:
            resource_id: Resource identifier
        
        Returns:
            ResourceInfo object or None if not found
        """
        resource = self._resources.get(resource_id)
        if not resource:
            return None
        
        # For VMs, get additional runtime information
        if resource.resource_type == "guest":
            try:
                if self.is_connected():
                    domain = self._connection.lookupByName(resource_id)
                    info = domain.info()
                    
                    # Update metadata with runtime info
                    resource.metadata.update({
                        "max_memory_kb": info[1],
                        "used_memory_kb": info[2], 
                        "vcpus_count": info[3],
                        "cpu_time_ns": info[4]
                    })
                    
                    # Get network interfaces
                    try:
                        interfaces = domain.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE)
                        if interfaces:
                            ips = []
                            for interface, data in interfaces.items():
                                if data['addrs']:
                                    for addr in data['addrs']:
                                        ips.append(addr['addr'])
                            resource.ip_addresses = ips
                    except:
                        pass  # Interface info not always available
                        
            except libvirt.libvirtError:
                pass  # VM may not exist anymore
        
        return resource
    
    def _create_network(self, host_id: str, network_config: Dict[str, Any]) -> str:
        """Create a virtual network"""
        network_name = f"{self.network_prefix}-{host_id}-{network_config.get('name', 'default')}"
        
        # Check if network already exists
        try:
            existing_net = self._connection.networkLookupByName(network_name)
            if existing_net:
                self.logger.info(f"Network {network_name} already exists")
                return network_name
        except libvirt.libvirtError:
            pass  # Network doesn't exist, proceed to create
        
        # Generate network XML
        network_xml = self._generate_network_xml(network_name, network_config)
        
        # Define and start network
        network = self._connection.networkDefineXML(network_xml)
        if network is None:
            raise ResourceCreationError(f"Failed to define network {network_name}")
        
        # Start the network
        if network.create() < 0:
            raise ResourceCreationError(f"Failed to start network {network_name}")
        
        return network_name
    
    def _destroy_network(self, network_name: str) -> None:
        """Destroy a virtual network"""
        try:
            network = self._connection.networkLookupByName(network_name)
            
            # Stop the network if active
            if network.isActive():
                network.destroy()
            
            # Undefine the network
            network.undefine()
            
            self.logger.info(f"Destroyed network {network_name}")
            
        except libvirt.libvirtError as e:
            if "network not found" not in str(e).lower():
                raise
    
    def _create_vm_disk(self, vm_name: str, guest: Guest) -> str:
        """Create VM disk from base image"""
        base_image = self.base_image_dir / f"{guest.os_type}.qcow2"
        
        if not base_image.exists():
            # Try common base image names
            for possible_name in [f"{guest.os_type}.img", f"{guest.os_type}.raw", "base.qcow2"]:
                possible_path = self.base_image_dir / possible_name
                if possible_path.exists():
                    base_image = possible_path
                    break
            else:
                raise ResourceCreationError(f"Base image not found for OS type: {guest.os_type}")
        
        # Create disk in storage pool
        disk_path = self.base_image_dir / f"{vm_name}.qcow2"
        
        # Copy base image to new disk
        subprocess.run([
            "qemu-img", "create", "-f", "qcow2", 
            "-b", str(base_image), 
            str(disk_path)
        ], check=True)
        
        # Resize if needed
        if hasattr(guest, 'disk_size_gb') and guest.disk_size_gb:
            subprocess.run([
                "qemu-img", "resize", str(disk_path), f"{guest.disk_size_gb}G"
            ], check=True)
        
        return str(disk_path)
    
    def _generate_vm_xml(
        self, 
        vm_name: str, 
        guest: Guest, 
        disk_path: str, 
        host_mapping: Dict[str, str]
    ) -> str:
        """Generate libvirt XML for VM"""
        
        memory_kb = (guest.memory_mb or 1024) * 1024
        vcpus = guest.vcpus or 1
        
        xml = f"""
<domain type='kvm'>
  <name>{vm_name}</name>
  <uuid>{uuid.uuid4()}</uuid>
  <memory unit='KiB'>{memory_kb}</memory>
  <currentMemory unit='KiB'>{memory_kb}</currentMemory>
  <vcpu placement='static'>{vcpus}</vcpu>
  <os>
    <type arch='x86_64' machine='pc'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='bridge'>
      <source bridge='virbr0'/>
      <model type='virtio'/>
    </interface>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <input type='tablet' bus='usb'/>
    <input type='mouse' bus='ps2'/>
    <input type='keyboard' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes'/>
    <video>
      <model type='cirrus' vram='16384' heads='1'/>
    </video>
  </devices>
</domain>
        """.strip()
        
        return xml
    
    def _generate_network_xml(self, network_name: str, network_config: Dict[str, Any]) -> str:
        """Generate libvirt XML for network"""
        bridge_name = network_config.get("bridge", f"br-{network_name}")
        ip_range = network_config.get("ip_range", "192.168.100.0/24")
        
        # Parse IP range
        import ipaddress
        network = ipaddress.ip_network(ip_range, strict=False)
        gateway = str(list(network.hosts())[0])
        
        xml = f"""
<network>
  <name>{network_name}</name>
  <bridge name='{bridge_name}' stp='on' delay='0'/>
  <ip address='{gateway}' netmask='{network.netmask}'>
    <dhcp>
      <range start='{list(network.hosts())[10]}' end='{list(network.hosts())[-10]}'/>
    </dhcp>
  </ip>
</network>
        """.strip()
        
        return xml
    
    def _wait_for_vm_state(
        self, 
        domain: libvirt.virDomain, 
        expected_state: int, 
        timeout: int = 60
    ) -> None:
        """Wait for VM to reach expected state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_state, _ = domain.state()
            if current_state == expected_state:
                return
            time.sleep(2)
        
        raise ResourceCreationError(f"VM did not reach expected state within {timeout} seconds")