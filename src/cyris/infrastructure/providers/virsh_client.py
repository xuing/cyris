"""
Virsh Command Line Client

A simple libvirt client that uses the virsh command-line tool
to perform KVM operations when Python libvirt bindings are not available.
"""

import subprocess
import tempfile
import uuid
import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class VirshError(Exception):
    """Exception raised for virsh command errors"""
    pass


class VirshDomain:
    """Represents a domain managed via virsh"""
    
    def __init__(self, name: str, uri: str = "qemu:///session"):
        self.name = name
        self.uri = uri
    
    def create(self) -> int:
        """Start the domain"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "start", self.name],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Started domain {self.name}")
            return 0
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start domain {self.name}: {e.stderr}")
            raise VirshError(f"Failed to start domain: {e.stderr}")
    
    def destroy(self) -> int:
        """Forcibly stop the domain"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "destroy", self.name],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Destroyed domain {self.name}")
            return 0
        except subprocess.CalledProcessError as e:
            if "domain is not running" in e.stderr.lower():
                return 0  # Already stopped
            logger.error(f"Failed to destroy domain {self.name}: {e.stderr}")
            raise VirshError(f"Failed to destroy domain: {e.stderr}")
    
    def undefine(self) -> int:
        """Undefine the domain"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "undefine", self.name],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Undefined domain {self.name}")
            return 0
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to undefine domain {self.name}: {e.stderr}")
            raise VirshError(f"Failed to undefine domain: {e.stderr}")
    
    def state(self) -> List[int]:
        """Get domain state"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "domstate", self.name],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            state_str = result.stdout.strip()
            # Map virsh states to libvirt constants
            if "running" in state_str:
                return [1, 0]  # VIR_DOMAIN_RUNNING
            elif "shut off" in state_str:
                return [5, 0]  # VIR_DOMAIN_SHUTOFF
            elif "paused" in state_str:
                return [3, 0]  # VIR_DOMAIN_PAUSED
            else:
                return [0, 0]  # Unknown state
        except subprocess.CalledProcessError:
            return [0, 0]  # Domain doesn't exist or error
    
    def info(self) -> List[Any]:
        """Get domain info"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "dominfo", self.name],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            # Parse basic info from output
            lines = result.stdout.strip().split('\n')
            state = 1 if any("running" in line.lower() for line in lines) else 5
            return [state, 1048576, 1048576, 2, 0]  # state, max_mem, memory, vcpus, cpu_time
        except subprocess.CalledProcessError:
            return [0, 0, 0, 0, 0]
    
    def isActive(self) -> int:
        """Check if domain is active"""
        state, _ = self.state()
        return 1 if state == 1 else 0


class VirshConnection:
    """Manages virsh connections"""
    
    def __init__(self, uri: str = "qemu:///session"):
        self.uri = uri
        self._test_connection()
    
    def _test_connection(self):
        """Test the virsh connection"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "version"],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Connected to hypervisor via virsh: {self.uri}")
        except subprocess.CalledProcessError as e:
            raise VirshError(f"Failed to connect to hypervisor: {e.stderr}")
    
    def isAlive(self) -> bool:
        """Check if connection is alive"""
        try:
            subprocess.run(
                ["virsh", "--connect", self.uri, "version"],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def getHostname(self) -> str:
        """Get hypervisor hostname"""
        try:
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "hostname"],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown-host"
    
    def close(self):
        """Close connection (no-op for virsh)"""
        pass
    
    def lookupByName(self, name: str) -> VirshDomain:
        """Look up domain by name"""
        return VirshDomain(name, self.uri)
    
    def defineXML(self, xml: str) -> VirshDomain:
        """Define a domain from XML"""
        # Write XML to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml)
            xml_file = f.name
        
        try:
            # Parse domain name from XML to return proper domain object
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            domain_name = root.find('name').text
            
            # Define domain
            result = subprocess.run(
                ["virsh", "--connect", self.uri, "define", xml_file],
                capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
            )
            logger.info(f"Defined domain {domain_name}")
            return VirshDomain(domain_name, self.uri)
            
        except subprocess.CalledProcessError as e:
            raise VirshError(f"Failed to define domain: {e.stderr}")
        except ET.ParseError as e:
            raise VirshError(f"Invalid XML: {e}")
        finally:
            # Clean up temporary file
            try:
                os.unlink(xml_file)
            except OSError:
                pass
    
    def networkLookupByName(self, name: str):
        """Look up network by name (placeholder)"""
        return None
    
    def networkDefineXML(self, xml: str):
        """Define network from XML (placeholder)"""
        return None


class VirshLibvirt:
    """Virsh-based libvirt implementation"""
    
    VIR_DOMAIN_RUNNING = 1
    VIR_DOMAIN_SHUTOFF = 5
    VIR_DOMAIN_PAUSED = 3
    
    virDomain = VirshDomain
    libvirtError = VirshError
    
    @staticmethod
    def open(uri: str = None) -> VirshConnection:
        """Open connection to hypervisor"""
        if uri is None:
            uri = "qemu:///session"  # Default to user session to avoid permission issues
        return VirshConnection(uri)