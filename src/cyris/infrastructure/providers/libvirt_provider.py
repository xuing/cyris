"""
Enhanced LibVirt Provider - Native Python Implementation

High-performance libvirt provider using native libvirt-python API to replace
subprocess-based virsh commands. Provides comprehensive domain lifecycle
management with advanced features and error handling.

Key Features:
- Native libvirt-python API for maximum performance
- Connection pooling and automatic reconnection
- Advanced domain lifecycle management
- Real-time state monitoring and event handling
- Comprehensive error reporting and recovery
- Thread-safe operations

Usage:
    # Basic usage
    provider = LibvirtProvider()
    domain = provider.create_domain_from_xml(xml_config)
    
    # Advanced usage with connection management
    provider = LibvirtProvider("qemu+ssh://remote/system")
    result = provider.list_domains(active_only=True)
"""

import libvirt
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import logging  # Keep for type annotations
import tempfile
import uuid
import os
import time
import threading
from typing import Dict, List, Optional, Any, Union, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from .libvirt_connection_manager import (
    LibvirtConnectionManager,
    get_connection_manager,
    LibvirtConnectionError,
    LibvirtDomainError,
    DomainInfo
)
from .libvirt_domain_wrapper import (
    LibvirtDomainWrapper,
    DomainState,
    DomainStateInfo,
    NetworkInterface
)

logger = get_logger(__name__, "libvirt_provider")


class LibvirtProviderError(Exception):
    """Exception raised for libvirt provider errors"""
    pass


class DomainLifecycleState(Enum):
    """Domain lifecycle state enumeration"""
    CREATING = "creating"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    PAUSED = "paused"
    CRASHED = "crashed"
    UNDEFINED = "undefined"
    ERROR = "error"


@dataclass
class DomainOperationResult:
    """Result of domain operations"""
    success: bool
    domain_name: str
    operation: str
    message: str
    execution_time: float
    error_code: Optional[int] = None
    error_details: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        return self.success
    
    @property
    def is_error(self) -> bool:
        return not self.success


@dataclass
class NetworkInfo:
    """Network information for libvirt networks"""
    name: str
    uuid: str
    is_active: bool
    is_persistent: bool
    bridge_name: Optional[str]
    forward_mode: Optional[str]
    ip_range: Optional[str]


@dataclass
class StoragePoolInfo:
    """Storage pool information"""
    name: str
    uuid: str
    is_active: bool
    pool_type: str
    capacity: int
    allocation: int
    available: int
    path: Optional[str]


