"""
Automation Configuration Settings

Pydantic-based configuration for automation tools including Terraform, Packer,
and other infrastructure automation providers.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .settings import CyRISSettings


class TerraformSettings(BaseSettings):
    """Configuration for Terraform automation provider"""
    
    enabled: bool = Field(True, description="Enable Terraform automation")
    binary_path: Optional[Path] = Field(None, description="Path to terraform binary")
    version: Optional[str] = Field(None, description="Required Terraform version")
    
    # Working directories
    working_dir: Path = Field(
        Path("~/.cyris/terraform").expanduser(),
        description="Terraform working directory"
    )
    templates_dir: Path = Field(
        Path("templates/terraform"),
        description="Terraform templates directory"
    )
    
    # Execution settings
    timeout: int = Field(3600, description="Operation timeout in seconds")
    retry_count: int = Field(3, description="Number of retry attempts")
    parallelism: int = Field(4, description="Terraform parallelism setting")
    
    # Provider-specific settings
    libvirt_uri: str = Field("qemu:///system", description="Libvirt connection URI")
    aws_region: str = Field("us-west-2", description="Default AWS region")
    
    # Feature flags
    auto_approve: bool = Field(False, description="Auto-approve terraform apply")
    destroy_on_error: bool = Field(True, description="Destroy resources on error")
    enable_logging: bool = Field(True, description="Enable detailed logging")
    
    model_config = {
        "env_prefix": "CYRIS_TERRAFORM_"
    }


class PackerSettings(BaseSettings):
    """Configuration for Packer image building provider"""
    
    enabled: bool = Field(True, description="Enable Packer automation")
    binary_path: Optional[Path] = Field(None, description="Path to packer binary")
    version: Optional[str] = Field(None, description="Required Packer version")
    
    # Working directories  
    working_dir: Path = Field(
        Path("~/.cyris/packer").expanduser(),
        description="Packer working directory"
    )
    templates_dir: Path = Field(
        Path("templates/packer"),
        description="Packer templates directory"
    )
    output_dir: Path = Field(
        Path("~/.cyris/images").expanduser(),
        description="Built images output directory"
    )
    
    # Image building settings
    timeout: int = Field(7200, description="Build timeout in seconds (2 hours)")
    retry_count: int = Field(2, description="Number of retry attempts")
    parallel_builds: int = Field(1, description="Number of parallel builds")
    
    # Image management
    cache_enabled: bool = Field(True, description="Enable image caching")
    cache_retention_days: int = Field(30, description="Image cache retention period")
    auto_cleanup: bool = Field(True, description="Auto cleanup old images")
    
    # Supported image formats
    output_formats: List[str] = Field(
        ["qcow2", "vmdk", "vhd"],
        description="Supported output image formats"
    )
    
    # Builder configurations
    qemu_accelerator: str = Field("kvm", description="QEMU accelerator (kvm/tcg)")
    memory_size: int = Field(2048, description="Build VM memory in MB") 
    disk_size: str = Field("20G", description="Build VM disk size")
    
    model_config = {
        "env_prefix": "CYRIS_PACKER_"
    }


class VagrantSettings(BaseSettings):
    """Configuration for Vagrant development automation (optional)"""
    
    enabled: bool = Field(False, description="Enable Vagrant automation")
    binary_path: Optional[Path] = Field(None, description="Path to vagrant binary")
    
    # Working directories
    working_dir: Path = Field(
        Path("~/.cyris/vagrant").expanduser(),
        description="Vagrant working directory"
    )
    
    # Provider settings
    default_provider: str = Field("libvirt", description="Default Vagrant provider")
    box_update_check: bool = Field(True, description="Check for box updates")
    
    # Development settings
    sync_folders: bool = Field(True, description="Enable synced folders")
    gui_enabled: bool = Field(False, description="Enable GUI for VMs")
    
    model_config = {
        "env_prefix": "CYRIS_VAGRANT_"
    }




class AWSSettings(BaseSettings):
    """Configuration for AWS automation provider"""
    
    enabled: bool = Field(True, description="Enable AWS automation")
    
    # Authentication
    access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    secret_access_key: Optional[str] = Field(None, description="AWS secret access key")
    use_iam_roles: bool = Field(True, description="Use IAM roles for authentication")
    
    # Region and availability
    region: str = Field("us-east-1", description="AWS region")
    availability_zones: List[str] = Field(default_factory=list, description="Preferred availability zones")
    
    # Working directories
    working_dir: Path = Field(
        Path("~/.cyris/aws").expanduser(),
        description="AWS working directory"
    )
    templates_dir: Path = Field(
        Path("~/.cyris/aws/templates").expanduser(),
        description="AWS CloudFormation/Terraform templates directory"
    )
    
    # Network settings
    vpc_id: Optional[str] = Field(None, description="Existing VPC ID to use")
    subnet_id: Optional[str] = Field(None, description="Existing subnet ID to use")
    default_vpc_cidr: str = Field("10.0.0.0/16", description="Default VPC CIDR block")
    
    # Instance defaults
    default_instance_type: str = Field("t3.micro", description="Default EC2 instance type")
    default_ami_id: Optional[str] = Field(None, description="Default AMI ID")
    key_pair_name: Optional[str] = Field(None, description="EC2 key pair name for SSH access")
    
    # Operation settings
    timeout: int = Field(1200, description="Operation timeout in seconds (20 minutes)")
    retry_count: int = Field(3, description="Number of retries for failed operations")
    
    # Resource management
    auto_tag_resources: bool = Field(True, description="Automatically tag resources")
    resource_cleanup: bool = Field(True, description="Enable automatic resource cleanup")
    cost_optimization: bool = Field(True, description="Enable cost optimization features")
    
    model_config = {
        "env_prefix": "CYRIS_AWS_"
    }


class ImageCacheSettings(BaseSettings):
    """Configuration for image caching and management"""
    
    enabled: bool = Field(True, description="Enable image caching")
    cache_dir: Path = Field(
        Path("~/.cyris/cache/images").expanduser(),
        description="Image cache directory"
    )
    
    # Cache management
    max_cache_size_gb: int = Field(50, description="Maximum cache size in GB")
    retention_days: int = Field(30, description="Cache retention period")
    cleanup_on_startup: bool = Field(True, description="Cleanup expired cache on startup")
    
    # Download settings
    download_timeout: int = Field(3600, description="Download timeout in seconds")
    concurrent_downloads: int = Field(3, description="Maximum concurrent downloads")
    verify_checksums: bool = Field(True, description="Verify downloaded checksums")
    
    # Mirror settings
    ubuntu_mirror: str = Field(
        "https://cloud-images.ubuntu.com/releases/",
        description="Ubuntu cloud images mirror"
    )
    centos_mirror: str = Field(
        "https://cloud.centos.org/centos/",
        description="CentOS cloud images mirror"
    )
    
    model_config = {
        "env_prefix": "CYRIS_IMAGE_CACHE_"
    }


class AutomationGlobalSettings(BaseSettings):
    """Global automation configuration settings"""
    
    # Feature flags
    automation_enabled: bool = Field(True, description="Enable automation features")
    legacy_fallback: bool = Field(True, description="Enable legacy fallback mode")
    parallel_operations: bool = Field(True, description="Enable parallel operations")
    
    # Logging and monitoring
    detailed_logging: bool = Field(True, description="Enable detailed automation logging")
    metrics_collection: bool = Field(False, description="Enable metrics collection")
    
    # Performance settings
    operation_timeout: int = Field(7200, description="Global operation timeout")
    max_concurrent_operations: int = Field(5, description="Max concurrent automation operations")
    
    # Error handling
    fail_fast: bool = Field(False, description="Fail fast on first error")
    auto_retry: bool = Field(True, description="Enable automatic retry on failures")
    cleanup_on_failure: bool = Field(True, description="Cleanup resources on failure")
    
    model_config = {
        "env_prefix": "CYRIS_AUTOMATION_"
    }


class CyRISAutomationSettings(CyRISSettings):
    """
    Extended CyRIS settings with automation capabilities.
    
    Extends the base CyRISSettings with configuration for automation
    tools and providers.
    """
    
    # Automation provider settings
    terraform: TerraformSettings = Field(default_factory=TerraformSettings)
    packer: PackerSettings = Field(default_factory=PackerSettings) 
    vagrant: VagrantSettings = Field(default_factory=VagrantSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    
    # Image and cache management
    image_cache: ImageCacheSettings = Field(default_factory=ImageCacheSettings)
    
    # Global automation settings
    automation: AutomationGlobalSettings = Field(default_factory=AutomationGlobalSettings)
    
    @field_validator('terraform', 'packer', 'vagrant', 'aws')
    @classmethod
    def ensure_automation_dirs(cls, v):
        """Ensure automation directories exist"""
        if hasattr(v, 'working_dir') and v.working_dir:
            v.working_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(v, 'templates_dir') and v.templates_dir:
            v.templates_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(v, 'output_dir') and v.output_dir:
            v.output_dir.mkdir(parents=True, exist_ok=True)
        return v
    
    def get_automation_status(self) -> Dict[str, bool]:
        """Get status of all automation providers"""
        return {
            'terraform_enabled': self.terraform.enabled,
            'packer_enabled': self.packer.enabled, 
            'vagrant_enabled': self.vagrant.enabled,
            'aws_enabled': self.aws.enabled,
            'image_cache_enabled': self.image_cache.enabled,
            'automation_enabled': self.automation.automation_enabled
        }
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled automation providers"""
        enabled = []
        if self.terraform.enabled:
            enabled.append('terraform')
        if self.packer.enabled:
            enabled.append('packer')
        if self.vagrant.enabled:
            enabled.append('vagrant')
        if self.aws.enabled:
            enabled.append('aws')
        return enabled
    
    model_config = {
        "env_file": ".env",
        "env_prefix": "CYRIS_"
    }