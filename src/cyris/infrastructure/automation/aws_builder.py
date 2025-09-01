"""
AWS Infrastructure Builder Implementation

Provides automated cloud infrastructure provisioning using AWS services.
Integrates with Terraform for Infrastructure as Code and direct AWS API calls.
"""

import json
import asyncio
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .base_automation import (
    AutomationProvider, AutomationConfig, AutomationResult, 
    AutomationStatus, AutomationError
)
from ...config.automation_settings import AWSSettings
from ...core.exceptions import CyRISVirtualizationError


class AWSError(AutomationError):
    """AWS-specific errors"""
    pass


class AWSBuilder(AutomationProvider):
    """
    AWS-based infrastructure builder for automated cloud provisioning.
    
    Capabilities:
    - EC2 instance creation and management
    - VPC and networking setup
    - Security group configuration
    - AMI creation and management
    - CloudFormation stack deployment
    - Terraform integration for complex deployments
    
    Typical workflow:
    1. Validate AWS credentials and region access
    2. Create or use existing VPC infrastructure
    3. Deploy EC2 instances with user data
    4. Configure security groups and networking
    5. Track resources and provide access information
    """
    
    def __init__(self, settings: AWSSettings):
        """
        Initialize AWS builder.
        
        Args:
            settings: AWS configuration settings
        """
        config = AutomationConfig(
            provider_type="aws",
            enabled=settings.enabled,
            timeout=settings.timeout,
            retry_count=settings.retry_count,
            working_directory=settings.working_dir,
            debug_mode=True
        )
        super().__init__(config)
        
        self.settings = settings
        self.resource_tracker = ResourceTracker(settings)
        
        # AWS clients (initialized on connect)
        self.ec2_client = None
        self.ec2_resource = None
        self.cloudformation_client = None
        
        # Create required directories
        settings.working_dir.mkdir(parents=True, exist_ok=True)
        settings.templates_dir.mkdir(parents=True, exist_ok=True)
    
    async def connect(self) -> None:
        """Connect to AWS and verify credentials"""
        try:
            # Initialize AWS clients
            session = boto3.Session(
                aws_access_key_id=self.settings.access_key_id,
                aws_secret_access_key=self.settings.secret_access_key,
                region_name=self.settings.region
            )
            
            self.ec2_client = session.client('ec2')
            self.ec2_resource = session.resource('ec2')
            self.cloudformation_client = session.client('cloudformation')
            
            # Verify credentials by calling describe_regions
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.ec2_client.describe_regions
            )
            
            # Verify the specified region exists
            available_regions = [region['RegionName'] for region in response['Regions']]
            if self.settings.region not in available_regions:
                raise AWSError(f"Region {self.settings.region} not available")
            
            self.logger.info(f"Connected to AWS region: {self.settings.region}")
            self._is_connected = True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise AWSError(f"AWS authentication failed ({error_code}): {str(e)}")
        except BotoCoreError as e:
            raise AWSError(f"AWS connection failed: {str(e)}")
        except Exception as e:
            raise AWSError(f"Failed to connect to AWS: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from AWS provider"""
        self.ec2_client = None
        self.ec2_resource = None
        self.cloudformation_client = None
        self._is_connected = False
        self.logger.info("Disconnected from AWS")
    
    async def validate_configuration(self) -> List[str]:
        """Validate AWS configuration"""
        issues = []
        
        # Check required settings
        if not self.settings.region:
            issues.append("AWS region is required")
        
        # Check authentication (if not using IAM roles)
        if not self.settings.access_key_id and not self.settings.use_iam_roles:
            issues.append("AWS access key ID is required when not using IAM roles")
        
        if not self.settings.secret_access_key and not self.settings.use_iam_roles:
            issues.append("AWS secret access key is required when not using IAM roles")
        
        # Check directories
        if not self.settings.working_dir.exists():
            issues.append(f"Working directory missing: {self.settings.working_dir}")
        
        # Verify AWS credentials if provided
        if self.is_connected:
            try:
                # Test basic AWS API access
                await asyncio.get_event_loop().run_in_executor(
                    None, self.ec2_client.describe_availability_zones
                )
            except Exception as e:
                issues.append(f"AWS API access failed: {str(e)}")
        
        return issues
    
    async def execute_operation(
        self,
        operation_type: str,
        parameters: Dict[str, Any],
        operation_id: Optional[str] = None
    ) -> AutomationResult:
        """
        Execute AWS infrastructure operation.
        
        Args:
            operation_type: Type of operation ('deploy', 'destroy', 'validate', 'list')
            parameters: Operation parameters
            operation_id: Optional operation ID
            
        Returns:
            AWS operation result
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
            if operation_type == "deploy":
                await self._execute_deploy(parameters, result)
            elif operation_type == "destroy":
                await self._execute_destroy(parameters, result)
            elif operation_type == "validate":
                await self._execute_validate(parameters, result)
            elif operation_type == "list":
                await self._execute_list(parameters, result)
            else:
                raise AWSError(f"Unknown operation type: {operation_type}")
            
            result.status = AutomationStatus.COMPLETED
            result.completed_at = datetime.now()
            
        except Exception as e:
            result.status = AutomationStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            self.logger.error(f"AWS operation failed: {e}")
        
        return result
    
    async def _execute_deploy(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute infrastructure deployment operation"""
        operation_id = result.operation_id
        hosts = parameters.get("hosts", [])
        guests = parameters.get("guests", [])
        network_config = parameters.get("network_config", {})
        deployment_method = parameters.get("deployment_method", "direct")  # 'direct' or 'terraform'
        
        if not hosts and not guests:
            raise AWSError("At least one host or guest is required for deployment")
        
        deployed_resources = {}
        
        try:
            if deployment_method == "terraform":
                # Use Terraform for complex deployments
                deployed_resources = await self._deploy_with_terraform(
                    hosts, guests, network_config, operation_id
                )
            else:
                # Use direct AWS API calls for simple deployments
                deployed_resources = await self._deploy_direct(
                    hosts, guests, network_config, operation_id
                )
            
            # Track resources for management
            await self.resource_tracker.track_deployment(operation_id, deployed_resources)
            
            result.output = f"Successfully deployed {len(deployed_resources)} AWS resources"
            result.artifacts = {
                "deployment_method": deployment_method,
                "deployed_resources": deployed_resources,
                "resource_summary": self._generate_resource_summary(deployed_resources)
            }
            
        except Exception as e:
            # Clean up any partially created resources
            await self._cleanup_failed_deployment(operation_id, deployed_resources)
            raise AWSError(f"Deployment failed: {str(e)}")
    
    async def _execute_destroy(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Execute infrastructure destruction operation"""
        operation_id = result.operation_id
        target_resources = parameters.get("resource_ids", [])
        deployment_id = parameters.get("deployment_id")
        force_destroy = parameters.get("force_destroy", False)
        
        destroyed_resources = []
        
        try:
            if deployment_id:
                # Destroy entire deployment
                resources = await self.resource_tracker.get_deployment_resources(deployment_id)
                destroyed_resources = await self._destroy_resources(resources, force_destroy)
            elif target_resources:
                # Destroy specific resources
                destroyed_resources = await self._destroy_resources(target_resources, force_destroy)
            else:
                raise AWSError("Either deployment_id or resource_ids must be provided")
            
            result.output = f"Successfully destroyed {len(destroyed_resources)} AWS resources"
            result.artifacts = {
                "destroyed_resources": destroyed_resources,
                "destruction_summary": self._generate_destruction_summary(destroyed_resources)
            }
            
        except Exception as e:
            raise AWSError(f"Destruction failed: {str(e)}")
    
    async def _execute_validate(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """Validate AWS deployment configuration"""
        hosts = parameters.get("hosts", [])
        guests = parameters.get("guests", [])
        network_config = parameters.get("network_config", {})
        
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        try:
            # Validate instance configurations
            for guest in guests:
                instance_validation = await self._validate_instance_config(guest)
                if instance_validation.get("errors"):
                    validation_results["errors"].extend(instance_validation["errors"])
                    validation_results["valid"] = False
                if instance_validation.get("warnings"):
                    validation_results["warnings"].extend(instance_validation["warnings"])
            
            # Validate network configurations
            if network_config:
                network_validation = await self._validate_network_config(network_config)
                if network_validation.get("errors"):
                    validation_results["errors"].extend(network_validation["errors"])
                    validation_results["valid"] = False
                if network_validation.get("warnings"):
                    validation_results["warnings"].extend(network_validation["warnings"])
            
            # Validate AWS limits and quotas
            quota_validation = await self._validate_aws_quotas(guests)
            if quota_validation.get("errors"):
                validation_results["errors"].extend(quota_validation["errors"])
                validation_results["valid"] = False
            
            result.output = f"Configuration validation {'passed' if validation_results['valid'] else 'failed'}"
            result.artifacts = validation_results
            
        except Exception as e:
            raise AWSError(f"Validation failed: {str(e)}")
    
    async def _execute_list(self, parameters: Dict[str, Any], result: AutomationResult) -> None:
        """List AWS resources"""
        resource_type = parameters.get("resource_type", "all")  # 'instances', 'vpcs', 'security_groups', 'all'
        tag_filters = parameters.get("tag_filters", {})
        
        resources = {}
        
        try:
            if resource_type in ["instances", "all"]:
                resources["instances"] = await self._list_instances(tag_filters)
            
            if resource_type in ["vpcs", "all"]:
                resources["vpcs"] = await self._list_vpcs(tag_filters)
            
            if resource_type in ["security_groups", "all"]:
                resources["security_groups"] = await self._list_security_groups(tag_filters)
            
            total_resources = sum(len(resource_list) for resource_list in resources.values())
            
            result.output = f"Found {total_resources} AWS resources"
            result.artifacts = {
                "resources": resources,
                "resource_counts": {k: len(v) for k, v in resources.items()}
            }
            
        except Exception as e:
            raise AWSError(f"Resource listing failed: {str(e)}")
    
    async def _deploy_direct(
        self, 
        hosts: List[Any], 
        guests: List[Any], 
        network_config: Dict[str, Any],
        operation_id: str
    ) -> Dict[str, Any]:
        """Deploy using direct AWS API calls"""
        deployed_resources = {}
        
        # Create VPC if needed
        vpc_config = network_config.get("vpc", {})
        if vpc_config and not self.settings.vpc_id:
            vpc = await self._create_vpc(vpc_config, operation_id)
            deployed_resources["vpc"] = vpc
        
        # Create security groups
        security_groups = await self._create_security_groups(network_config, operation_id)
        deployed_resources["security_groups"] = security_groups
        
        # Deploy EC2 instances for guests
        instances = []
        for guest in guests:
            instance = await self._create_instance(guest, security_groups, operation_id)
            instances.append(instance)
        
        deployed_resources["instances"] = instances
        
        return deployed_resources
    
    async def _deploy_with_terraform(
        self,
        hosts: List[Any],
        guests: List[Any],
        network_config: Dict[str, Any],
        operation_id: str
    ) -> Dict[str, Any]:
        """Deploy using Terraform (delegated to TerraformBuilder)"""
        # This would integrate with TerraformBuilder for complex deployments
        # For now, return a placeholder implementation
        
        terraform_config = await self._generate_terraform_aws_config(hosts, guests, network_config)
        
        # Write Terraform configuration
        workspace_dir = self.settings.working_dir / f"terraform-{operation_id}"
        workspace_dir.mkdir(exist_ok=True)
        
        config_path = workspace_dir / "main.tf"
        with open(config_path, 'w') as f:
            f.write(terraform_config)
        
        # TODO: Integrate with TerraformBuilder to execute
        # For now, return simulated deployment
        return {
            "terraform_workspace": str(workspace_dir),
            "config_path": str(config_path),
            "status": "terraform_ready"
        }
    
    async def _create_vpc(self, vpc_config: Dict[str, Any], operation_id: str) -> Dict[str, Any]:
        """Create VPC with subnets"""
        try:
            vpc_response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.ec2_client.create_vpc,
                {'CidrBlock': vpc_config.get('cidr_block', '10.0.0.0/16')}
            )
            
            vpc_id = vpc_response['Vpc']['VpcId']
            
            # Tag the VPC
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.ec2_client.create_tags,
                {
                    'Resources': [vpc_id],
                    'Tags': [
                        {'Key': 'Name', 'Value': f'cyris-vpc-{operation_id}'},
                        {'Key': 'CyRIS-Operation', 'Value': operation_id}
                    ]
                }
            )
            
            return {
                'vpc_id': vpc_id,
                'cidr_block': vpc_config.get('cidr_block', '10.0.0.0/16'),
                'operation_id': operation_id
            }
            
        except ClientError as e:
            raise AWSError(f"Failed to create VPC: {str(e)}")
    
    async def _create_security_groups(self, network_config: Dict[str, Any], operation_id: str) -> List[Dict[str, Any]]:
        """Create security groups for network access"""
        security_groups = []
        
        try:
            # Create default security group for CyRIS
            sg_response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.ec2_client.create_security_group,
                {
                    'GroupName': f'cyris-sg-{operation_id}',
                    'Description': f'CyRIS Security Group for operation {operation_id}',
                    'VpcId': self.settings.vpc_id or 'default'
                }
            )
            
            sg_id = sg_response['GroupId']
            
            # Add common rules
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.ec2_client.authorize_security_group_ingress,
                {
                    'GroupId': sg_id,
                    'IpPermissions': [
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 22,
                            'ToPort': 22,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        },
                        {
                            'IpProtocol': 'icmp',
                            'FromPort': -1,
                            'ToPort': -1,
                            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                        }
                    ]
                }
            )
            
            security_groups.append({
                'group_id': sg_id,
                'group_name': f'cyris-sg-{operation_id}',
                'operation_id': operation_id
            })
            
            return security_groups
            
        except ClientError as e:
            raise AWSError(f"Failed to create security groups: {str(e)}")
    
    async def _create_instance(
        self, 
        guest: Any, 
        security_groups: List[Dict[str, Any]], 
        operation_id: str
    ) -> Dict[str, Any]:
        """Create EC2 instance for guest"""
        try:
            instance_name = getattr(guest, 'name', f'cyris-instance-{operation_id}')
            instance_type = getattr(guest, 'instance_type', self.settings.default_instance_type)
            ami_id = getattr(guest, 'ami_id', self.settings.default_ami_id)
            
            # Prepare user data for SSH key injection
            user_data = self._generate_user_data(guest)
            
            instance_response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.ec2_client.run_instances,
                {
                    'ImageId': ami_id,
                    'MinCount': 1,
                    'MaxCount': 1,
                    'InstanceType': instance_type,
                    'KeyName': self.settings.key_pair_name,
                    'SecurityGroupIds': [sg['group_id'] for sg in security_groups],
                    'UserData': user_data,
                    'TagSpecifications': [
                        {
                            'ResourceType': 'instance',
                            'Tags': [
                                {'Key': 'Name', 'Value': instance_name},
                                {'Key': 'CyRIS-Operation', 'Value': operation_id},
                                {'Key': 'CyRIS-Guest', 'Value': instance_name}
                            ]
                        }
                    ]
                }
            )
            
            instance = instance_response['Instances'][0]
            
            return {
                'instance_id': instance['InstanceId'],
                'instance_name': instance_name,
                'instance_type': instance_type,
                'ami_id': ami_id,
                'operation_id': operation_id,
                'state': instance['State']['Name']
            }
            
        except ClientError as e:
            raise AWSError(f"Failed to create instance for {getattr(guest, 'name', 'unknown')}: {str(e)}")
    
    def _generate_user_data(self, guest: Any) -> str:
        """Generate cloud-init user data for instance configuration"""
        ssh_keys = getattr(guest, 'ssh_keys', [])
        
        user_data = """#!/bin/bash
# CyRIS Instance Initialization

# Update system
yum update -y

# Install common tools
yum install -y htop vim curl wget

# Configure SSH
systemctl enable sshd
systemctl start sshd
"""
        
        # Add SSH keys if provided
        if ssh_keys:
            user_data += "\n# Add SSH keys\n"
            user_data += "mkdir -p /home/ec2-user/.ssh\n"
            for key in ssh_keys:
                user_data += f"echo '{key}' >> /home/ec2-user/.ssh/authorized_keys\n"
            user_data += "chown -R ec2-user:ec2-user /home/ec2-user/.ssh\n"
            user_data += "chmod 700 /home/ec2-user/.ssh\n"
            user_data += "chmod 600 /home/ec2-user/.ssh/authorized_keys\n"
        
        return user_data
    
    async def _generate_terraform_aws_config(
        self,
        hosts: List[Any],
        guests: List[Any], 
        network_config: Dict[str, Any]
    ) -> str:
        """Generate Terraform configuration for AWS deployment"""
        config = f"""
# CyRIS AWS Terraform Configuration
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{self.settings.region}"
}}

