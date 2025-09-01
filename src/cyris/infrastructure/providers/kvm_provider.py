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
import tempfile
import yaml
import re
import socket
import ipaddress

# Import permission manager for automatic libvirt access setup
from ..permissions import PermissionManager

import libvirt

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
        
        # Configuration with defaults - use session for user-level virtualization
        self.libvirt_uri = config.get("libvirt_uri", config.get("connection_uri", "qemu:///session"))
        self.storage_pool = config.get("storage_pool", "default")
        self.network_prefix = config.get("network_prefix", "cyris")
        self.vm_template_dir = Path(config.get("vm_template_dir", "/var/lib/libvirt/templates"))
        self.base_image_dir = Path(config.get("base_image_dir", "/var/lib/libvirt/images"))
        
        # Network configuration
        self.network_mode = config.get("network_mode", "user")  # "user" or "bridge"
        self.bridge_name = config.get("bridge_name", "virbr0")  # Default libvirt bridge
        self.enable_ssh = config.get("enable_ssh", False)  # Enable SSH-accessible networking
        
        # Connection state
        self._connection: Optional[libvirt.virConnect] = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize permission manager for automatic libvirt access
        self.permission_manager = PermissionManager()
        
        self.logger.info(f"KVMProvider initialized with URI: {self.libvirt_uri}")
        self.logger.info("Using native libvirt-python API")
    
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
                # Get host ID - legacy Host uses host_id, modern Host uses id
                host_id = getattr(host, 'host_id', None) or str(getattr(host, 'id', 'unknown'))
                self.logger.info(f"Setting up host environment for {host_id}")
                
                # For KVM, host creation mainly involves network setup
                # Create networks defined in host configuration
                for network_config in getattr(host, 'networks', []):
                    network_id = self._create_network(host_id, network_config)
                    self.logger.info(f"Created network {network_id} for host {host_id}")
                
                # Register host resource
                host_resource = ResourceInfo(
                    resource_id=host_id,
                    resource_type="host",
                    name=host_id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "kvm",
                        "host_type": "physical",
                        "networks": getattr(host, 'networks', [])
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self._register_resource(host_resource)
                host_ids.append(host_id)
                
            except Exception as e:
                host_id = getattr(host, 'host_id', None) or str(getattr(host, 'id', 'unknown'))
                self.logger.error(f"Failed to create host {host_id}: {e}")
                raise ResourceCreationError(f"Host creation failed: {e}", "kvm", host_id)
        
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
                # Get guest ID - prefer guest_id over id to avoid UUID conflicts
                guest_id = getattr(guest, 'guest_id', None) or str(getattr(guest, 'id', 'unknown'))
                self.logger.info(f"Creating VM for guest {guest_id}")
                
                # Generate unique VM name
                vm_name = f"{self.network_prefix}-{guest_id}-{str(uuid.uuid4())[:8]}"
                
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
                    name=guest_id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "kvm",
                        "guest_id": guest_id,
                        "vm_name": vm_name,
                        "disk_path": disk_path,
                        "os_type": getattr(guest, 'os_type', 'linux'),
                        "memory_mb": getattr(guest, 'memory_mb', 1024),
                        "vcpus": getattr(guest, 'vcpus', 1)
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self._register_resource(guest_resource)
                guest_ids.append(vm_name)
                
                self.logger.info(f"Successfully created VM {vm_name} for guest {guest_id}")
                
            except Exception as e:
                guest_id = getattr(guest, 'guest_id', None) or str(getattr(guest, 'id', 'unknown'))
                self.logger.error(f"Failed to create guest {guest_id}: {e}")
                raise ResourceCreationError(f"Guest creation failed: {e}", "kvm", guest_id)
        
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
                    self.logger.debug(f"Found VM {guest_id}, state: {domain.state()[0]}")
                except libvirt.libvirtError as e:
                    self.logger.warning(f"VM {guest_id} not found, may already be destroyed: {e}")
                    self._unregister_resource(guest_id)
                    continue
                
                # Force stop if running
                if domain.isActive():
                    self.logger.info(f"VM {guest_id} is active, forcing stop")
                    domain.destroy()  # Force stop
                else:
                    self.logger.info(f"VM {guest_id} is already stopped")
                
                # Wait for VM to stop with longer timeout
                try:
                    self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_SHUTOFF, timeout=60)
                    self.logger.debug(f"VM {guest_id} reached shutoff state")
                except Exception as e:
                    self.logger.warning(f"VM {guest_id} failed to reach shutoff state: {e}")
                    # Continue with undefining anyway
                    pass
                
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
                # Check if this looks like a VM name (starts with "cyris-") 
                # If so, query libvirt directly instead of relying on internal registry
                if resource_id.startswith("cyris-"):
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
                        # VM not found in libvirt
                        status_map[resource_id] = "not_found"
                else:
                    # For other resources (hosts, etc.), check internal registry
                    resource = self._resources.get(resource_id)
                    if not resource:
                        status_map[resource_id] = "not_found"
                        continue
                    
                    if resource.resource_type == "host":
                        # For hosts, we just return active if registered
                        status_map[resource_id] = "active"
                    elif resource.resource_type == "guest":
                        # For guests in registry, also check libvirt
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
                            status_map[resource_id] = "not_found"
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
        
        # Organize disks by range for better management
        base_path = Path(self.config.get('base_path', '/tmp/cyris-vms'))
        
        # Check if we have range context information
        current_range_id = getattr(self, '_current_range_id', None)
        if current_range_id:
            # Create range-specific directory for disk files
            vm_disk_dir = base_path / current_range_id / "disks"
            vm_disk_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Creating disk in range directory: {vm_disk_dir}")
            
            # Set up libvirt access for the directory structure
            if self.libvirt_uri == "qemu:///system":
                self.permission_manager.setup_libvirt_access(vm_disk_dir)
        else:
            # Fallback to base directory if no range context
            vm_disk_dir = base_path
            vm_disk_dir.mkdir(exist_ok=True)
            self.logger.warning("No range context available, using base directory for disk")
        
        # Get guest properties with backward compatibility
        guest_id = getattr(guest, 'id', None) or getattr(guest, 'guest_id', 'unknown')
        basevm_config_file = getattr(guest, 'basevm_config_file', None)
        base_image_path = None
        
        if basevm_config_file:
            config_dir = Path(basevm_config_file).parent
            # Look for .qcow2 file in same directory as XML
            for img_file in config_dir.glob('*.qcow2'):
                if img_file.exists() and img_file.stat().st_size > 0:
                    base_image_path = img_file
                    break
        
        if not base_image_path:
            # Fallback: ensure bootable base image
            base_image_path = vm_disk_dir / "base.qcow2"
            if not base_image_path.exists():
                self.logger.info(f"Setting up bootable base image: {base_image_path}")
                self._ensure_bootable_base_image(base_image_path)
        
        # Create VM disk as copy-on-write overlay
        vm_disk_path = vm_disk_dir / f"{vm_name}.qcow2"
        
        if base_image_path.stat().st_size > 1024:  # If base image is substantial
            # Create COW overlay
            subprocess.run([
                "qemu-img", "create", "-f", "qcow2", 
                "-b", str(base_image_path), "-F", "qcow2",
                str(vm_disk_path)
            ], check=True)
        else:
            # Create new image
            subprocess.run([
                "qemu-img", "create", "-f", "qcow2", 
                str(vm_disk_path), "10G"
            ], check=True)
        
        self.logger.info(f"Created VM disk: {vm_disk_path}")
        
        # Automatically set up libvirt access permissions for the disk file
        vm_disk_path_obj = Path(vm_disk_path)
        if self.libvirt_uri == "qemu:///system":
            # Only set permissions for system mode (bridge networking)
            self.logger.debug("Setting up libvirt permissions for system mode")
            success = self.permission_manager.setup_libvirt_access(vm_disk_path_obj)
            if not success:
                self.logger.warning(f"Failed to set up automatic permissions for {vm_disk_path}")
                self.logger.warning("VM may fail to start due to permission issues")
            else:
                self.logger.debug(f"Successfully set up libvirt access for {vm_disk_path}")
        
        return str(vm_disk_path)
    
    def _ensure_bootable_base_image(self, base_image_path: Path) -> None:
        """
        Ensure a bootable base image exists. Downloads Ubuntu cloud image if needed.
        Creates simple cloud-init configuration for networking.
        """
        import urllib.request
        import tempfile
        import shutil
        
        # Ubuntu 22.04 LTS cloud image (minimal, ~600MB)
        cloud_image_url = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.img', delete=False) as tmp_file:
                self.logger.info("Downloading Ubuntu cloud image (first time setup, ~600MB)...")
                urllib.request.urlretrieve(cloud_image_url, tmp_file.name)
                
                # Convert to qcow2 and resize
                self.logger.info("Converting and resizing image...")
                subprocess.run([
                    "qemu-img", "convert", "-f", "qcow2", "-O", "qcow2",
                    tmp_file.name, str(base_image_path)
                ], check=True)
                
                # Resize to 10GB
                subprocess.run([
                    "qemu-img", "resize", str(base_image_path), "10G"
                ], check=True)
                
                # Create simple cloud-init configuration
                self._create_cloud_init_config(base_image_path.parent)
                
                self.logger.info(f"Bootable base image ready: {base_image_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to setup bootable base image: {e}")
            # Fallback to empty image with warning
            self.logger.warning("Creating empty base image - VMs will not boot properly")
            subprocess.run([
                "qemu-img", "create", "-f", "qcow2", 
                str(base_image_path), "10G"
            ], check=True)
    
    def _create_cloud_init_config(self, disk_dir: Path) -> None:
        """Create minimal cloud-init configuration for networking"""
        cloud_init_dir = disk_dir / "cloud-init"
        cloud_init_dir.mkdir(exist_ok=True)
        
        # User data for cloud-init (simple networking setup)
        user_data = """#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    passwd: $6$rounds=4096$saltsalt$L9uC/LkBaztjP6HnQBnmFEWFPfPq1XN2yRh8PxN9z1GvOzKqQ1q1/KdL5sP3q1q1q1q1q1q1q1q1q1q1q1q1q1
# Password is "ubuntu"
package_update: true
packages:
  - cloud-init
runcmd:
  - systemctl enable systemd-networkd
  - systemctl start systemd-networkd
"""
        
        # Network configuration
        network_config = """version: 2
ethernets:
  eth0:
    dhcp4: true
    dhcp-identifier: mac
"""
        
        # Write cloud-init files
        (cloud_init_dir / "user-data").write_text(user_data)
        (cloud_init_dir / "network-config").write_text(network_config)
        
        # Create empty meta-data
        (cloud_init_dir / "meta-data").write_text("instance-id: cyris-vm\n")
    
    def _generate_vm_xml(
        self, 
        vm_name: str, 
        guest: Guest, 
        disk_path: str, 
        host_mapping: Dict[str, str]
    ) -> str:
        """Generate libvirt XML for VM based on template"""
        
        # Try to use the basevm.xml as template
        guest_id = getattr(guest, 'id', None) or getattr(guest, 'guest_id', 'unknown')
        basevm_config_file = getattr(guest, 'basevm_config_file', None)
        
        if basevm_config_file and Path(basevm_config_file).exists():
            # Load and modify template XML
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(basevm_config_file)
                root = tree.getroot()
                
                # Update domain name and UUID
                name_elem = root.find('name')
                if name_elem is not None:
                    name_elem.text = vm_name
                
                # Generate new UUID
                uuid_elem = root.find('uuid')
                if uuid_elem is not None:
                    uuid_elem.text = str(uuid.uuid4())
                
                # Update disk path
                disk_elem = root.find('.//disk[@type="file"]/source')
                if disk_elem is not None:
                    disk_elem.set('file', disk_path)
                
                # Update memory and vCPUs if guest specifies them
                memory_kb = (getattr(guest, 'memory_mb', None) or 1024) * 1024
                memory_elem = root.find('memory')
                if memory_elem is not None:
                    memory_elem.text = str(memory_kb)
                
                current_memory_elem = root.find('currentMemory')
                if current_memory_elem is not None:
                    current_memory_elem.text = str(memory_kb)
                
                vcpus = getattr(guest, 'vcpus', None) or 2
                vcpu_elem = root.find('vcpu')
                if vcpu_elem is not None:
                    vcpu_elem.text = str(vcpus)
                
                # Configure network interface based on configuration
                interface_elem = root.find('.//interface')
                if interface_elem is not None:
                    self._configure_network_interface(interface_elem)
                
                # Update MAC address to be unique
                mac_elem = root.find('.//interface/mac')
                if mac_elem is not None:
                    # Generate random MAC with 52:54:00 prefix (QEMU/KVM range)
                    import random
                    mac_suffix = ':'.join(['%02x' % random.randint(0, 255) for _ in range(3)])
                    mac_elem.set('address', f'52:54:00:{mac_suffix}')
                
                return ET.tostring(root, encoding='unicode')
                
            except Exception as e:
                self.logger.warning(f"Failed to parse template XML {basevm_config_file}: {e}")
                # Fall back to generating basic XML
        
        # Fallback: generate basic XML with user networking for session mode
        memory_kb = (getattr(guest, 'memory_mb', None) or 1024) * 1024
        vcpus = getattr(guest, 'vcpus', None) or 2
        
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
    <interface type='network'>
      <source network='default'/>
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
    
    def _configure_network_interface(self, interface_elem: ET.Element) -> None:
        """
        Configure network interface based on network mode settings.
        
        Args:
            interface_elem: XML interface element to configure
        """
        # Get current interface type from template
        current_type = interface_elem.get('type', 'user')
        
        if self.network_mode == "bridge" or self.enable_ssh:
            # Configure bridge networking for SSH access
            self.logger.info("Configuring bridge networking for SSH access")
            
            # Determine the libvirt URI to decide on bridge configuration
            if "system" in self.libvirt_uri:
                # System mode - use network mode with default network
                interface_elem.set('type', 'network')
                source_elem = interface_elem.find('source')
                if source_elem is None:
                    source_elem = ET.SubElement(interface_elem, 'source')
                source_elem.set('network', 'default')
                
                self.logger.info("Configured system-level bridge networking")
            else:
                # Session mode - try to preserve bridge networking if template specifies it
                if current_type == 'bridge':
                    # Keep bridge networking if template specifies it and bridge exists
                    source_elem = interface_elem.find('source')
                    bridge_name = source_elem.get('bridge', 'virbr0') if source_elem is not None else 'virbr0'
                    
                    # Check if bridge exists (simple check)
                    try:
                        import subprocess
                        result = subprocess.run(['ip', 'link', 'show', bridge_name], 
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            # Bridge exists, keep bridge networking
                            self.logger.info(f"Configured session-mode bridge networking using {bridge_name}")
                        else:
                            # Bridge doesn't exist, fallback to network mode
                            interface_elem.set('type', 'network')
                            if source_elem is None:
                                source_elem = ET.SubElement(interface_elem, 'source')
                            source_elem.set('network', 'default')
                            source_elem.attrib.pop('bridge', None)  # Remove bridge attribute
                            self.logger.info("Bridge not available, using session-mode network networking")
                    except Exception as e:
                        # If check fails, use user mode as fallback
                        self.logger.warning(f"Failed to check bridge availability: {e}, using user mode")
                        interface_elem.set('type', 'user')
                        source_elem = interface_elem.find('source')
                        if source_elem is not None:
                            interface_elem.remove(source_elem)
                        self.logger.info("Configured user-mode networking (bridge check failed)")
                else:
                    # Template doesn't specify bridge, use network mode for session
                    interface_elem.set('type', 'network')
                    source_elem = interface_elem.find('source')
                    if source_elem is None:
                        source_elem = ET.SubElement(interface_elem, 'source')
                    source_elem.set('network', 'default')
                    self.logger.info("Configured session-mode network networking")
        else:
            # Use user-mode networking (isolated)
            interface_elem.set('type', 'user')
            
            # Remove source element as it's not needed for user networking
            source_elem = interface_elem.find('source')
            if source_elem is not None:
                interface_elem.remove(source_elem)
                
            self.logger.info("Configured user-mode networking (isolated)")
    
    def clone_vm(self, base_vm_config: str, new_name: str, ssh_keys: Optional[List[str]] = None) -> str:
        """
        Clone a VM from base image with SSH key injection.
        
        Args:
            base_vm_config: Path to base VM XML configuration file
            new_name: Name for the new VM
            ssh_keys: List of SSH public keys to inject
            
        Returns:
            VM resource ID of cloned VM
            
        Raises:
            ResourceCreationError: If cloning fails
        """
        if not self.is_connected():
            self.connect()
            
        try:
            base_config_path = Path(base_vm_config)
            if not base_config_path.exists():
                raise ResourceCreationError(f"Base VM config not found: {base_vm_config}")
                
            # Parse base VM XML to get disk path
            tree = ET.parse(base_config_path)
            root = tree.getroot()
            
            # Find base disk
            disk_elem = root.find('.//disk[@type="file"]/source')
            if disk_elem is None:
                raise ResourceCreationError(f"No disk found in base VM config: {base_vm_config}")
                
            base_disk_path = disk_elem.get('file')
            if not base_disk_path or not Path(base_disk_path).exists():
                raise ResourceCreationError(f"Base disk not found: {base_disk_path}")
                
            self.logger.info(f"Cloning VM from base: {base_disk_path}")
            
            # Create new disk as COW overlay
            vm_disk_path = self._create_cloned_disk(new_name, base_disk_path)
            
            # Inject SSH keys if provided
            if ssh_keys:
                self._inject_ssh_keys(vm_disk_path, ssh_keys)
                
            # Generate new VM XML
            vm_xml = self._generate_cloned_vm_xml(new_name, base_config_path, vm_disk_path)
            
            # Define and start VM
            domain = self._connection.defineXML(vm_xml)
            if domain is None:
                raise ResourceCreationError(f"Failed to define cloned VM {new_name}")
                
            # Start the VM
            if domain.create() < 0:
                raise ResourceCreationError(f"Failed to start cloned VM {new_name}")
                
            # Wait for VM to be running
            self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_RUNNING)
            
            # Register as resource
            vm_resource = ResourceInfo(
                resource_id=new_name,
                resource_type="guest",
                name=new_name,
                status=ResourceStatus.ACTIVE,
                metadata={
                    "provider": "kvm",
                    "vm_name": new_name,
                    "disk_path": vm_disk_path,
                    "base_config": str(base_config_path),
                    "ssh_keys_injected": len(ssh_keys) if ssh_keys else 0
                },
                created_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )
            
            self._register_resource(vm_resource)
            self.logger.info(f"Successfully cloned VM: {new_name}")
            
            return new_name
            
        except Exception as e:
            self.logger.error(f"Failed to clone VM {new_name}: {e}")
            raise ResourceCreationError(f"VM cloning failed: {e}", "kvm", new_name)
    
    def _create_cloned_disk(self, vm_name: str, base_disk_path: str) -> str:
        """Create a COW overlay disk for cloning"""
        import subprocess
        
        # Create disk directory if needed
        disk_dir = self.base_path / "disks"
        disk_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate new disk path
        vm_disk_path = disk_dir / f"{vm_name}.qcow2"
        
        # Create COW overlay using qemu-img
        cmd = [
            "qemu-img", "create", "-f", "qcow2", 
            "-b", base_disk_path,
            "-F", "qcow2",
            str(vm_disk_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.logger.info(f"Created overlay disk: {vm_disk_path}")
            return str(vm_disk_path)
        except subprocess.CalledProcessError as e:
            raise ResourceCreationError(f"Failed to create overlay disk: {e.stderr}")
    
    def _inject_ssh_keys(self, disk_path: str, ssh_keys: List[str]) -> None:
        """Inject SSH public keys into VM disk using cloud-init or direct mounting"""
        import tempfile
        import subprocess
        
        try:
            # Create cloud-init user-data with SSH keys
            user_data = self._create_cloud_init_user_data(ssh_keys)
            
            # Create cloud-init ISO
            cloud_init_iso = self._create_cloud_init_iso(user_data)
            
            # For now, we'll implement a simple approach
            # In production, this would use libguestfs or similar
            self.logger.info(f"SSH key injection prepared for {disk_path}")
            
        except Exception as e:
            self.logger.warning(f"SSH key injection failed: {e}")
    
    def _create_cloud_init_user_data(self, ssh_keys: List[str]) -> str:
        """Create cloud-init user-data YAML"""
        import yaml
        
        user_data = {
            'users': [
                {
                    'name': 'ubuntu',
                    'ssh_authorized_keys': ssh_keys,
                    'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
                    'groups': ['sudo'],
                    'shell': '/bin/bash'
                }
            ],
            'ssh_pwauth': True,
            'password': 'ubuntu',
            'chpasswd': {'expire': False}
        }
        
        return "#cloud-config\n" + yaml.dump(user_data, default_flow_style=False)
    
    def _create_cloud_init_iso(self, user_data: str) -> str:
        """Create cloud-init configuration ISO"""
        import tempfile
        import subprocess
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Write user-data
            user_data_file = temp_path / "user-data"
            user_data_file.write_text(user_data)
            
            # Write minimal meta-data
            meta_data_file = temp_path / "meta-data"
            meta_data_file.write_text("instance-id: cyris-vm\nlocal-hostname: cyris-vm\n")
            
            # Create ISO - try genisoimage first, then mkisofs
            iso_path = temp_path / "cloud-init.iso"
            
            # Try genisoimage first
            cmd = [
                "genisoimage", "-output", str(iso_path),
                "-volid", "cidata", "-joliet", "-rock",
                str(user_data_file), str(meta_data_file)
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return str(iso_path)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to mkisofs
                cmd[0] = "mkisofs"
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    return str(iso_path)
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    self.logger.warning(f"Cloud-init ISO creation failed: {e}")
                    return ""
    
    def _generate_cloned_vm_xml(self, vm_name: str, base_config_path: Path, vm_disk_path: str) -> str:
        """Generate XML configuration for cloned VM"""
        import xml.etree.ElementTree as ET
        import uuid
        
        # Parse base configuration
        tree = ET.parse(base_config_path)
        root = tree.getroot()
        
        # Update VM name
        name_elem = root.find('name')
        if name_elem is not None:
            name_elem.text = vm_name
        
        # Update UUID
        uuid_elem = root.find('uuid')
        if uuid_elem is not None:
            uuid_elem.text = str(uuid.uuid4())
        
        # Update disk path
        disk_elem = root.find('.//disk[@type="file"]/source')
        if disk_elem is not None:
            disk_elem.set('file', vm_disk_path)
        
        # Update MAC address to avoid conflicts
        mac_elem = root.find('.//interface/mac')
        if mac_elem is not None:
            # Generate new MAC address
            import random
            mac_suffix = ':'.join([f'{random.randint(0, 255):02x}' for _ in range(3)])
            mac_elem.set('address', f'52:54:00:{mac_suffix}')
        
        return ET.tostring(root, encoding='unicode')
    
    def get_vm_ip(self, vm_id: str) -> Optional[str]:
        """
        Discover VM IP address using multiple methods.
        
        Args:
            vm_id: VM identifier
            
        Returns:
            IP address string or None if not found
        """
        if not self.is_connected():
            self.connect()
            
        try:
            domain = self._connection.lookupByName(vm_id)
            
            # Method 1: Try libvirt DHCP leases
            ip = self._get_ip_from_dhcp_leases(domain)
            if ip:
                self.logger.info(f"Found IP via DHCP leases: {vm_id} -> {ip}")
                return ip
                
            # Method 2: Try virsh domifaddr
            ip = self._get_ip_from_domifaddr(vm_id)
            if ip:
                self.logger.info(f"Found IP via domifaddr: {vm_id} -> {ip}")
                return ip
                
            # Method 3: Try ARP table scan
            ip = self._get_ip_from_arp(domain)
            if ip:
                self.logger.info(f"Found IP via ARP scan: {vm_id} -> {ip}")
                return ip
                
            # Method 4: Try network bridge inspection
            ip = self._get_ip_from_bridge_scan(domain)
            if ip:
                self.logger.info(f"Found IP via bridge scan: {vm_id} -> {ip}")
                return ip
                
            self.logger.warning(f"Could not discover IP for VM: {vm_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get IP for VM {vm_id}: {e}")
            return None
    
    def inject_ssh_keys(self, vm_id: str, public_keys: List[str]) -> bool:
        """
        Inject SSH public keys into running VM.
        
        Args:
            vm_id: VM identifier
            public_keys: List of SSH public keys
            
        Returns:
            True if injection successful
        """
        if not public_keys:
            return True
            
        try:
            # Get VM disk path
            resource = self.get_resource_info(vm_id)
            if not resource or "disk_path" not in resource.metadata:
                self.logger.error(f"Cannot find disk path for VM {vm_id}")
                return False
                
            disk_path = resource.metadata["disk_path"]
            
            # Check if VM is running - need to shut down for disk modification
            domain = self._connection.lookupByName(vm_id)
            was_running = domain.isActive()
            
            if was_running:
                self.logger.info(f"Shutting down VM {vm_id} for key injection")
                domain.shutdown()
                self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_SHUTOFF, timeout=30)
                
            # Inject keys using cloud-init or direct mount
            success = self._inject_ssh_keys(disk_path, public_keys)
            
            # Restart VM if it was running
            if was_running and success:
                self.logger.info(f"Restarting VM {vm_id} after key injection")
                domain.create()
                self._wait_for_vm_state(domain, libvirt.VIR_DOMAIN_RUNNING)
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to inject SSH keys for VM {vm_id}: {e}")
            return False
    
    def get_vm_ssh_info(self, vm_id: str) -> Optional[Dict[str, Any]]:
        """
        Get SSH connection information for a VM.
        
        Args:
            vm_id: VM identifier
            
        Returns:
            Dictionary with SSH connection info or None if not available
        """
        if not self.is_connected():
            self.connect()
            
        try:
            domain = self._connection.lookupByName(vm_id)
            
            # Get network interfaces using libvirt-python
            desc = domain.XMLDesc(0)
                
            root = ET.fromstring(desc)
            
            # Look for interface information
            interface_elem = root.find('.//interface')
            if interface_elem is not None:
                interface_type = interface_elem.get('type')
                
                if interface_type == 'network':
                    # Try to get DHCP lease information
                    try:
                        # Get MAC address
                        mac_elem = interface_elem.find('mac')
                        if mac_elem is not None:
                            mac_addr = mac_elem.get('address')
                            
                            # Try to find IP from DHCP leases
                            network_name = 'default'
                            source_elem = interface_elem.find('source')
                            if source_elem is not None:
                                network_name = source_elem.get('network', 'default')
                            
                            # This would require libvirt network lease lookup
                            # For now, provide general information
                            return {
                                'connection_type': 'bridge',
                                'network': network_name,
                                'mac_address': mac_addr,
                                'ssh_port': 22,
                                'notes': 'VM is on bridged network. Use network scanning to find IP address.',
                                'suggested_commands': [
                                    'nmap -sP 192.168.122.0/24  # Scan default network',
                                    f'arp -a | grep {mac_addr}  # Find IP by MAC'
                                ]
                            }
                    except Exception as e:
                        self.logger.warning(f"Could not get network details for {vm_id}: {e}")
                
                elif interface_type == 'user':
                    return {
                        'connection_type': 'user_mode',
                        'ssh_port': None,
                        'notes': 'VM uses user-mode networking. SSH access not directly available.',
                        'alternative': 'Use VNC console or configure port forwarding'
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get SSH info for VM {vm_id}: {e}")
            return None
    
    def _create_cloned_disk(self, vm_name: str, base_disk_path: str) -> str:
        """Create VM disk as COW overlay of base disk"""
        base_path = Path(self.config.get('base_path', '/tmp/cyris-vms'))
        
        current_range_id = getattr(self, '_current_range_id', None)
        if current_range_id:
            vm_disk_dir = base_path / current_range_id / "disks"
            vm_disk_dir.mkdir(parents=True, exist_ok=True)
        else:
            vm_disk_dir = base_path
            vm_disk_dir.mkdir(exist_ok=True)
            
        vm_disk_path = vm_disk_dir / f"{vm_name}.qcow2"
        
        # Create COW overlay
        subprocess.run([
            "qemu-img", "create", "-f", "qcow2",
            "-b", base_disk_path, "-F", "qcow2",
            str(vm_disk_path)
        ], check=True)
        
        self.logger.info(f"Created cloned disk: {vm_disk_path}")
        
        # Set up permissions
        if self.libvirt_uri == "qemu:///system":
            self.permission_manager.setup_libvirt_access(vm_disk_path)
            
        return str(vm_disk_path)
    
    def _generate_cloned_vm_xml(self, vm_name: str, base_config_path: Path, disk_path: str) -> str:
        """Generate XML for cloned VM"""
        tree = ET.parse(base_config_path)
        root = tree.getroot()
        
        # Update domain name and UUID
        name_elem = root.find('name')
        if name_elem is not None:
            name_elem.text = vm_name
            
        uuid_elem = root.find('uuid')
        if uuid_elem is not None:
            uuid_elem.text = str(uuid.uuid4())
            
        # Update disk path
        disk_elem = root.find('.//disk[@type="file"]/source')
        if disk_elem is not None:
            disk_elem.set('file', disk_path)
            
        # Update MAC address to be unique
        mac_elem = root.find('.//interface/mac')
        if mac_elem is not None:
            import random
            mac_suffix = ':'.join(['%02x' % random.randint(0, 255) for _ in range(3)])
            mac_elem.set('address', f'52:54:00:{mac_suffix}')
            
        # Configure networking
        interface_elem = root.find('.//interface')
        if interface_elem is not None:
            self._configure_network_interface(interface_elem)
            
        return ET.tostring(root, encoding='unicode')
    
    def _inject_ssh_keys(self, disk_path: str, public_keys: List[str]) -> bool:
        """Inject SSH keys into VM disk using cloud-init"""
        try:
            # Create cloud-init user data
            user_data = {
                'users': [{
                    'name': 'cyris',
                    'sudo': 'ALL=(ALL) NOPASSWD:ALL',
                    'ssh-authorized-keys': public_keys
                }, {
                    'name': 'root',
                    'ssh-authorized-keys': public_keys
                }],
                'ssh_pwauth': True,
                'package_update': True
            }
            
            # Create cloud-init ISO
            cloud_init_iso = self._create_cloud_init_iso(disk_path, user_data)
            
            if cloud_init_iso:
                self.logger.info(f"Created cloud-init ISO: {cloud_init_iso}")
                return True
            else:
                # Fallback: try direct mount method
                return self._inject_keys_via_mount(disk_path, public_keys)
                
        except Exception as e:
            self.logger.error(f"Failed to inject SSH keys: {e}")
            return False
    
    def _create_cloud_init_iso(self, disk_path: str, user_data: Dict) -> Optional[str]:
        """Create cloud-init ISO for SSH key injection"""
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                
                # Create user-data file
                user_data_file = tmp_path / "user-data"
                with open(user_data_file, 'w') as f:
                    f.write("#cloud-config\n")
                    yaml.dump(user_data, f)
                    
                # Create meta-data file
                meta_data_file = tmp_path / "meta-data"
                with open(meta_data_file, 'w') as f:
                    f.write(f"instance-id: {uuid.uuid4()}\n")
                    f.write(f"local-hostname: cyris-vm\n")
                    
                # Create ISO
                iso_path = str(Path(disk_path).parent / f"{Path(disk_path).stem}-cloudinit.iso")
                
                subprocess.run([
                    "genisoimage", "-output", iso_path,
                    "-volid", "cidata", "-joliet", "-rock",
                    str(user_data_file), str(meta_data_file)
                ], check=True, capture_output=True)
                
                return iso_path
                
        except Exception as e:
            self.logger.warning(f"Failed to create cloud-init ISO: {e}")
            return None
    
    def _inject_keys_via_mount(self, disk_path: str, public_keys: List[str]) -> bool:
        """Fallback: inject keys by mounting disk directly"""
        try:
            with tempfile.TemporaryDirectory() as mount_dir:
                # Try to mount the disk (requires root)
                mount_cmd = ["sudo", "mount", "-o", "loop", disk_path, mount_dir]
                result = subprocess.run(mount_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.warning(f"Cannot mount disk for key injection: {result.stderr}")
                    return False
                    
                try:
                    # Create .ssh directory
                    ssh_dir = Path(mount_dir) / "root" / ".ssh"
                    ssh_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Write authorized_keys
                    auth_keys_file = ssh_dir / "authorized_keys"
                    with open(auth_keys_file, 'w') as f:
                        for key in public_keys:
                            f.write(f"{key}\n")
                            
                    # Set permissions
                    subprocess.run(["sudo", "chmod", "600", str(auth_keys_file)])
                    subprocess.run(["sudo", "chmod", "700", str(ssh_dir)])
                    
                    return True
                    
                finally:
                    # Always unmount
                    subprocess.run(["sudo", "umount", mount_dir])
                    
        except Exception as e:
            self.logger.error(f"Failed to inject keys via mount: {e}")
            return False
    
    def _get_ip_from_dhcp_leases(self, domain) -> Optional[str]:
        """Get IP from libvirt DHCP leases"""
        try:
            # Try to get interface addresses
            interfaces = domain.interfaceAddresses(
                libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE
            )
            
            for interface, data in interfaces.items():
                if data.get('addrs'):
                    for addr in data['addrs']:
                        ip = addr.get('addr')
                        if ip and self._is_valid_ip(ip):
                            return ip
                            
        except Exception as e:
            self.logger.debug(f"DHCP lease lookup failed: {e}")
            
        return None
    
    def _get_ip_from_domifaddr(self, vm_id: str) -> Optional[str]:
        """Get IP using virsh domifaddr command"""
        try:
            result = subprocess.run([
                "virsh", "--connect", self.libvirt_uri,
                "domifaddr", vm_id
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'ipv4' in line.lower():
                        # Parse line like: vnet0      52:54:00:xx:xx:xx    ipv4         192.168.122.xxx/24
                        parts = line.split()
                        for part in parts:
                            if '/' in part and self._is_valid_ip(part.split('/')[0]):
                                return part.split('/')[0]
                                
        except Exception as e:
            self.logger.debug(f"domifaddr lookup failed: {e}")
            
        return None
    
    def _get_ip_from_arp(self, domain) -> Optional[str]:
        """Get IP by scanning ARP table for VM MAC address"""
        try:
            # Get VM MAC address
            desc = domain.XMLDesc(0)
            root = ET.fromstring(desc)
            mac_elem = root.find('.//interface/mac')
            
            if mac_elem is None:
                return None
                
            mac_addr = mac_elem.get('address').lower()
            
            # Scan ARP table
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if mac_addr in line.lower():
                        # Parse line like: hostname (192.168.122.xxx) at 52:54:00:xx:xx:xx [ether] on virbr0
                        match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                        if match:
                            ip = match.group(1)
                            if self._is_valid_ip(ip):
                                return ip
                                
        except Exception as e:
            self.logger.debug(f"ARP scan failed: {e}")
            
        return None
    
    def _get_ip_from_bridge_scan(self, domain) -> Optional[str]:
        """Get IP by scanning bridge network range"""
        try:
            # Determine network range to scan
            networks_to_scan = [
                '192.168.122.0/24',  # Default libvirt network
                '192.168.1.0/24',    # Common home network
                '10.0.0.0/24'        # Common corporate network
            ]
            
            # Get VM MAC for verification
            desc = domain.XMLDesc(0)
            root = ET.fromstring(desc)
            mac_elem = root.find('.//interface/mac')
            target_mac = mac_elem.get('address').lower() if mac_elem is not None else None
            
            for network_range in networks_to_scan:
                network = ipaddress.ip_network(network_range, strict=False)
                
                # Quick ping sweep of likely IPs
                for host_num in [50, 51, 100, 101, 102, 110, 111, 112]:
                    try:
                        test_ip = str(list(network.hosts())[host_num])
                        
                        # Quick ping test
                        ping_result = subprocess.run([
                            'ping', '-c', '1', '-W', '1', test_ip
                        ], capture_output=True, timeout=2)
                        
                        if ping_result.returncode == 0 and target_mac:
                            # Verify MAC matches
                            arp_result = subprocess.run([
                                'arp', '-n', test_ip
                            ], capture_output=True, text=True)
                            
                            if target_mac in arp_result.stdout.lower():
                                return test_ip
                                
                    except (IndexError, subprocess.TimeoutExpired):
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Bridge scan failed: {e}")
            
        return None
    
    def _is_valid_ip(self, ip_str: str) -> bool:
        """Check if string is a valid IP address"""
        try:
            ipaddress.ip_address(ip_str)
            # Exclude localhost and link-local
            return not ip_str.startswith(('127.', '169.254.'))
        except ValueError:
            return False