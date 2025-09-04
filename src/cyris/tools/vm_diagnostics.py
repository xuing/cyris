"""
VM Diagnostics Module

Provides comprehensive VM health checking and diagnostic capabilities
with minimal intrusion to existing codebase.
"""

# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import subprocess
import time
from typing import Dict, List, Optional, Tuple, NamedTuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = get_logger(__name__, "vm_diagnostics")


class DiagnosticLevel(Enum):
    """Diagnostic severity levels"""
    INFO = "info"
    WARNING = "warning"  
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check"""
    check_name: str
    level: DiagnosticLevel
    message: str
    suggestion: Optional[str] = None
    details: Optional[Dict] = None


class VMDiagnostics:
    """Core VM diagnostics and health checking"""
    
    def __init__(self):
        self.logger = get_logger(__name__, "vm_diagnostics")
        
    def check_vm_image_health(self, vm_name: str) -> List[DiagnosticResult]:
        """Check VM disk image integrity and configuration"""
        results = []
        
        try:
            # Get VM disk information
            disk_info = self._get_vm_disk_info(vm_name)
            if not disk_info:
                results.append(DiagnosticResult(
                    check_name="image_exists",
                    level=DiagnosticLevel.ERROR,
                    message=f"Cannot find disk information for VM {vm_name}",
                    suggestion="Check if VM exists and is properly configured"
                ))
                return results
            
            # Check image file existence and size
            for disk_path in disk_info:
                disk_file = Path(disk_path)
                if not disk_file.exists():
                    results.append(DiagnosticResult(
                        check_name="image_file_exists",
                        level=DiagnosticLevel.CRITICAL,
                        message=f"VM disk image not found: {disk_path}",
                        suggestion="Recreate VM or restore disk image from backup"
                    ))
                    continue
                
                # Check if image is suspiciously small (like our 196KB issue)
                file_size = disk_file.stat().st_size
                if file_size < 500 * 1024 * 1024:  # Less than 500MB
                    results.append(DiagnosticResult(
                        check_name="image_size_check",
                        level=DiagnosticLevel.ERROR,
                        message=f"VM image suspiciously small: {file_size / (1024*1024):.1f}MB",
                        suggestion="Image may be corrupted. Check base image and recreate VM",
                        details={"file_size_bytes": file_size, "file_path": str(disk_path)}
                    ))
                
                # Validate image format using qemu-img
                qemu_result = self._validate_image_with_qemu(disk_path)
                if qemu_result:
                    results.append(qemu_result)
            
        except Exception as e:
            results.append(DiagnosticResult(
                check_name="image_health_check",
                level=DiagnosticLevel.ERROR,
                message=f"Failed to check image health: {str(e)}",
                suggestion="Check VM configuration and libvirt permissions"
            ))
        
        if not results:
            results.append(DiagnosticResult(
                check_name="image_health",
                level=DiagnosticLevel.INFO,
                message="VM image appears healthy"
            ))
        
        return results
    
    def check_cloud_init_config(self, vm_name: str) -> List[DiagnosticResult]:
        """Check if cloud-init is properly configured"""
        results = []
        
        try:
            # Check if cloud-init.iso is attached
            attached_disks = self._get_vm_attached_disks(vm_name)
            has_cloud_init = any("cloud-init" in disk.lower() for disk in attached_disks)
            
            if not has_cloud_init:
                results.append(DiagnosticResult(
                    check_name="cloud_init_attached",
                    level=DiagnosticLevel.WARNING,
                    message="cloud-init.iso not found in VM configuration",
                    suggestion="Attach cloud-init.iso: virsh attach-disk {vm_name} /path/to/cloud-init.iso hdc --type cdrom --config".format(vm_name=vm_name)
                ))
            else:
                # Validate cloud-init.iso file exists and is readable
                cloud_init_paths = [disk for disk in attached_disks if "cloud-init" in disk.lower()]
                for cloud_init_path in cloud_init_paths:
                    if not Path(cloud_init_path).exists():
                        results.append(DiagnosticResult(
                            check_name="cloud_init_file_exists",
                            level=DiagnosticLevel.ERROR,
                            message=f"cloud-init.iso file not found: {cloud_init_path}",
                            suggestion="Create cloud-init.iso or update VM configuration"
                        ))
                    else:
                        results.append(DiagnosticResult(
                            check_name="cloud_init_config",
                            level=DiagnosticLevel.INFO,
                            message="cloud-init.iso properly configured"
                        ))
        
        except Exception as e:
            results.append(DiagnosticResult(
                check_name="cloud_init_check",
                level=DiagnosticLevel.WARNING,
                message=f"Could not verify cloud-init configuration: {str(e)}",
                suggestion="Check VM configuration and libvirt access"
            ))
        
        return results
    
    def check_vm_real_status(self, vm_name: str) -> List[DiagnosticResult]:
        """Check if VM is actually running and responsive"""
        results = []
        
        try:
            # Get VM statistics
            stats = self._get_vm_statistics(vm_name)
            if not stats:
                results.append(DiagnosticResult(
                    check_name="vm_stats_available",
                    level=DiagnosticLevel.ERROR,
                    message=f"Cannot retrieve statistics for VM {vm_name}",
                    suggestion="Check if VM is running and libvirt is accessible"
                ))
                return results
            
            # Check CPU activity
            cpu_time = stats.get('cpu_time', 0)
            if cpu_time == 0:
                results.append(DiagnosticResult(
                    check_name="cpu_activity",
                    level=DiagnosticLevel.WARNING,
                    message="VM shows no CPU activity - may not be properly started",
                    suggestion="Restart VM or check boot process"
                ))
            elif cpu_time < 10_000_000_000:  # Less than 10 seconds of CPU time
                results.append(DiagnosticResult(
                    check_name="cpu_activity",
                    level=DiagnosticLevel.WARNING,
                    message=f"VM has minimal CPU activity ({cpu_time / 1_000_000_000:.1f}s)",
                    suggestion="VM may have startup issues. Check console logs",
                    details={"cpu_time_ns": cpu_time}
                ))
            
            # Check network activity
            net_rx = stats.get('net_rx_bytes', 0)
            net_tx = stats.get('net_tx_bytes', 0)
            
            if net_rx < 1000 and net_tx == 0:  # Very minimal network activity
                results.append(DiagnosticResult(
                    check_name="network_activity",
                    level=DiagnosticLevel.WARNING,
                    message="VM shows minimal network activity - may not be properly initialized",
                    suggestion="Check cloud-init configuration and network setup",
                    details={"net_rx_bytes": net_rx, "net_tx_bytes": net_tx}
                ))
            
            # If everything looks good
            if not any(r.level in [DiagnosticLevel.WARNING, DiagnosticLevel.ERROR] for r in results):
                results.append(DiagnosticResult(
                    check_name="vm_real_status",
                    level=DiagnosticLevel.INFO,
                    message="VM appears to be running normally",
                    details={"cpu_time_s": cpu_time / 1_000_000_000, "net_rx_mb": net_rx / (1024*1024)}
                ))
        
        except Exception as e:
            results.append(DiagnosticResult(
                check_name="vm_status_check",
                level=DiagnosticLevel.ERROR,
                message=f"Failed to check VM real status: {str(e)}",
                suggestion="Check libvirt connection and VM configuration"
            ))
        
        return results
    
    def diagnose_network_issues(self, vm_name: str, expected_ip: Optional[str] = None) -> List[DiagnosticResult]:
        """Diagnose VM network connectivity issues"""
        results = []
        
        try:
            # Check if VM has network interfaces configured
            net_interfaces = self._get_vm_network_interfaces(vm_name)
            if not net_interfaces:
                results.append(DiagnosticResult(
                    check_name="network_interfaces",
                    level=DiagnosticLevel.ERROR,
                    message="VM has no network interfaces configured",
                    suggestion="Add network interface to VM configuration"
                ))
                return results
            
            # Check DHCP lease status
            mac_addresses = self._get_vm_mac_addresses(vm_name)
            dhcp_leases = self._get_dhcp_leases_for_macs(mac_addresses)
            
            if not dhcp_leases and mac_addresses:
                results.append(DiagnosticResult(
                    check_name="dhcp_lease",
                    level=DiagnosticLevel.WARNING,
                    message="VM has not obtained DHCP lease",
                    suggestion="Check cloud-init configuration and restart VM if necessary",
                    details={"mac_addresses": mac_addresses}
                ))
            
            # If expected IP provided, check connectivity
            if expected_ip:
                ping_result = self._test_ping_connectivity(expected_ip)
                if not ping_result:
                    results.append(DiagnosticResult(
                        check_name="ip_connectivity",
                        level=DiagnosticLevel.WARNING,
                        message=f"Cannot ping expected IP {expected_ip}",
                        suggestion="Check VM network configuration and firewall rules"
                    ))
        
        except Exception as e:
            results.append(DiagnosticResult(
                check_name="network_diagnosis",
                level=DiagnosticLevel.ERROR,
                message=f"Network diagnosis failed: {str(e)}",
                suggestion="Check libvirt network configuration"
            ))
        
        return results
    
    def get_vm_startup_logs(self, vm_name: str, lines: int = 50) -> Dict[str, str]:
        """Extract VM startup and console logs"""
        logs = {}
        
        try:
            # Try to get console output (if available)
            console_cmd = ["virsh", "console", vm_name, "--safe", "--force"]
            # Note: This might not work in non-interactive environment
            # but we can provide the command for manual execution
            logs["console_command"] = " ".join(console_cmd)
            
            # Get domain log from libvirt
            try:
                log_cmd = ["virsh", "dominfo", vm_name]
                result = subprocess.run(log_cmd, capture_output=True, text=True, timeout=10)
                logs["domain_info"] = result.stdout
            except:
                logs["domain_info"] = "Unable to retrieve domain info"
                
        except Exception as e:
            logs["error"] = f"Failed to retrieve logs: {str(e)}"
        
        return logs
    
    # Helper methods
    
    def _get_vm_disk_info(self, vm_name: str) -> List[str]:
        """Get VM disk file paths"""
        try:
            cmd = ["virsh", "domblklist", vm_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            
            disk_paths = []
            for line in result.stdout.split('\n')[2:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] != '-':
                        disk_paths.append(parts[1])
            
            return disk_paths
        except:
            return []
    
    def _get_vm_attached_disks(self, vm_name: str) -> List[str]:
        """Get all attached disk paths including ISOs"""
        return self._get_vm_disk_info(vm_name)
    
    def _validate_image_with_qemu(self, image_path: str) -> Optional[DiagnosticResult]:
        """Validate image using qemu-img"""
        try:
            cmd = ["qemu-img", "info", "--force-share", image_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode != 0:
                return DiagnosticResult(
                    check_name="qemu_image_validation",
                    level=DiagnosticLevel.ERROR,
                    message=f"qemu-img validation failed for {image_path}",
                    suggestion="Image may be corrupted. Check image integrity"
                )
            
            # Check for corruption indicators in output
            if "corrupt" in result.stdout.lower():
                return DiagnosticResult(
                    check_name="image_corruption",
                    level=DiagnosticLevel.CRITICAL,
                    message=f"Image corruption detected in {image_path}",
                    suggestion="Replace corrupted image with backup"
                )
                
        except subprocess.TimeoutExpired:
            return DiagnosticResult(
                check_name="qemu_validation_timeout",
                level=DiagnosticLevel.WARNING,
                message="Image validation timed out - image may be very large or corrupted",
                suggestion="Check image manually with qemu-img info"
            )
        except:
            return None
        
        return None
    
    def _get_vm_statistics(self, vm_name: str) -> Dict:
        """Get VM runtime statistics"""
        try:
            cmd = ["virsh", "domstats", vm_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {}
            
            stats = {}
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    
                    # Parse important statistics
                    if key == 'cpu.time':
                        stats['cpu_time'] = int(value)
                    elif key == 'net.0.rx.bytes':
                        stats['net_rx_bytes'] = int(value)
                    elif key == 'net.0.tx.bytes':
                        stats['net_tx_bytes'] = int(value)
            
            return stats
        except:
            return {}
    
    def _get_vm_network_interfaces(self, vm_name: str) -> List[str]:
        """Get VM network interface names"""
        try:
            cmd = ["virsh", "dumpxml", vm_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            # Simple parsing - look for interface tags
            interfaces = []
            for line in result.stdout.split('\n'):
                if '<interface type=' in line:
                    interfaces.append("network_interface")
            
            return interfaces
        except:
            return []
    
    def _get_vm_mac_addresses(self, vm_name: str) -> List[str]:
        """Get VM MAC addresses"""
        try:
            cmd = ["virsh", "dumpxml", vm_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            mac_addresses = []
            for line in result.stdout.split('\n'):
                if 'mac address=' in line:
                    # Extract MAC address from XML
                    start = line.find("'") + 1
                    end = line.find("'", start)
                    if start > 0 and end > start:
                        mac_addresses.append(line[start:end])
            
            return mac_addresses
        except:
            return []
    
    def _get_dhcp_leases_for_macs(self, mac_addresses: List[str]) -> List[str]:
        """Check DHCP leases for given MAC addresses"""
        try:
            cmd = ["virsh", "net-dhcp-leases", "default"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            found_leases = []
            for line in result.stdout.split('\n'):
                for mac in mac_addresses:
                    if mac in line and 'ipv4' in line:
                        found_leases.append(line.strip())
            
            return found_leases
        except:
            return []
    
    def _test_ping_connectivity(self, ip_address: str) -> bool:
        """Test basic ping connectivity"""
        try:
            cmd = ["ping", "-c", "1", "-W", "2", ip_address]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False


# Convenience function for quick VM health check
def quick_vm_health_check(vm_name: str) -> List[DiagnosticResult]:
    """Perform a quick health check on a VM"""
    diagnostics = VMDiagnostics()
    
    all_results = []
    all_results.extend(diagnostics.check_vm_image_health(vm_name))
    all_results.extend(diagnostics.check_cloud_init_config(vm_name))
    all_results.extend(diagnostics.check_vm_real_status(vm_name))
    
    return all_results