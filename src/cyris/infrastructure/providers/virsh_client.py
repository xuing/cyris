"""
LibVirt Client - Compatibility Bridge

This module provides a compatibility bridge for the enhanced libvirt-python
implementation while maintaining backward compatibility with existing code
that imports from virsh_client.

The new implementation is in libvirt_provider.py with significant performance
improvements and enhanced functionality.
"""

# Import everything from the new enhanced implementation
from .libvirt_provider import (
    LibvirtProvider,
    LibvirtProviderError,
    DomainOperationResult,
    DomainLifecycleState,
    NetworkInfo,
    StoragePoolInfo,
    create_libvirt_provider,
    quick_domain_operation,
    get_domain_summary
)

from .libvirt_domain_wrapper import (
    LibvirtDomainWrapper,
    DomainState,
    DomainStateInfo,
    NetworkInterface
)

# Backward compatibility aliases
VirshError = LibvirtProviderError
VirshDomain = LibvirtDomainWrapper
VirshConnection = LibvirtProvider
VirshLibvirt = LibvirtProvider

# Legacy classes and functions for full backward compatibility
class VirshClient:
    """Legacy VirshClient compatibility class"""
    
    def __init__(self, uri: str = "qemu:///session"):
        self.provider = LibvirtProvider(uri)
        self.uri = uri
    
    def open(self, uri: str = None):
        """Open connection - returns provider for compatibility"""
        if uri:
            return LibvirtProvider(uri)
        return self.provider
    
    def list_all_domains(self):
        """List all domains"""
        return self.provider.list_domains(active_only=False, include_state=False)
    
    def destroy_domain(self, domain_name: str):
        """Destroy domain"""
        result = self.provider.destroy_domain(domain_name)
        return result.success
    
    def undefine_domain(self, domain_name: str):
        """Undefine domain"""
        result = self.provider.destroy_domain(domain_name, undefine=True)
        return result.success


def virsh_command_compatibility_warning():
    """Issue deprecation warning for direct virsh usage"""
    import warnings
    warnings.warn(
        "Direct virsh command usage is deprecated. Please use the enhanced "
        "libvirt-python implementation in libvirt_provider.py for better "
        "performance and reliability.",
        DeprecationWarning,
        stacklevel=2
    )


# Module-level compatibility functions
def open_libvirt_connection(uri: str = "qemu:///system"):
    """Open libvirt connection with enhanced provider"""
    return LibvirtProvider(uri)


# Export the main classes for backward compatibility
__all__ = [
    'LibvirtProvider',
    'LibvirtProviderError',
    'LibvirtDomainWrapper',
    'VirshError',
    'VirshDomain', 
    'VirshConnection',
    'VirshLibvirt',
    'VirshClient',
    'create_libvirt_provider',
    'open_libvirt_connection'
]