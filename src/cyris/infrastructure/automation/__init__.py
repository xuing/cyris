"""
Automation Infrastructure Module

Provides automation capabilities for VM provisioning, image building,
and infrastructure as code using tools like Terraform, Packer, and Vagrant.
"""

from .base_automation import (
    AutomationProvider,
    AutomationResult,
    AutomationStatus,
    AutomationError,
    AutomationConfig
)

from .packer_builder import PackerBuilder, PackerError
from .terraform_builder import TerraformBuilder, TerraformError
from .aws_builder import AWSBuilder, AWSError

__all__ = [
    'AutomationProvider',
    'AutomationResult', 
    'AutomationStatus',
    'AutomationError',
    'AutomationConfig',
    'PackerBuilder',
    'PackerError',
    'TerraformBuilder', 
    'TerraformError',
    'AWSBuilder',
    'AWSError'
]