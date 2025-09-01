"""
Packer Image Builder Implementation

Provides automated VM image building, conversion, and customization using HashiCorp Packer.
Supports multiple image formats (qcow2, vmdk, vhd) and cloud-init integration.
"""

import json
import subprocess
import shutil
import hashlib
import asyncio
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
from ...config.automation_settings import PackerSettings
from ...core.exceptions import CyRISVirtualizationError


class PackerError(AutomationError):
    """Packer-specific errors"""
    pass


class PackerBuilder(AutomationProvider):
    """
    Packer-based image builder for automated VM image creation.
    
    Capabilities:
    - Download and convert base images (ISO/IMG to qcow2/vmdk/vhd)
    - Inject SSH keys and user configurations via cloud-init
    - Cache built images for reuse
    - Support multiple output formats
    - Parallel build execution
    
    Typical workflow:
    1. Select/validate image template
    2. Generate Packer configuration
    3. Execute build process
    4. Convert to target formats
    5. Cache results
    """
    
    def __init__(self, settings: PackerSettings):
        """
        Initialize Packer builder.
        
        Args:
            settings: Packer configuration settings
        """
        config = AutomationConfig(
            provider_type="packer",
            enabled=settings.enabled,
            timeout=settings.timeout,
            retry_count=settings.retry_count,
            working_directory=settings.working_dir,
            debug_mode=True
        )
        super().__init__(config)
        
        self.settings = settings
        self.packer_binary = self._find_packer_binary()
        self.image_cache = ImageCache(settings)
        
        # Create required directories
        settings.working_dir.mkdir(parents=True, exist_ok=True)
        settings.templates_dir.mkdir(parents=True, exist_ok=True)
        settings.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _find_packer_binary(self) -> Optional[Path]:
        """Find packer binary on system"""
        if self.settings.binary_path:
            return self.settings.binary_path
        
        # Search common locations
        common_paths = [
            Path("/usr/local/bin/packer"),
            Path("/usr/bin/packer"),
            Path("/opt/packer/packer")
        ]
        
        for path in common_paths:
            if path.exists() and path.is_file():
                return path
        
        # Try which/where command
        try:
            result = subprocess.run(
                ["which", "packer"], 
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
        """Connect to Packer and verify availability"""
        if not self.packer_binary:
            raise PackerError("Packer binary not found on system")
        
        if not self.packer_binary.exists():
            raise PackerError(f"Packer binary not found at: {self.packer_binary}")
        
        try:
            # Verify packer version
            result = await asyncio.create_subprocess_exec(
                str(self.packer_binary), "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.settings.working_dir
            )
            
            stdout, stderr = await asyncio.wait_for(
                result.communicate(), 
                timeout=30.0
            )
            
            if result.returncode != 0:
                raise PackerError(f"Packer version check failed: {stderr.decode()}")
            
            version_output = stdout.decode().strip()
            self.logger.info(f"Connected to Packer: {version_output}")
            self._is_connected = True
            
        except asyncio.TimeoutError:
            raise PackerError("Packer version check timed out")
        except Exception as e:
            raise PackerError(f"Failed to connect to Packer: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Packer provider"""
        self._is_connected = False
        self.logger.info("Disconnected from Packer")
    
    async def validate_configuration(self) -> List[str]:
        """Validate Packer configuration"""
        issues = []
        
        # Check binary availability
        if not self.packer_binary:
            issues.append("Packer binary not found")
        elif not self.packer_binary.exists():
            issues.append(f"Packer binary missing: {self.packer_binary}")
        
        # Check directories
        if not self.settings.working_dir.exists():
            issues.append(f"Working directory missing: {self.settings.working_dir}")
        
        if not self.settings.templates_dir.exists():
            issues.append(f"Templates directory missing: {self.settings.templates_dir}")
        
        # Check disk space (minimum 5GB for image building)
        try:
            disk_usage = shutil.disk_usage(self.settings.working_dir)
            free_gb = disk_usage.free / (1024**3)
            if free_gb < 5:
                issues.append(f"Insufficient disk space: {free_gb:.1f}GB available, need 5GB+")
        except Exception as e:
            issues.append(f"Could not check disk space: {str(e)}")
        
        # Check required tools
        required_tools = ["qemu-img", "qemu-system-x86_64"]
        for tool in required_tools:
            if not shutil.which(tool):
                issues.append(f"Required tool missing: {tool}")
        
        return issues
    
    async def execute_operation(
        self,
        operation_type: str,
        parameters: Dict[str, Any],
        operation_id: Optional[str] = None
    ) -> AutomationResult:
        """
        Execute Packer build operation.
        
        Args:
            operation_type: Type of operation ('build', 'validate', 'inspect')
            parameters: Build parameters
            operation_id: Optional operation ID
            
        Returns:
            Build operation result
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
            if operation_type == "build":
                await self._execute_build(parameters, result)
            elif operation_type == "validate":
                await self._execute_validate(parameters, result)
            elif operation_type == "inspect":
                await self._execute_inspect(parameters, result)
            else:
                raise PackerError(f"Unknown operation type: {operation_type}")
            
            result.status = AutomationStatus.COMPLETED
            result.completed_at = datetime.now()
            
        except Exception as e:
            result.status = AutomationStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            self.logger.error(f"Packer operation failed: {e}")
        
        return result
    
    async def _execute_build(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute image build operation"""
        operation_id = result.operation_id
        template_name = parameters.get("template_name")
        output_formats = parameters.get("output_formats", ["qcow2"])
        ssh_keys = parameters.get("ssh_keys", [])
        custom_config = parameters.get("custom_config", {})
        
        if not template_name:
            raise PackerError("template_name is required for build operation")
        
        # Check cache first
        cache_key = self._generate_cache_key(template_name, ssh_keys, custom_config)
        cached_images = await self.image_cache.get_cached_images(cache_key)
        
        if cached_images and not parameters.get("force_rebuild", False):
            result.output = f"Using cached images for {template_name}"
            result.artifacts = {"cached_images": cached_images}
            return
        
        # Generate Packer template
        template_config = await self._generate_packer_template(
            template_name, output_formats, ssh_keys, custom_config
        )
        
        # Write template to working directory
        template_path = self.settings.working_dir / f"{template_name}-{operation_id}.pkr.hcl"
        with open(template_path, 'w') as f:
            f.write(template_config)
        
        # Execute packer build
        build_output = await self._run_packer_build(template_path, operation_id)
        
        # Process build results
        built_images = await self._process_build_results(
            template_name, output_formats, operation_id
        )
        
        # Cache successful builds
        if built_images:
            await self.image_cache.cache_images(cache_key, built_images)
        
        result.output = build_output
        result.artifacts = {
            "built_images": built_images,
            "template_path": str(template_path),
            "cache_key": cache_key
        }
    
    async def _execute_validate(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Validate Packer template"""
        template_path = parameters.get("template_path")
        if not template_path:
            raise PackerError("template_path is required for validate operation")
        
        template_path = Path(template_path)
        if not template_path.exists():
            raise PackerError(f"Template file not found: {template_path}")
        
        # Run packer validate
        process = await asyncio.create_subprocess_exec(
            str(self.packer_binary), "validate", str(template_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.settings.working_dir
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=self.settings.timeout
        )
        
        if process.returncode != 0:
            raise PackerError(f"Template validation failed: {stderr.decode()}")
        
        result.output = stdout.decode()
    
    async def _execute_inspect(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Inspect Packer template"""
        template_path = parameters.get("template_path")
        if not template_path:
            raise PackerError("template_path is required for inspect operation")
        
        # Run packer inspect
        process = await asyncio.create_subprocess_exec(
            str(self.packer_binary), "inspect", str(template_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.settings.working_dir
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30.0
        )
        
        if process.returncode != 0:
            raise PackerError(f"Template inspection failed: {stderr.decode()}")
        
        result.output = stdout.decode()
    
    async def _generate_packer_template(
        self,
        template_name: str,
        output_formats: List[str],
        ssh_keys: List[str],
        custom_config: Dict[str, Any]
    ) -> str:
        """Generate Packer HCL template"""
        
        # Load base template
        base_template_path = self.settings.templates_dir / f"{template_name}.pkr.hcl"
        if not base_template_path.exists():
            # Generate default template
            return await self._generate_default_template(
                template_name, output_formats, ssh_keys, custom_config
            )
        
        with open(base_template_path) as f:
            base_template = f.read()
        
        # Customize template with parameters
        template = base_template.format(
            ssh_keys=json.dumps(ssh_keys),
            custom_config=json.dumps(custom_config),
            output_formats=json.dumps(output_formats),
            **custom_config
        )
        
        return template
    
    async def _generate_default_template(
        self,
        template_name: str,
        output_formats: List[str],
        ssh_keys: List[str],
        custom_config: Dict[str, Any]
    ) -> str:
        """Generate default Packer template for common distributions"""
        
        # Ubuntu 22.04 default template
        if "ubuntu" in template_name.lower():
            return f"""
packer {{
  required_plugins {{
    qemu = {{
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }}
  }}
}}

source "qemu" "ubuntu" {{
  iso_url          = "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
  iso_checksum     = "sha256:a4acfda10b18da50e2ec50ccaf860d7f20b389df8765611142305c0e911d16fd"
  output_directory = "{self.settings.output_dir}/{template_name}"
  vm_name          = "{template_name}.qcow2"
  format           = "qcow2"
  accelerator      = "{self.settings.qemu_accelerator}"
  
  memory           = {self.settings.memory_size}
  cpus             = 2
  disk_size        = "{self.settings.disk_size}"
  
  ssh_username     = "ubuntu"
  ssh_password     = "ubuntu"
  ssh_timeout      = "20m"
  
  boot_command = [
    "<enter><enter><f6><esc><wait> ",
    "autoinstall ds=nocloud-net;s=http://{{{{ .HTTPIP }}}}:{{{{ .HTTPPort }}}}/",
    "<enter>"
  ]
  
  http_directory = "{self.settings.templates_dir}/http"
  shutdown_command = "echo 'ubuntu' | sudo -S shutdown -P now"
}}

build {{
  sources = ["source.qemu.ubuntu"]
  
  provisioner "shell" {{
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y cloud-init",
      "sudo systemctl enable cloud-init"
    ]
  }}
  
  {self._generate_ssh_key_provisioner(ssh_keys)}
  
  post-processor "shell-local" {{
    inline = [
      {self._generate_format_conversions(output_formats)}
    ]
  }}
}}
"""
        
        # Generic template for other distributions  
        return self._generate_generic_template(template_name, output_formats, ssh_keys, custom_config)
    
    def _generate_ssh_key_provisioner(self, ssh_keys: List[str]) -> str:
        """Generate SSH key injection provisioner"""
        if not ssh_keys:
            return ""
        
        keys_json = json.dumps(ssh_keys)
        return f'''
  provisioner "shell" {{
    inline = [
      "mkdir -p /home/ubuntu/.ssh",
      "chmod 700 /home/ubuntu/.ssh",
      "echo '{keys_json}' | jq -r '.[]' >> /home/ubuntu/.ssh/authorized_keys",
      "chmod 600 /home/ubuntu/.ssh/authorized_keys",
      "chown -R ubuntu:ubuntu /home/ubuntu/.ssh"
    ]
  }}
'''
    
    def _generate_format_conversions(self, output_formats: List[str]) -> str:
        """Generate format conversion commands"""
        conversions = []
        
        for fmt in output_formats:
            if fmt != "qcow2":  # qcow2 is default output
                conversions.append(
                    f'"qemu-img convert -f qcow2 -O {fmt} '
                    f'{{{{ build.name }}}}/{{{{ build.name }}}}.qcow2 '
                    f'{{{{ build.name }}}}/{{{{ build.name }}}}.{fmt}"'
                )
        
        return ",\\n      ".join(conversions) if conversions else '""'
    
    def _generate_generic_template(
        self,
        template_name: str,
        output_formats: List[str],
        ssh_keys: List[str],
        custom_config: Dict[str, Any]
    ) -> str:
        """Generate generic template for custom configurations"""
        return f"""
# Generic Packer template for {template_name}
# Customize this template based on your requirements

packer {{
  required_plugins {{
    qemu = {{
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }}
  }}
}}

source "qemu" "generic" {{
  # ISO Configuration
  iso_url      = "{custom_config.get('iso_url', 'REQUIRED: Set iso_url in custom_config')}"
  iso_checksum = "{custom_config.get('iso_checksum', 'REQUIRED: Set iso_checksum in custom_config')}"
  
  # Output Configuration
  output_directory = "{self.settings.output_dir}/{template_name}"
  vm_name          = "{template_name}.qcow2"
  format           = "qcow2"
  
  # Hardware Configuration
  memory     = {custom_config.get('memory', self.settings.memory_size)}
  cpus       = {custom_config.get('cpus', 2)}
  disk_size  = "{custom_config.get('disk_size', self.settings.disk_size)}"
  
  # SSH Configuration  
  ssh_username = "{custom_config.get('ssh_username', 'root')}"
  ssh_password = "{custom_config.get('ssh_password', 'password')}"
  ssh_timeout = "20m"
  
  # Boot Configuration
  boot_command = {json.dumps(custom_config.get('boot_command', ['<enter>']))}
  
  shutdown_command = "{custom_config.get('shutdown_command', 'shutdown -P now')}"
}}

build {{
  sources = ["source.qemu.generic"]
  
  {self._generate_ssh_key_provisioner(ssh_keys)}
  
  post-processor "shell-local" {{
    inline = [
      {self._generate_format_conversions(output_formats)}
    ]
  }}
}}
"""
    
    async def _run_packer_build(self, template_path: Path, operation_id: str) -> str:
        """Execute packer build command"""
        build_args = [
            str(self.packer_binary),
            "build",
            "-color=false",
            f"-parallel-builds={self.settings.parallel_builds}",
            str(template_path)
        ]
        
        # Start process
        process = await asyncio.create_subprocess_exec(
            *build_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=self.settings.working_dir
        )
        
        # Stream output with timeout
        output_lines = []
        try:
            async for line in self._read_process_output(process):
                output_lines.append(line)
                self.logger.debug(f"Packer [{operation_id}]: {line.strip()}")
            
            await asyncio.wait_for(process.wait(), timeout=self.settings.timeout)
            
        except asyncio.TimeoutError:
            process.terminate()
            await process.wait()
            raise PackerError(f"Build timed out after {self.settings.timeout} seconds")
        
        if process.returncode != 0:
            output = "\\n".join(output_lines)
            raise PackerError(f"Packer build failed (exit code {process.returncode}):\\n{output}")
        
        return "\\n".join(output_lines)
    
    async def _read_process_output(self, process):
        """Async generator for reading process output line by line"""
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            yield line.decode('utf-8', errors='ignore')
    
    async def _process_build_results(
        self,
        template_name: str,
        output_formats: List[str],
        operation_id: str
    ) -> Dict[str, Path]:
        """Process and validate build results"""
        build_dir = self.settings.output_dir / template_name
        built_images = {}
        
        # Check for built images
        for fmt in ["qcow2"] + output_formats:
            image_path = build_dir / f"{template_name}.{fmt}"
            if image_path.exists():
                built_images[fmt] = image_path
                self.logger.info(f"Built image: {image_path} ({image_path.stat().st_size / (1024**2):.1f} MB)")
        
        if not built_images:
            raise PackerError("No images were produced by the build process")
        
        return built_images
    
    def _generate_cache_key(
        self,
        template_name: str,
        ssh_keys: List[str],
        custom_config: Dict[str, Any]
    ) -> str:
        """Generate cache key for built images"""
        cache_data = {
            "template_name": template_name,
            "ssh_keys": sorted(ssh_keys),  # Sort for consistent hashing
            "custom_config": custom_config,
            "packer_version": "1.9.0",  # TODO: Get actual version
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]
    
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
        
        # Clean up temporary template files
        temp_templates = list(self.settings.working_dir.glob(f"*-{operation_id}.*"))
        for temp_file in temp_templates:
            try:
                temp_file.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {temp_file}: {e}")


class ImageCache:
    """Image caching and management for Packer builds"""
    
    def __init__(self, settings: PackerSettings):
        self.settings = settings
        self.cache_dir = settings.output_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(f"{__name__}.ImageCache")
    
    async def get_cached_images(self, cache_key: str) -> Optional[Dict[str, Path]]:
        """Get cached images if available and valid"""
        cache_path = self.cache_dir / cache_key
        if not cache_path.exists():
            return None
        
        # Check cache age
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if cache_age > timedelta(days=self.settings.cache_retention_days):
            self.logger.info(f"Cache expired for {cache_key}")
            return None
        
        # Load cached image paths
        cached_images = {}
        for image_file in cache_path.glob("*"):
            if image_file.is_file():
                format_name = image_file.suffix[1:]  # Remove dot
                cached_images[format_name] = image_file
        
        return cached_images if cached_images else None
    
    async def cache_images(self, cache_key: str, images: Dict[str, Path]) -> None:
        """Cache built images"""
        cache_path = self.cache_dir / cache_key
        cache_path.mkdir(exist_ok=True)
        
        for fmt, image_path in images.items():
            cached_path = cache_path / f"image.{fmt}"
            shutil.copy2(image_path, cached_path)
            self.logger.info(f"Cached {fmt} image: {cached_path}")
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        cleaned = 0
        cutoff_time = datetime.now() - timedelta(days=self.settings.cache_retention_days)
        
        for cache_dir in self.cache_dir.iterdir():
            if cache_dir.is_dir():
                dir_time = datetime.fromtimestamp(cache_dir.stat().st_mtime)
                if dir_time < cutoff_time:
                    shutil.rmtree(cache_dir)
                    cleaned += 1
                    self.logger.info(f"Cleaned up expired cache: {cache_dir}")
        
        return cleaned