# Variables
variable "operation_id" {{
  description = "CyRIS operation identifier"
  type        = string
  default     = "default"
}}

# Data sources
data "aws_ami" "default" {{
  most_recent = true
  owners      = ["amazon"]
  
  filter {{
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }}
}}
"""
        
        # Add VPC configuration if needed
        if not self.settings.vpc_id:
            config += """
# VPC Configuration
resource "aws_vpc" "cyris_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "cyris-vpc-${var.operation_id}"
    CyRIS-Operation = var.operation_id
  }
}

resource "aws_internet_gateway" "cyris_igw" {
  vpc_id = aws_vpc.cyris_vpc.id
  
  tags = {
    Name = "cyris-igw-${var.operation_id}"
    CyRIS-Operation = var.operation_id
  }
}

resource "aws_subnet" "cyris_subnet" {
  vpc_id                  = aws_vpc.cyris_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "cyris-subnet-${var.operation_id}"
    CyRIS-Operation = var.operation_id
  }
}
"""
        
        # Add security group
        config += """
# Security Group
resource "aws_security_group" "cyris_sg" {
  name_prefix = "cyris-sg-"
  vpc_id      = aws_vpc.cyris_vpc.id
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "cyris-sg-${var.operation_id}"
    CyRIS-Operation = var.operation_id
  }
}
"""
        
        # Add instances for guests
        for i, guest in enumerate(guests):
            guest_name = getattr(guest, 'name', f'guest-{i}')
            instance_type = getattr(guest, 'instance_type', self.settings.default_instance_type)
            
            config += f"""