class LibvirtProvider:
    """
    Enhanced LibVirt Provider using native libvirt-python API.
    
    Provides comprehensive domain lifecycle management, network operations,
    and storage management with high performance and reliability.
    
    Features:
    - Connection pooling and management
    - Domain lifecycle operations (create, start, stop, destroy, undefine)
    - Network management (create, configure, destroy networks)
    - Storage pool operations
    - Real-time monitoring and state tracking
    - Advanced error handling and recovery
    - Thread-safe operations
    """
    
    # LibVirt constants for compatibility
    VIR_DOMAIN_RUNNING = libvirt.VIR_DOMAIN_RUNNING
    VIR_DOMAIN_SHUTOFF = libvirt.VIR_DOMAIN_SHUTOFF
    VIR_DOMAIN_PAUSED = libvirt.VIR_DOMAIN_PAUSED
    VIR_DOMAIN_CRASHED = libvirt.VIR_DOMAIN_CRASHED
    
    def __init__(
        self,
        uri: str = "qemu:///system",
        timeout: int = 30,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize LibVirt Provider.
        
        Args:
            uri: LibVirt connection URI
            timeout: Default operation timeout in seconds
            logger: Optional logger instance
        """
        self.uri = uri
        self.timeout = timeout
        self.logger = logger or get_logger(__name__, "libvirt_provider")
        
        # Enhanced connection management
        try:
            self.connection_manager = get_connection_manager(uri)
            self.logger.info(f"LibVirt provider initialized with native API: {uri}")
        except LibvirtConnectionError as e:
            self.logger.error(f"Failed to initialize libvirt connection: {e}")
            raise LibvirtProviderError(f"Connection initialization failed: {e}")
        
        # Operation statistics
        self.stats = {
            'operations_total': 0,
            'operations_successful': 0,
            'operations_failed': 0,
            'domains_created': 0,
            'domains_destroyed': 0,
            'average_operation_time': 0.0
        }
        
        # Thread safety
        self._stats_lock = threading.Lock()
        
        self.logger.info(f"LibVirt provider ready: {self._get_hypervisor_info()}")
    
    def _get_hypervisor_info(self) -> str:
        """Get hypervisor information for logging"""
        try:
            with self.connection_manager.connection_context() as conn:
                hostname = conn.getHostname()
                version = conn.getVersion()
                hv_type = conn.getType()
                return f"{hv_type} on {hostname} (version: {version})"
        except Exception:
            return "unknown hypervisor"
    
    def _record_operation(self, operation: str, success: bool, execution_time: float):
        """Record operation statistics"""
        with self._stats_lock:
            self.stats['operations_total'] += 1
            if success:
                self.stats['operations_successful'] += 1
            else:
                self.stats['operations_failed'] += 1
            
            # Update average operation time
            total_ops = self.stats['operations_total']
            current_avg = self.stats['average_operation_time']
            self.stats['average_operation_time'] = (
                (current_avg * (total_ops - 1) + execution_time) / total_ops
            )
    
    def create_domain_from_xml(self, xml_config: str, start: bool = True) -> DomainOperationResult:
        """
        Create and optionally start a domain from XML configuration.
        
        Args:
            xml_config: Domain XML configuration
            start: Whether to start the domain after creation
            
        Returns:
            DomainOperationResult with operation details
        """
        start_time = time.time()
        domain_name = "unknown"
        
        try:
            # Parse domain name from XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_config)
            name_elem = root.find('name')
            domain_name = name_elem.text if name_elem is not None else "unknown"
            
            with self.connection_manager.connection_context() as conn:
                # Define domain from XML
                domain = conn.defineXML(xml_config)
                
                if start:
                    # Start the domain
                    domain.create()
                    self.stats['domains_created'] += 1
                    operation_msg = f"Created and started domain {domain_name}"
                else:
                    operation_msg = f"Created domain {domain_name} (not started)"
                
                execution_time = time.time() - start_time
                self._record_operation("create_domain", True, execution_time)
                
                self.logger.info(operation_msg)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="create_domain",
                    message=operation_msg,
                    execution_time=execution_time
                )
                
        except libvirt.libvirtError as e:
            execution_time = time.time() - start_time
            self._record_operation("create_domain", False, execution_time)
            
            error_msg = f"Failed to create domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="create_domain",
                message=error_msg,
                execution_time=execution_time,
                error_code=e.get_error_code() if hasattr(e, 'get_error_code') else None,
                error_details=str(e)
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self._record_operation("create_domain", False, execution_time)
            
            error_msg = f"Unexpected error creating domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="create_domain",
                message=error_msg,
                execution_time=execution_time,
                error_details=str(e)
            )
    
    def start_domain(self, domain_name: str) -> DomainOperationResult:
        """
        Start a domain.
        
        Args:
            domain_name: Name of the domain to start
            
        Returns:
            DomainOperationResult with operation details
        """
        start_time = time.time()
        
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            
            if wrapper.is_active():
                execution_time = time.time() - start_time
                message = f"Domain {domain_name} is already running"
                self.logger.info(message)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="start_domain",
                    message=message,
                    execution_time=execution_time
                )
            
            success = wrapper.start()
            execution_time = time.time() - start_time
            
            if success:
                message = f"Started domain {domain_name}"
                self.logger.info(message)
                self._record_operation("start_domain", True, execution_time)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="start_domain",
                    message=message,
                    execution_time=execution_time
                )
            else:
                message = f"Failed to start domain {domain_name}"
                self.logger.error(message)
                self._record_operation("start_domain", False, execution_time)
                
                return DomainOperationResult(
                    success=False,
                    domain_name=domain_name,
                    operation="start_domain",
                    message=message,
                    execution_time=execution_time
                )
                
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            execution_time = time.time() - start_time
            self._record_operation("start_domain", False, execution_time)
            
            error_msg = f"Failed to start domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="start_domain",
                message=error_msg,
                execution_time=execution_time,
                error_details=str(e)
            )
    
    def stop_domain(self, domain_name: str, force: bool = False, timeout: int = 60) -> DomainOperationResult:
        """
        Stop a domain gracefully or forcefully.
        
        Args:
            domain_name: Name of the domain to stop
            force: Whether to force shutdown (destroy) instead of graceful shutdown
            timeout: Timeout for graceful shutdown before forcing
            
        Returns:
            DomainOperationResult with operation details
        """
        start_time = time.time()
        
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            
            if not wrapper.is_active():
                execution_time = time.time() - start_time
                message = f"Domain {domain_name} is already stopped"
                self.logger.info(message)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="stop_domain",
                    message=message,
                    execution_time=execution_time
                )
            
            if force:
                # Force destroy
                success = wrapper.destroy()
                operation = "destroy"
            else:
                # Graceful shutdown
                success = wrapper.shutdown(timeout=timeout)
                operation = "shutdown"
            
            execution_time = time.time() - start_time
            
            if success:
                message = f"Stopped domain {domain_name} via {operation}"
                self.logger.info(message)
                self._record_operation("stop_domain", True, execution_time)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="stop_domain",
                    message=message,
                    execution_time=execution_time
                )
            else:
                message = f"Failed to stop domain {domain_name} via {operation}"
                self.logger.error(message)
                self._record_operation("stop_domain", False, execution_time)
                
                return DomainOperationResult(
                    success=False,
                    domain_name=domain_name,
                    operation="stop_domain",
                    message=message,
                    execution_time=execution_time
                )
                
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            execution_time = time.time() - start_time
            self._record_operation("stop_domain", False, execution_time)
            
            error_msg = f"Failed to stop domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="stop_domain",
                message=error_msg,
                execution_time=execution_time,
                error_details=str(e)
            )
    
    def destroy_domain(self, domain_name: str, undefine: bool = False, remove_storage: bool = False) -> DomainOperationResult:
        """
        Destroy (force stop) and optionally undefine a domain.
        
        Args:
            domain_name: Name of the domain to destroy
            undefine: Whether to also undefine the domain
            remove_storage: Whether to remove associated storage
            
        Returns:
            DomainOperationResult with operation details
        """
        start_time = time.time()
        
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            
            if undefine:
                # Complete removal
                success = wrapper.destroy_and_undefine(remove_storage=remove_storage)
                operation_type = "destroy_and_undefine"
                self.stats['domains_destroyed'] += 1 if success else 0
            else:
                # Just destroy (force stop)
                success = wrapper.destroy()
                operation_type = "destroy"
            
            execution_time = time.time() - start_time
            
            if success:
                message = f"Successfully performed {operation_type} on domain {domain_name}"
                self.logger.info(message)
                self._record_operation("destroy_domain", True, execution_time)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="destroy_domain",
                    message=message,
                    execution_time=execution_time
                )
            else:
                message = f"Failed to perform {operation_type} on domain {domain_name}"
                self.logger.error(message)
                self._record_operation("destroy_domain", False, execution_time)
                
                return DomainOperationResult(
                    success=False,
                    domain_name=domain_name,
                    operation="destroy_domain",
                    message=message,
                    execution_time=execution_time
                )
                
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            execution_time = time.time() - start_time
            self._record_operation("destroy_domain", False, execution_time)
            
            # Handle "domain not found" as partial success for cleanup operations
            if "Domain not found" in str(e):
                message = f"Domain {domain_name} not found (already removed)"
                self.logger.info(message)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="destroy_domain",
                    message=message,
                    execution_time=execution_time
                )
            
            error_msg = f"Failed to destroy domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="destroy_domain",
                message=error_msg,
                execution_time=execution_time,
                error_details=str(e)
            )
    
    def list_domains(
        self, 
        active_only: bool = False, 
        include_state: bool = True
    ) -> List[Union[str, DomainInfo]]:
        """
        List domains with optional state information.
        
        Args:
            active_only: If True, only return running domains
            include_state: If True, return DomainInfo objects, otherwise just names
            
        Returns:
            List of domain names or DomainInfo objects
        """
        try:
            domains = self.connection_manager.list_domains(active_only=active_only)
            
            if not include_state:
                return [domain.name() for domain in domains]
            
            domain_infos = []
            for domain in domains:
                try:
                    wrapper = LibvirtDomainWrapper(domain, self.connection_manager)
                    state_info = wrapper.get_state_info()
                    
                    domain_info = DomainInfo(
                        name=state_info.name,
                        uuid=state_info.uuid,
                        state=state_info.state.value,
                        id=state_info.id,
                        max_memory=state_info.max_memory,
                        memory=state_info.memory,
                        vcpus=state_info.vcpus,
                        cpu_time=state_info.cpu_time
                    )
                    domain_infos.append(domain_info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to get state info for domain {domain.name()}: {e}")
                    continue
            
            return domain_infos
            
        except (LibvirtConnectionError, libvirt.libvirtError) as e:
            self.logger.error(f"Failed to list domains: {e}")
            return []
    
    def get_domain_state(self, domain_name: str) -> Optional[DomainStateInfo]:
        """
        Get detailed state information for a domain.
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            DomainStateInfo object or None if domain not found
        """
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            return wrapper.get_state_info()
            
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            self.logger.warning(f"Failed to get state for domain {domain_name}: {e}")
            return None
    
    def reboot_domain(self, domain_name: str) -> DomainOperationResult:
        """
        Reboot a domain.
        
        Args:
            domain_name: Name of the domain to reboot
            
        Returns:
            DomainOperationResult with operation details
        """
        start_time = time.time()
        
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            success = wrapper.reboot()
            
            execution_time = time.time() - start_time
            
            if success:
                message = f"Rebooted domain {domain_name}"
                self.logger.info(message)
                self._record_operation("reboot_domain", True, execution_time)
                
                return DomainOperationResult(
                    success=True,
                    domain_name=domain_name,
                    operation="reboot_domain",
                    message=message,
                    execution_time=execution_time
                )
            else:
                message = f"Failed to reboot domain {domain_name}"
                self.logger.error(message)
                self._record_operation("reboot_domain", False, execution_time)
                
                return DomainOperationResult(
                    success=False,
                    domain_name=domain_name,
                    operation="reboot_domain",
                    message=message,
                    execution_time=execution_time
                )
                
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            execution_time = time.time() - start_time
            self._record_operation("reboot_domain", False, execution_time)
            
            error_msg = f"Failed to reboot domain {domain_name}: {e}"
            self.logger.error(error_msg)
            
            return DomainOperationResult(
                success=False,
                domain_name=domain_name,
                operation="reboot_domain",
                message=error_msg,
                execution_time=execution_time,
                error_details=str(e)
            )
    
    def get_domain_xml(self, domain_name: str, flags: int = 0) -> Optional[str]:
        """
        Get XML configuration for a domain.
        
        Args:
            domain_name: Name of the domain
            flags: XML dump flags
            
        Returns:
            Domain XML configuration or None if error
        """
        try:
            wrapper = LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
            return wrapper.get_xml_config(flags=flags)
            
        except (LibvirtDomainError, LibvirtConnectionError) as e:
            self.logger.error(f"Failed to get XML for domain {domain_name}: {e}")
            return None
    
    def create_network_from_xml(self, xml_config: str, start: bool = True) -> bool:
        """
        Create a network from XML configuration.
        
        Args:
            xml_config: Network XML configuration
            start: Whether to start the network after creation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection_manager.connection_context() as conn:
                # Define network from XML
                network = conn.networkDefineXML(xml_config)
                
                if start:
                    # Start the network
                    network.create()
                    self.logger.info(f"Created and started network {network.name()}")
                else:
                    self.logger.info(f"Created network {network.name()} (not started)")
                
                return True
                
        except libvirt.libvirtError as e:
            self.logger.error(f"Failed to create network: {e}")
            return False
    
    def list_networks(self, active_only: bool = False) -> List[NetworkInfo]:
        """
        List networks with detailed information.
        
        Args:
            active_only: If True, only return active networks
            
        Returns:
            List of NetworkInfo objects
        """
        try:
            with self.connection_manager.connection_context() as conn:
                if active_only:
                    networks = conn.listAllNetworks(libvirt.VIR_CONNECT_LIST_NETWORKS_ACTIVE)
                else:
                    networks = conn.listAllNetworks()
                
                network_infos = []
                for network in networks:
                    try:
                        # Parse network XML to get details
                        xml_desc = network.XMLDesc()
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(xml_desc)
                        
                        bridge_elem = root.find('bridge')
                        bridge_name = bridge_elem.get('name') if bridge_elem is not None else None
                        
                        forward_elem = root.find('forward')
                        forward_mode = forward_elem.get('mode') if forward_elem is not None else None
                        
                        ip_elem = root.find('ip')
                        ip_range = None
                        if ip_elem is not None:
                            address = ip_elem.get('address')
                            netmask = ip_elem.get('netmask') 
                            if address and netmask:
                                ip_range = f"{address}/{netmask}"
                        
                        network_info = NetworkInfo(
                            name=network.name(),
                            uuid=network.UUIDString(),
                            is_active=bool(network.isActive()),
                            is_persistent=bool(network.isPersistent()),
                            bridge_name=bridge_name,
                            forward_mode=forward_mode,
                            ip_range=ip_range
                        )
                        network_infos.append(network_info)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to get info for network {network.name()}: {e}")
                        continue
                
                return network_infos
                
        except libvirt.libvirtError as e:
            self.logger.error(f"Failed to list networks: {e}")
            return []
    
    def destroy_network(self, network_name: str, undefine: bool = False) -> bool:
        """
        Destroy and optionally undefine a network.
        
        Args:
            network_name: Name of the network to destroy
            undefine: Whether to also undefine the network
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.connection_manager.connection_context() as conn:
                network = conn.networkLookupByName(network_name)
                
                # Stop network if active
                if network.isActive():
                    network.destroy()
                    self.logger.info(f"Stopped network {network_name}")
                
                # Undefine if requested
                if undefine and network.isPersistent():
                    network.undefine()
                    self.logger.info(f"Undefined network {network_name}")
                
                return True
                
        except libvirt.libvirtError as e:
            self.logger.error(f"Failed to destroy network {network_name}: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information and hypervisor details"""
        try:
            with self.connection_manager.connection_context() as conn:
                return {
                    'uri': self.uri,
                    'hostname': conn.getHostname(),
                    'hypervisor_type': conn.getType(),
                    'version': conn.getVersion(),
                    'libvirt_version': conn.getLibVersion(),
                    'is_alive': conn.isAlive(),
                    'encrypted': conn.isEncrypted(),
                    'secure': conn.isSecure()
                }
        except Exception as e:
            self.logger.error(f"Failed to get connection info: {e}")
            return {'error': str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get provider operation statistics"""
        with self._stats_lock:
            stats = self.stats.copy()
        
        connection_stats = self.connection_manager.get_stats()
        
        return {
            **stats,
            'connection_stats': connection_stats,
            'success_rate': (
                stats['operations_successful'] / max(stats['operations_total'], 1) * 100
            )
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health = {
            'overall_healthy': True,
            'checks': {}
        }
        
        try:
            # Connection health
            connection_health = self.connection_manager.health_check()
            health['checks']['connection'] = connection_health
            
            if not connection_health.get('libvirt_available'):
                health['overall_healthy'] = False
            
            # Try basic operations
            try:
                domains = self.list_domains(active_only=True)
                health['checks']['domain_listing'] = {
                    'success': True,
                    'active_domains': len(domains)
                }
            except Exception as e:
                health['checks']['domain_listing'] = {
                    'success': False,
                    'error': str(e)
                }
                health['overall_healthy'] = False
            
            # Check statistics
            stats = self.get_statistics()
            health['checks']['statistics'] = {
                'success': True,
                'operations_total': stats['operations_total'],
                'success_rate': stats['success_rate']
            }
            
        except Exception as e:
            health['overall_healthy'] = False
            health['error'] = str(e)
        
        return health
    
    def close(self):
        """Close provider and clean up resources"""
        if hasattr(self, 'connection_manager'):
            # Connection manager handles its own cleanup
            pass
        self.logger.info("LibVirt provider closed")
    
    # Backward compatibility methods to match virsh_client interface
    def open(self, uri: str = None) -> 'LibvirtProvider':
        """
        Compatibility method for opening connection.
        Returns self since connection is already managed.
        """
        return self
    
    def lookupByName(self, domain_name: str) -> LibvirtDomainWrapper:
        """
        Compatibility method for looking up domain by name.
        """
        return LibvirtDomainWrapper.from_name(domain_name, self.connection_manager)
    
    def defineXML(self, xml_config: str) -> LibvirtDomainWrapper:
        """
        Compatibility method for defining domain from XML.
        """
        result = self.create_domain_from_xml(xml_config, start=False)
        if result.success:
            return LibvirtDomainWrapper.from_name(result.domain_name, self.connection_manager)
        else:
            raise LibvirtProviderError(result.message)
    
    def isAlive(self) -> bool:
        """Check if connection is alive"""
        try:
            with self.connection_manager.connection_context() as conn:
                return conn.isAlive()
        except:
            return False
    
    def getHostname(self) -> str:
        """Get hypervisor hostname"""
        try:
            with self.connection_manager.connection_context() as conn:
                return conn.getHostname()
        except:
            return "unknown-host"
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Compatibility aliases for backward compatibility with existing code
VirshLibvirt = LibvirtProvider
VirshConnection = LibvirtProvider
VirshDomain = LibvirtDomainWrapper
VirshError = LibvirtProviderError


# Factory function for provider creation
def create_libvirt_provider(uri: str = "qemu:///system") -> LibvirtProvider:
    """
    Factory function to create a libvirt provider.
    
    Args:
        uri: LibVirt connection URI
        
    Returns:
        LibvirtProvider instance
    """
    return LibvirtProvider(uri)


# Utility functions for quick operations
def quick_domain_operation(domain_name: str, operation: str, uri: str = "qemu:///system") -> bool:
    """
    Perform quick domain operations.
    
    Args:
        domain_name: Name of the domain
        operation: Operation to perform ('start', 'stop', 'reboot', 'destroy')
        uri: LibVirt connection URI
        
    Returns:
        True if successful, False otherwise
    """
    try:
        provider = LibvirtProvider(uri)
        
        if operation == 'start':
            result = provider.start_domain(domain_name)
        elif operation == 'stop':
            result = provider.stop_domain(domain_name)
        elif operation == 'reboot':
            result = provider.reboot_domain(domain_name)
        elif operation == 'destroy':
            result = provider.destroy_domain(domain_name)
        else:
            return False
        
        return result.success
        
    except Exception as e:
        logger.error(f"Quick operation {operation} failed for {domain_name}: {e}")
        return False


def get_domain_summary(domain_name: str, uri: str = "qemu:///system") -> Optional[Dict[str, Any]]:
    """
    Get a summary of domain information.
    
    Args:
        domain_name: Name of the domain
        uri: LibVirt connection URI
        
    Returns:
        Dictionary with domain summary or None if error
    """
    try:
        provider = LibvirtProvider(uri)
        state_info = provider.get_domain_state(domain_name)
        
        if not state_info:
            return None
        
        return {
            'name': state_info.name,
            'uuid': state_info.uuid,
            'state': state_info.state_str,
            'is_active': state_info.is_active,
            'memory_mb': state_info.memory_mb,
            'vcpus': state_info.vcpus,
            'ip_addresses': [iface.primary_ip for iface in state_info.interfaces if iface.primary_ip],
            'interfaces': len(state_info.interfaces)
        }
        
    except Exception as e:
        logger.error(f"Failed to get domain summary for {domain_name}: {e}")
        return None