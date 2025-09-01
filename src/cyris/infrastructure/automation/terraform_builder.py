"""
Terraform Infrastructure Builder Implementation

Provides automated infrastructure provisioning using HashiCorp Terraform with libvirt provider.
Supports declarative VM creation, network topology, and storage management.
"""

import json
import subprocess
import shutil
import hashlib
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging
import tempfile
import yaml

from .base_automation import (
    AutomationProvider, AutomationConfig, AutomationResult, 
    AutomationStatus, AutomationError
)
from ...config.automation_settings import TerraformSettings
from ...core.exceptions import CyRISVirtualizationError


class TerraformError(AutomationError):
    """Terraform-specific errors"""
    pass


class TerraformBuilder(AutomationProvider):
    """
    Terraform-based infrastructure builder for automated VM and network provisioning.
    
    Capabilities:
    - Declarative infrastructure as code (HCL)
    - VM creation with libvirt provider
    - Network topology management
    - Storage volume provisioning
    - State management and drift detection
    - Plan validation before apply
    
    Typical workflow:
    1. Generate Terraform configuration from CyRIS entities
    2. Initialize Terraform workspace
    3. Plan infrastructure changes
    4. Apply configuration
    5. Track resource state
    """
    
    def __init__(self, settings: TerraformSettings):
        """
        Initialize Terraform builder.
        
        Args:
            settings: Terraform configuration settings
        """
        config = AutomationConfig(
            provider_type="terraform",
            enabled=settings.enabled,
            timeout=settings.timeout,
            retry_count=settings.retry_count,
            working_directory=settings.working_dir,
            debug_mode=True
        )
        super().__init__(config)
        
        self.settings = settings
        self.terraform_binary = self._find_terraform_binary()
        self.state_manager = StateManager(settings)
        
        # Create required directories
        settings.working_dir.mkdir(parents=True, exist_ok=True)
        settings.templates_dir.mkdir(parents=True, exist_ok=True)
        settings.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _find_terraform_binary(self) -> Optional[Path]:
        """Find terraform binary on system"""
        if self.settings.binary_path:
            return self.settings.binary_path
        
        # Search common locations
        common_paths = [
            Path("/usr/local/bin/terraform"),
            Path("/usr/bin/terraform"),
            Path("/opt/terraform/terraform")
        ]
        
        for path in common_paths:
            if path.exists() and path.is_file():
                return path
        
        # Try which/where command
        try:
            result = subprocess.run(
                ["which", "terraform"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None
    
    async def connect(self) -> None:
        """Connect to Terraform and verify availability"""
        if not self.terraform_binary:
            raise TerraformError("Terraform binary not found on system")
        
        if not self.terraform_binary.exists():
            raise TerraformError(f"Terraform binary not found at: {self.terraform_binary}")
        
        try:
            # Verify terraform version
            result = await asyncio.create_subprocess_exec(
                str(self.terraform_binary), "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.settings.working_dir
            )
            
            stdout, stderr = await asyncio.wait_for(
                result.communicate(), 
                timeout=30.0
            )
            
            if result.returncode != 0:
                raise TerraformError(f"Terraform version check failed: {stderr.decode()}")
            
            version_output = stdout.decode().strip()
            self.logger.info(f"Connected to Terraform: {version_output}")
            self._is_connected = True
            
        except asyncio.TimeoutError:
            raise TerraformError("Terraform version check timed out")
        except Exception as e:
            raise TerraformError(f"Failed to connect to Terraform: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Terraform provider"""
        self._is_connected = False
        self.logger.info("Disconnected from Terraform")
    
    async def validate_configuration(self) -> List[str]:
        """Validate Terraform configuration"""
        issues = []
        
        # Check binary availability
        if not self.terraform_binary:
            issues.append("Terraform binary not found")
        elif not self.terraform_binary.exists():
            issues.append(f"Terraform binary missing: {self.terraform_binary}")
        
        # Check directories
        if not self.settings.working_dir.exists():
            issues.append(f"Working directory missing: {self.settings.working_dir}")
        
        if not self.settings.templates_dir.exists():
            issues.append(f"Templates directory missing: {self.settings.templates_dir}")
        
        # Check disk space (minimum 1GB for state and plans)
        try:
            disk_usage = shutil.disk_usage(self.settings.working_dir)
            free_gb = disk_usage.free / (1024**3)
            if free_gb < 1:
                issues.append(f"Insufficient disk space: {free_gb:.1f}GB available, need 1GB+")
        except Exception as e:
            issues.append(f"Could not check disk space: {str(e)}")
        
        # Check required tools for libvirt
        required_tools = ["qemu-system-x86_64", "virsh"]
        for tool in required_tools:
            if not shutil.which(tool):
                issues.append(f"Required tool missing: {tool}")
        
        # Check libvirt connection
        try:
            result = subprocess.run(
                ["virsh", "list", "--all"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append("Cannot connect to libvirt daemon")
        except Exception as e:
            issues.append(f"Libvirt connection check failed: {str(e)}")
        
        return issues
    
    async def execute_operation(
        self,
        operation_type: str,
        parameters: Dict[str, Any],
        operation_id: Optional[str] = None
    ) -> AutomationResult:
        """
        Execute Terraform infrastructure operation.
        
        Args:
            operation_type: Type of operation ('apply', 'plan', 'destroy', 'validate')
            parameters: Operation parameters
            operation_id: Optional operation ID
            
        Returns:
            Infrastructure operation result
        """
        if not operation_id:
            operation_id = self.generate_operation_id()
        
        result = AutomationResult(
            operation_id=operation_id,
            provider_type=self.provider_type,
            status=AutomationStatus.RUNNING,
            started_at=datetime.now()
        )
        
        self._track_operation(result)
        
        try:
            if operation_type == "apply":
                await self._execute_apply(parameters, result)
            elif operation_type == "plan":
                await self._execute_plan(parameters, result)
            elif operation_type == "destroy":
                await self._execute_destroy(parameters, result)
            elif operation_type == "validate":
                await self._execute_validate(parameters, result)
            else:
                raise TerraformError(f"Unknown operation type: {operation_type}")
            
            result.status = AutomationStatus.COMPLETED
            result.completed_at = datetime.now()
            
        except Exception as e:
            result.status = AutomationStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            self.logger.error(f"Terraform operation failed: {e}")
        
        return result
    
    async def _execute_apply(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute infrastructure apply operation"""
        operation_id = result.operation_id
        hosts = parameters.get("hosts", [])
        guests = parameters.get("guests", [])
        network_config = parameters.get("network_config", {})
        
        if not hosts and not guests:
            raise TerraformError("At least one host or guest is required for apply operation")
        
        # Generate Terraform configuration
        config_content = await self._generate_terraform_config(
            hosts, guests, network_config, operation_id
        )
        
        # Write configuration to working directory
        workspace_dir = self.settings.working_dir / f"workspace-{operation_id}"
        workspace_dir.mkdir(exist_ok=True)
        
        config_path = workspace_dir / "main.tf"
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Initialize Terraform
        await self._run_terraform_init(workspace_dir, operation_id)
        
        # Plan changes
        plan_output = await self._run_terraform_plan(workspace_dir, operation_id)
        
        # Apply changes
        apply_output = await self._run_terraform_apply(workspace_dir, operation_id)
        
        # Get state information
        state_info = await self._get_terraform_state(workspace_dir)
        
        result.output = apply_output
        result.artifacts = {
            "workspace_dir": str(workspace_dir),
            "config_path": str(config_path),
            "plan_output": plan_output,
            "state_info": state_info,
            "resources_created": self._extract_created_resources(state_info)
        }
    
    async def _execute_plan(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute infrastructure plan operation"""
        operation_id = result.operation_id
        workspace_dir = parameters.get("workspace_dir")
        
        if not workspace_dir:
            raise TerraformError("workspace_dir is required for plan operation")
        
        workspace_path = Path(workspace_dir)
        if not workspace_path.exists():
            raise TerraformError(f"Workspace directory not found: {workspace_path}")
        
        # Run terraform plan
        plan_output = await self._run_terraform_plan(workspace_path, operation_id)
        
        result.output = plan_output
        result.artifacts = {
            "workspace_dir": str(workspace_path),
            "plan_output": plan_output
        }
    
    async def _execute_destroy(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute infrastructure destroy operation"""
        operation_id = result.operation_id
        workspace_dir = parameters.get("workspace_dir")
        
        if not workspace_dir:
            raise TerraformError("workspace_dir is required for destroy operation")
        
        workspace_path = Path(workspace_dir)
        if not workspace_path.exists():
            raise TerraformError(f"Workspace directory not found: {workspace_path}")
        
        # Run terraform destroy
        destroy_output = await self._run_terraform_destroy(workspace_path, operation_id)
        
        result.output = destroy_output
        result.artifacts = {
            "workspace_dir": str(workspace_path),
            "destroy_output": destroy_output
        }
    
    async def _execute_validate(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Validate Terraform configuration"""
        config_path = parameters.get("config_path")
        if not config_path:
            raise TerraformError("config_path is required for validate operation")
        
        config_path = Path(config_path)
        workspace_dir = config_path.parent
        
        if not config_path.exists():
            raise TerraformError(f"Configuration file not found: {config_path}")
        
        # Initialize if needed
        if not (workspace_dir / ".terraform").exists():
            await self._run_terraform_init(workspace_dir, result.operation_id)
        
        # Run terraform validate
        process = await asyncio.create_subprocess_exec(
            str(self.terraform_binary), "validate",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_dir
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            raise TerraformError(f"Configuration validation failed: {stderr.decode()}")
        
        result.output = stdout.decode()
    
    async def _generate_terraform_config(
        self,
        hosts: List[Any],
        guests: List[Any],
        network_config: Dict[str, Any],
        operation_id: str
    ) -> str:
        """Generate Terraform HCL configuration"""
        
        # Load base template or generate default
        base_template_path = self.settings.templates_dir / "libvirt.tf.template"
        if base_template_path.exists():
            with open(base_template_path) as f:
                base_template = f.read()
        else:
            base_template = self._generate_default_template()
        
        # Generate resources
        resources = []
        
        # Generate network resources
        for network_name, network_info in network_config.items():
            resources.append(self._generate_network_resource(network_name, network_info))
        
        # Generate host resources
        for host in hosts:
            resources.append(self._generate_host_resource(host))
        
        # Generate guest resources
        for guest in guests:
            resources.append(self._generate_guest_resource(guest))
        
        # Combine template and resources
        config = base_template + "\n\n" + "\n\n".join(resources)
        
        return config
    
    def _generate_default_template(self) -> str:
        """Generate default Terraform libvirt template"""
        return '''
# CyRIS Terraform Libvirt Provider Configuration
terraform {
  required_providers {
    libvirt = {
      source  = "dmacvicar/libvirt"
      version = "~> 0.7"
    }
  }
}

# Libvirt provider configuration
provider "libvirt" {
  uri = "qemu:///system"
}
'''
    
    def _generate_network_resource(self, network_name: str, network_info: Dict[str, Any]) -> str:
        """Generate Terraform network resource"""
        subnet = network_info.get('subnet', '192.168.100.0/24')
        domain = network_info.get('domain', 'cyris.local')
        
        return f'''
# Network: {network_name}
resource "libvirt_network" "{network_name}" {{
  name      = "{network_name}"
  mode      = "nat"
  domain    = "{domain}"
  addresses = ["{subnet}"]
  
  dhcp {{
    enabled = true
  }}
  
  dns {{
    enabled = true
  }}
}}
'''
    
    def _generate_host_resource(self, host: Any) -> str:
        """Generate Terraform host resource"""
        host_name = getattr(host, 'name', 'unknown-host')
        
        # For now, hosts are treated as VM resources
        # In a real implementation, this might create physical host management resources
        return f'''
# Host: {host_name}
# Note: Host resources are managed by the hypervisor
# This is a placeholder for host-level configuration
'''
    
    def _generate_guest_resource(self, guest: Any) -> str:
        """Generate Terraform guest VM resource"""
        guest_name = getattr(guest, 'name', 'unknown-guest')
        memory = getattr(guest, 'memory', 1024)
        vcpus = getattr(guest, 'vcpus', 1)
        base_image = getattr(guest, 'base_image', 'ubuntu-20.04.qcow2')
        
        return f'''
# VM: {guest_name}
resource "libvirt_volume" "{guest_name}_disk" {{
  name           = "{guest_name}.qcow2"
  base_volume_id = "${{libvirt_volume.base_image.id}}"
  format         = "qcow2"
  size           = 21474836480  # 20GB
}}

resource "libvirt_domain" "{guest_name}" {{
  name   = "{guest_name}"
  memory = {memory}
  vcpu   = {vcpus}
  
  disk {{
    volume_id = "${{libvirt_volume.{guest_name}_disk.id}}"
  }}
  
  network_interface {{
    network_name   = "${{libvirt_network.default.name}}"
    wait_for_lease = true
  }}
  
  console {{
    type        = "pty"
    target_port = "0"
    target_type = "serial"
  }}
  
  graphics {{
    type           = "spice"
    listen_type    = "address"
    autoport       = true
  }}
}}
'''
    
    async def _run_terraform_init(self, workspace_dir: Path, operation_id: str) -> str:
        """Run terraform init"""
        process = await asyncio.create_subprocess_exec(
            str(self.terraform_binary), "init",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace_dir
        )
        
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            output = stdout.decode() if stdout else "No output"
            raise TerraformError(f"Terraform init failed (exit code {process.returncode}):\n{output}")
        
        return stdout.decode() if stdout else ""
    
    async def _run_terraform_plan(self, workspace_dir: Path, operation_id: str) -> str:
        """Run terraform plan"""
        plan_file = workspace_dir / f"plan-{operation_id}.tfplan"
        
        process = await asyncio.create_subprocess_exec(
            str(self.terraform_binary), "plan", f"-out={plan_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace_dir
        )
        
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            output = stdout.decode() if stdout else "No output"
            raise TerraformError(f"Terraform plan failed (exit code {process.returncode}):\n{output}")
        
        return stdout.decode() if stdout else ""
    
    async def _run_terraform_apply(self, workspace_dir: Path, operation_id: str) -> str:
        """Run terraform apply"""
        plan_file = workspace_dir / f"plan-{operation_id}.tfplan"
        
        process = await asyncio.create_subprocess_exec(
            str(self.terraform_binary), "apply", "-auto-approve", str(plan_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace_dir
        )
        
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            output = stdout.decode() if stdout else "No output"
            raise TerraformError(f"Terraform apply failed (exit code {process.returncode}):\n{output}")
        
        return stdout.decode() if stdout else ""
    
    async def _run_terraform_destroy(self, workspace_dir: Path, operation_id: str) -> str:
        """Run terraform destroy"""
        process = await asyncio.create_subprocess_exec(
            str(self.terraform_binary), "destroy", "-auto-approve",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace_dir
        )
        
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            output = stdout.decode() if stdout else "No output"
            raise TerraformError(f"Terraform destroy failed (exit code {process.returncode}):\n{output}")
        
        return stdout.decode() if stdout else ""
    
    async def _get_terraform_state(self, workspace_dir: Path) -> Dict[str, Any]:
        """Get current Terraform state"""
        state_file = workspace_dir / "terraform.tfstate"
        
        if not state_file.exists():
            return {}
        
        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to read state file: {e}")
            return {}
    
    def _extract_created_resources(self, state_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract created resources from Terraform state"""
        resources = []
        
        if "resources" in state_info:
            for resource in state_info["resources"]:
                resources.append({
                    "type": resource.get("type"),
                    "name": resource.get("name"),
                    "provider": resource.get("provider"),
                    "instances": len(resource.get("instances", []))
                })
        
        return resources
    
    async def get_operation_status(self, operation_id: str) -> Optional[AutomationResult]:
        """Get status of specific operation"""
        return self._active_operations.get(operation_id)
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel running operation"""
        # TODO: Implement operation cancellation by process termination
        if operation_id in self._active_operations:
            result = self._active_operations[operation_id]
            result.status = AutomationStatus.CANCELLED
            return True
        return False
    
    async def cleanup_artifacts(self, operation_id: str) -> None:
        """Clean up artifacts from completed operation"""
        self._untrack_operation(operation_id)
        
        # Clean up temporary workspace if configured to do so
        if self.settings.cleanup_workspaces:
            workspace_dir = self.settings.working_dir / f"workspace-{operation_id}"
            if workspace_dir.exists():
                try:
                    shutil.rmtree(workspace_dir)
                    self.logger.info(f"Cleaned up workspace: {workspace_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup workspace {workspace_dir}: {e}")


class StateManager:
    """Terraform state management and synchronization"""
    
    def __init__(self, settings: TerraformSettings):
        self.settings = settings
        self.state_dir = settings.state_dir
        self.logger = logging.getLogger(f"{__name__}.StateManager")
    
    async def sync_state(self, workspace_id: str) -> Dict[str, Any]:
        """Synchronize state with actual infrastructure"""
        # TODO: Implement state synchronization
        return {}
    
    async def backup_state(self, workspace_id: str) -> Path:
        """Create state backup"""
        # TODO: Implement state backup
        return self.state_dir / f"{workspace_id}.backup"
    
    async def restore_state(self, workspace_id: str, backup_path: Path) -> bool:
        """Restore state from backup"""
        # TODO: Implement state restoration
        return True