# Instance: {guest_name}
resource "aws_instance" "{guest_name.replace('-', '_')}" {{
  ami           = data.aws_ami.default.id
  instance_type = "{instance_type}"
  key_name      = "{self.settings.key_pair_name}"
  
  vpc_security_group_ids = [aws_security_group.cyris_sg.id]
  subnet_id              = aws_subnet.cyris_subnet.id
  
  tags = {{
    Name = "{guest_name}"
    CyRIS-Operation = var.operation_id
    CyRIS-Guest = "{guest_name}"
  }}
}}
"""
        
        return config
    
    def _generate_resource_summary(self, deployed_resources: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of deployed resources"""
        summary = {
            "total_resources": 0,
            "resource_types": {},
            "estimated_cost_per_hour": 0.0
        }
        
        for resource_type, resources in deployed_resources.items():
            if isinstance(resources, list):
                count = len(resources)
                summary["resource_types"][resource_type] = count
                summary["total_resources"] += count
            else:
                summary["resource_types"][resource_type] = 1
                summary["total_resources"] += 1
        
        # Rough cost estimation (would need real AWS pricing API)
        instance_count = summary["resource_types"].get("instances", 0)
        summary["estimated_cost_per_hour"] = instance_count * 0.10  # Rough estimate
        
        return summary
    
    def _generate_destruction_summary(self, destroyed_resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of destroyed resources"""
        return {
            "total_destroyed": len(destroyed_resources),
            "resource_types": {},  # Would categorize by type
            "estimated_cost_savings_per_hour": len(destroyed_resources) * 0.10
        }
    
    async def _validate_instance_config(self, guest: Any) -> Dict[str, Any]:
        """Validate individual instance configuration"""
        validation = {"errors": [], "warnings": []}
        
        # Check instance type
        instance_type = getattr(guest, 'instance_type', self.settings.default_instance_type)
        if not instance_type:
            validation["errors"].append("Instance type is required")
        
        # Check AMI ID
        ami_id = getattr(guest, 'ami_id', self.settings.default_ami_id)
        if not ami_id:
            validation["errors"].append("AMI ID is required")
        
        return validation
    
    async def _validate_network_config(self, network_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate network configuration"""
        validation = {"errors": [], "warnings": []}
        
        # Validate VPC configuration
        vpc_config = network_config.get("vpc", {})
        if vpc_config and "cidr_block" in vpc_config:
            # Basic CIDR validation
            cidr = vpc_config["cidr_block"]
            if not ("/" in cidr and "." in cidr):
                validation["errors"].append(f"Invalid CIDR block format: {cidr}")
        
        return validation
    
    async def _validate_aws_quotas(self, guests: List[Any]) -> Dict[str, Any]:
        """Validate against AWS service quotas"""
        validation = {"errors": [], "warnings": []}
        
        # Check instance count against typical limits
        instance_count = len(guests)
        if instance_count > 20:  # Default EC2 limit is often 20
            validation["warnings"].append(f"Requesting {instance_count} instances may exceed default EC2 limits")
        
        return validation
    
    async def _list_instances(self, tag_filters: Dict[str, str]) -> List[Dict[str, Any]]:
        """List EC2 instances with optional filtering"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.ec2_client.describe_instances
            )
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'instance_id': instance['InstanceId'],
                        'state': instance['State']['Name'],
                        'instance_type': instance['InstanceType'],
                        'launch_time': instance.get('LaunchTime'),
                        'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    })
            
            return instances
            
        except ClientError as e:
            raise AWSError(f"Failed to list instances: {str(e)}")
    
    async def _list_vpcs(self, tag_filters: Dict[str, str]) -> List[Dict[str, Any]]:
        """List VPCs with optional filtering"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.ec2_client.describe_vpcs
            )
            
            vpcs = []
            for vpc in response['Vpcs']:
                vpcs.append({
                    'vpc_id': vpc['VpcId'],
                    'state': vpc['State'],
                    'cidr_block': vpc['CidrBlock'],
                    'is_default': vpc['IsDefault'],
                    'tags': {tag['Key']: tag['Value'] for tag in vpc.get('Tags', [])}
                })
            
            return vpcs
            
        except ClientError as e:
            raise AWSError(f"Failed to list VPCs: {str(e)}")
    
    async def _list_security_groups(self, tag_filters: Dict[str, str]) -> List[Dict[str, Any]]:
        """List security groups with optional filtering"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.ec2_client.describe_security_groups
            )
            
            security_groups = []
            for sg in response['SecurityGroups']:
                security_groups.append({
                    'group_id': sg['GroupId'],
                    'group_name': sg['GroupName'],
                    'description': sg['Description'],
                    'vpc_id': sg.get('VpcId'),
                    'tags': {tag['Key']: tag['Value'] for tag in sg.get('Tags', [])}
                })
            
            return security_groups
            
        except ClientError as e:
            raise AWSError(f"Failed to list security groups: {str(e)}")
    
    async def _destroy_resources(self, resources: List[str], force_destroy: bool) -> List[Dict[str, Any]]:
        """Destroy specified AWS resources"""
        destroyed = []
        
        # This is a simplified implementation
        # Real implementation would handle different resource types properly
        for resource_id in resources:
            if resource_id.startswith('i-'):  # EC2 instance
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        self.ec2_client.terminate_instances,
                        {'InstanceIds': [resource_id]}
                    )
                    destroyed.append({
                        'resource_id': resource_id,
                        'resource_type': 'ec2_instance',
                        'action': 'terminated'
                    })
                except ClientError as e:
                    if not force_destroy:
                        raise AWSError(f"Failed to destroy {resource_id}: {str(e)}")
        
        return destroyed
    
    async def _cleanup_failed_deployment(self, operation_id: str, resources: Dict[str, Any]) -> None:
        """Clean up resources from failed deployment"""
        self.logger.warning(f"Cleaning up failed deployment {operation_id}")
        
        # Extract resource IDs and attempt cleanup
        resource_ids = []
        for resource_type, resource_list in resources.items():
            if isinstance(resource_list, list):
                for resource in resource_list:
                    if isinstance(resource, dict) and 'instance_id' in resource:
                        resource_ids.append(resource['instance_id'])
        
        if resource_ids:
            try:
                await self._destroy_resources(resource_ids, force_destroy=True)
            except Exception as e:
                self.logger.error(f"Failed to cleanup resources: {e}")
    
    async def get_operation_status(self, operation_id: str) -> Optional[AutomationResult]:
        """Get status of specific operation"""
        return self._active_operations.get(operation_id)
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel running operation"""
        if operation_id in self._active_operations:
            result = self._active_operations[operation_id]
            result.status = AutomationStatus.CANCELLED
            return True
        return False
    
    async def cleanup_artifacts(self, operation_id: str) -> None:
        """Clean up artifacts from completed operation"""
        self._untrack_operation(operation_id)
        
        # Clean up temporary files
        temp_files = list(self.settings.working_dir.glob(f"*{operation_id}*"))
        for temp_file in temp_files:
            try:
                if temp_file.is_dir():
                    import shutil
                    shutil.rmtree(temp_file)
                else:
                    temp_file.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {temp_file}: {e}")


class ResourceTracker:
    """AWS resource tracking and management"""
    
    def __init__(self, settings: AWSSettings):
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.ResourceTracker")
    
    async def track_deployment(self, deployment_id: str, resources: Dict[str, Any]) -> None:
        """Track resources for a deployment"""
        # TODO: Implement resource tracking (could use DynamoDB, local file, etc.)
        pass
    
    async def get_deployment_resources(self, deployment_id: str) -> List[str]:
        """Get resources for a deployment"""
        # TODO: Implement resource retrieval
        return []