"""
AWS Infrastructure Provider

This module provides AWS cloud infrastructure support for CyRIS,
implementing the infrastructure provider interface for cloud deployments.
"""

import logging
import time
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import json

from .base_provider import (
    InfrastructureProvider, ResourceInfo, ResourceStatus,
    InfrastructureError, ConnectionError, ResourceCreationError,
    ResourceDestructionError, ResourceNotFoundError
)
from ...domain.entities.host import Host
from ...domain.entities.guest import Guest


class AWSProvider(InfrastructureProvider):
    """
    AWS cloud infrastructure provider implementation.
    
    This provider manages EC2 instances, VPCs, security groups, and other
    AWS resources for cyber range deployment in the cloud.
    
    Capabilities:
    - EC2 instance management
    - VPC and subnet creation
    - Security group configuration
    - EBS volume management
    - AMI creation and management
    - Resource tagging and tracking
    
    Configuration:
    - region: AWS region (default: us-east-1)
    - access_key_id: AWS access key ID (optional, uses IAM roles if not provided)
    - secret_access_key: AWS secret access key (optional)
    - vpc_cidr: Default VPC CIDR block
    - instance_profile: IAM instance profile for EC2 instances
    - key_pair: EC2 key pair name for SSH access
    - default_ami: Default AMI ID for instances
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AWS provider.
        
        Args:
            config: Provider configuration dictionary
        """
        super().__init__("aws", config)
        
        # Configuration with defaults
        self.region = config.get("region", "us-east-1")
        self.access_key_id = config.get("access_key_id")
        self.secret_access_key = config.get("secret_access_key")
        self.vpc_cidr = config.get("vpc_cidr", "10.0.0.0/16")
        self.instance_profile = config.get("instance_profile")
        self.key_pair = config.get("key_pair")
        self.default_ami = config.get("default_ami", "ami-0abcdef1234567890")  # Ubuntu 20.04 LTS
        
        # AWS clients
        self._ec2_client: Optional[boto3.client] = None
        self._ec2_resource: Optional[boto3.resource] = None
        self.logger = logging.getLogger(__name__)
        
        # Resource tracking
        self._vpc_id: Optional[str] = None
        self._subnet_mapping: Dict[str, str] = {}  # subnet_name -> subnet_id
        self._security_groups: Dict[str, str] = {}  # group_name -> group_id
        
        self.logger.info(f"AWSProvider initialized for region: {self.region}")
    
    def connect(self) -> None:
        """
        Establish connection to AWS services.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            session_kwargs = {"region_name": self.region}
            
            if self.access_key_id and self.secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": self.access_key_id,
                    "aws_secret_access_key": self.secret_access_key
                })
            
            session = boto3.Session(**session_kwargs)
            
            # Create clients
            self._ec2_client = session.client("ec2")
            self._ec2_resource = session.resource("ec2")
            
            # Test connection
            response = self._ec2_client.describe_regions()
            if not response["Regions"]:
                raise ConnectionError("No AWS regions available")
            
            self.logger.info(f"Connected to AWS region: {self.region}")
            
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"AWS connection failed: {e}")
            raise ConnectionError(f"AWS connection failed: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to AWS: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Clean up and close connections"""
        # AWS SDK handles connection cleanup automatically
        self._ec2_client = None
        self._ec2_resource = None
        self.logger.info("Disconnected from AWS")
    
    def is_connected(self) -> bool:
        """Check if provider is connected and ready"""
        if not self._ec2_client:
            return False
        
        try:
            # Test connection with a simple API call
            self._ec2_client.describe_regions(RegionNames=[self.region])
            return True
        except:
            return False
    
    def create_hosts(self, hosts: List[Host]) -> List[str]:
        """
        Create host-level infrastructure (VPCs, subnets, security groups).
        
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
                self.logger.info(f"Creating AWS infrastructure for host {host.id}")
                
                # Create VPC for this range if not exists
                if not self._vpc_id:
                    self._vpc_id = self._create_vpc(host.id)
                
                # Create subnets based on host configuration
                subnet_ids = []
                for network_config in getattr(host, 'networks', []):
                    subnet_id = self._create_subnet(host.id, network_config, self._vpc_id)
                    subnet_ids.append(subnet_id)
                    self._subnet_mapping[network_config.get('name', 'default')] = subnet_id
                
                # Create security groups
                security_group_id = self._create_security_group(host.id, self._vpc_id)
                self._security_groups[host.id] = security_group_id
                
                # Register host resource
                host_resource = ResourceInfo(
                    resource_id=host.id,
                    resource_type="host",
                    name=host.id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "aws",
                        "vpc_id": self._vpc_id,
                        "subnet_ids": subnet_ids,
                        "security_group_id": security_group_id,
                        "region": self.region
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self._register_resource(host_resource)
                host_ids.append(host.id)
                
                self.logger.info(f"Successfully created AWS infrastructure for host {host.id}")
                
            except Exception as e:
                self.logger.error(f"Failed to create host {host.id}: {e}")
                raise ResourceCreationError(f"Host creation failed: {e}", "aws", host.id)
        
        return host_ids
    
    def create_guests(self, guests: List[Guest], host_mapping: Dict[str, str]) -> List[str]:
        """
        Create EC2 instances for virtual machines.
        
        Args:
            guests: List of guest configurations
            host_mapping: Mapping of guest host references to actual host IDs
        
        Returns:
            List of created guest resource IDs (instance IDs)
        
        Raises:
            InfrastructureError: If creation fails
        """
        if not self.is_connected():
            self.connect()
        
        guest_ids = []
        
        for guest in guests:
            try:
                self.logger.info(f"Creating EC2 instance for guest {guest.id}")
                
                # Determine host and subnet
                host_id = host_mapping.get(guest.host_id, list(host_mapping.values())[0])
                host_resource = self._resources.get(host_id)
                
                if not host_resource or "subnet_ids" not in host_resource.metadata:
                    raise ResourceCreationError(f"Host {host_id} not found or not properly configured")
                
                subnet_id = host_resource.metadata["subnet_ids"][0]  # Use first subnet
                security_group_id = host_resource.metadata["security_group_id"]
                
                # Select AMI based on OS type
                ami_id = self._get_ami_for_os(guest.os_type)
                
                # Select instance type based on guest specifications
                instance_type = self._get_instance_type(guest.memory_mb, guest.vcpus)
                
                # Prepare instance configuration
                instance_config = {
                    "ImageId": ami_id,
                    "MinCount": 1,
                    "MaxCount": 1,
                    "InstanceType": instance_type,
                    "KeyName": self.key_pair,
                    "SubnetId": subnet_id,
                    "SecurityGroupIds": [security_group_id],
                    "TagSpecifications": [
                        {
                            "ResourceType": "instance",
                            "Tags": [
                                {"Key": "Name", "Value": f"cyris-{guest.id}"},
                                {"Key": "CyRIS-GuestId", "Value": guest.id},
                                {"Key": "CyRIS-HostId", "Value": host_id},
                                {"Key": "CyRIS-Provider", "Value": "aws"}
                            ]
                        }
                    ]
                }
                
                # Add IAM instance profile if specified
                if self.instance_profile:
                    instance_config["IamInstanceProfile"] = {"Name": self.instance_profile}
                
                # Add user data if specified
                if hasattr(guest, 'user_data') and guest.user_data:
                    instance_config["UserData"] = guest.user_data
                
                # Launch instance
                response = self._ec2_client.run_instances(**instance_config)
                
                if not response["Instances"]:
                    raise ResourceCreationError("Failed to launch EC2 instance")
                
                instance = response["Instances"][0]
                instance_id = instance["InstanceId"]
                
                # Wait for instance to be running
                self._wait_for_instance_state(instance_id, "running")
                
                # Get updated instance info
                instance_info = self._get_instance_info(instance_id)
                
                # Register guest resource
                guest_resource = ResourceInfo(
                    resource_id=instance_id,
                    resource_type="guest",
                    name=guest.id,
                    status=ResourceStatus.ACTIVE,
                    metadata={
                        "provider": "aws",
                        "guest_id": guest.id,
                        "instance_id": instance_id,
                        "instance_type": instance_type,
                        "ami_id": ami_id,
                        "subnet_id": subnet_id,
                        "security_group_id": security_group_id,
                        "private_ip": instance_info.get("private_ip"),
                        "public_ip": instance_info.get("public_ip"),
                        "os_type": guest.os_type
                    },
                    created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                    ip_addresses=[
                        ip for ip in [
                            instance_info.get("private_ip"),
                            instance_info.get("public_ip")
                        ] if ip
                    ]
                )
                
                self._register_resource(guest_resource)
                guest_ids.append(instance_id)
                
                self.logger.info(f"Successfully created EC2 instance {instance_id} for guest {guest.id}")
                
            except Exception as e:
                self.logger.error(f"Failed to create guest {guest.id}: {e}")
                raise ResourceCreationError(f"Guest creation failed: {e}", "aws", guest.id)
        
        return guest_ids
    
    def destroy_hosts(self, host_ids: List[str]) -> None:
        """
        Destroy host-level infrastructure.
        
        Args:
            host_ids: List of host resource IDs to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        if not self.is_connected():
            self.connect()
        
        for host_id in host_ids:
            try:
                self.logger.info(f"Destroying AWS infrastructure for host {host_id}")
                
                host_resource = self._resources.get(host_id)
                if not host_resource:
                    self.logger.warning(f"Host {host_id} not found in registry")
                    continue
                
                metadata = host_resource.metadata
                
                # Delete security group
                if "security_group_id" in metadata:
                    self._delete_security_group(metadata["security_group_id"])
                
                # Delete subnets
                if "subnet_ids" in metadata:
                    for subnet_id in metadata["subnet_ids"]:
                        self._delete_subnet(subnet_id)
                
                # If this was the last host, delete VPC
                remaining_hosts = [
                    r for r in self._resources.values()
                    if r.resource_type == "host" and r.resource_id != host_id
                ]
                
                if not remaining_hosts and "vpc_id" in metadata:
                    self._delete_vpc(metadata["vpc_id"])
                    self._vpc_id = None
                
                # Unregister resource
                self._unregister_resource(host_id)
                
                self.logger.info(f"Successfully destroyed infrastructure for host {host_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to destroy host {host_id}: {e}")
                raise ResourceDestructionError(f"Host destruction failed: {e}", "aws", host_id)
    
    def destroy_guests(self, guest_ids: List[str]) -> None:
        """
        Destroy EC2 instances.
        
        Args:
            guest_ids: List of guest resource IDs (instance IDs) to destroy
        
        Raises:
            InfrastructureError: If destruction fails
        """
        if not self.is_connected():
            self.connect()
        
        for guest_id in guest_ids:
            try:
                self.logger.info(f"Terminating EC2 instance {guest_id}")
                
                # Terminate instance
                self._ec2_client.terminate_instances(InstanceIds=[guest_id])
                
                # Wait for termination
                self._wait_for_instance_state(guest_id, "terminated")
                
                # Unregister resource
                self._unregister_resource(guest_id)
                
                self.logger.info(f"Successfully terminated instance {guest_id}")
                
            except ClientError as e:
                if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                    self.logger.warning(f"Instance {guest_id} not found, may already be terminated")
                    self._unregister_resource(guest_id)
                else:
                    self.logger.error(f"Failed to destroy guest {guest_id}: {e}")
                    raise ResourceDestructionError(f"Guest destruction failed: {e}", "aws", guest_id)
            except Exception as e:
                self.logger.error(f"Failed to destroy guest {guest_id}: {e}")
                raise ResourceDestructionError(f"Guest destruction failed: {e}", "aws", guest_id)
    
    def get_status(self, resource_ids: List[str]) -> Dict[str, str]:
        """
        Get status of resources.
        
        Args:
            resource_ids: List of resource IDs to check
        
        Returns:
            Dictionary mapping resource ID to status string
        """
        if not self.is_connected():
            self.connect()
        
        status_map = {}
        
        for resource_id in resource_ids:
            try:
                resource = self._resources.get(resource_id)
                if not resource:
                    status_map[resource_id] = "not_found"
                    continue
                
                if resource.resource_type == "host":
                    # For hosts, check if VPC and subnets exist
                    vpc_id = resource.metadata.get("vpc_id")
                    if vpc_id:
                        try:
                            self._ec2_client.describe_vpcs(VpcIds=[vpc_id])
                            status_map[resource_id] = "active"
                        except ClientError:
                            status_map[resource_id] = "error"
                    else:
                        status_map[resource_id] = "active"
                
                elif resource.resource_type == "guest":
                    # For guests, check EC2 instance status
                    instance_id = resource.metadata.get("instance_id", resource_id)
                    try:
                        response = self._ec2_client.describe_instances(InstanceIds=[instance_id])
                        
                        if not response["Reservations"]:
                            status_map[resource_id] = "not_found"
                            continue
                        
                        instance = response["Reservations"][0]["Instances"][0]
                        state = instance["State"]["Name"]
                        
                        if state == "running":
                            status_map[resource_id] = "active"
                        elif state in ["pending", "stopping", "starting"]:
                            status_map[resource_id] = "creating"
                        elif state == "stopped":
                            status_map[resource_id] = "stopped"
                        elif state == "terminated":
                            status_map[resource_id] = "terminated"
                        else:
                            status_map[resource_id] = "unknown"
                    
                    except ClientError as e:
                        if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
                            status_map[resource_id] = "not_found"
                        else:
                            status_map[resource_id] = "error"
                
                else:
                    status_map[resource_id] = "unknown"
            
            except Exception as e:
                self.logger.error(f"Failed to get status for {resource_id}: {e}")
                status_map[resource_id] = "error"
        
        return status_map
    
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """Get detailed information about a resource"""
        resource = self._resources.get(resource_id)
        if not resource:
            return None
        
        # For EC2 instances, get current information
        if resource.resource_type == "guest":
            try:
                if self.is_connected():
                    instance_info = self._get_instance_info(
                        resource.metadata.get("instance_id", resource_id)
                    )
                    
                    # Update metadata and IP addresses
                    resource.metadata.update(instance_info)
                    resource.ip_addresses = [
                        ip for ip in [
                            instance_info.get("private_ip"),
                            instance_info.get("public_ip")
                        ] if ip
                    ]
                    
            except:
                pass  # Instance may not exist anymore
        
        return resource
    
    def _create_vpc(self, range_id: str) -> str:
        """Create VPC for the cyber range"""
        try:
            response = self._ec2_client.create_vpc(CidrBlock=self.vpc_cidr)
            vpc_id = response["Vpc"]["VpcId"]
            
            # Tag VPC
            self._ec2_client.create_tags(
                Resources=[vpc_id],
                Tags=[
                    {"Key": "Name", "Value": f"cyris-vpc-{range_id}"},
                    {"Key": "CyRIS-RangeId", "Value": range_id}
                ]
            )
            
            # Wait for VPC to be available
            waiter = self._ec2_client.get_waiter("vpc_available")
            waiter.wait(VpcIds=[vpc_id])
            
            self.logger.info(f"Created VPC {vpc_id} for range {range_id}")
            return vpc_id
            
        except ClientError as e:
            raise ResourceCreationError(f"VPC creation failed: {e}")
    
    def _create_subnet(self, range_id: str, network_config: Dict[str, Any], vpc_id: str) -> str:
        """Create subnet in VPC"""
        subnet_cidr = network_config.get("cidr", "10.0.1.0/24")
        subnet_name = network_config.get("name", "default")
        
        try:
            response = self._ec2_client.create_subnet(
                VpcId=vpc_id,
                CidrBlock=subnet_cidr
            )
            subnet_id = response["Subnet"]["SubnetId"]
            
            # Tag subnet
            self._ec2_client.create_tags(
                Resources=[subnet_id],
                Tags=[
                    {"Key": "Name", "Value": f"cyris-subnet-{range_id}-{subnet_name}"},
                    {"Key": "CyRIS-RangeId", "Value": range_id},
                    {"Key": "CyRIS-NetworkName", "Value": subnet_name}
                ]
            )
            
            self.logger.info(f"Created subnet {subnet_id} for range {range_id}")
            return subnet_id
            
        except ClientError as e:
            raise ResourceCreationError(f"Subnet creation failed: {e}")
    
    def _create_security_group(self, range_id: str, vpc_id: str) -> str:
        """Create security group for the range"""
        try:
            response = self._ec2_client.create_security_group(
                GroupName=f"cyris-sg-{range_id}",
                Description=f"CyRIS security group for range {range_id}",
                VpcId=vpc_id
            )
            sg_id = response["GroupId"]
            
            # Add default rules (SSH from anywhere for now)
            self._ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                    },
                    {
                        "IpProtocol": "icmp",
                        "FromPort": -1,
                        "ToPort": -1,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                    }
                ]
            )
            
            # Tag security group
            self._ec2_client.create_tags(
                Resources=[sg_id],
                Tags=[
                    {"Key": "Name", "Value": f"cyris-sg-{range_id}"},
                    {"Key": "CyRIS-RangeId", "Value": range_id}
                ]
            )
            
            self.logger.info(f"Created security group {sg_id} for range {range_id}")
            return sg_id
            
        except ClientError as e:
            raise ResourceCreationError(f"Security group creation failed: {e}")
    
    def _delete_vpc(self, vpc_id: str) -> None:
        """Delete VPC"""
        try:
            self._ec2_client.delete_vpc(VpcId=vpc_id)
            self.logger.info(f"Deleted VPC {vpc_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidVpcID.NotFound":
                raise
    
    def _delete_subnet(self, subnet_id: str) -> None:
        """Delete subnet"""
        try:
            self._ec2_client.delete_subnet(SubnetId=subnet_id)
            self.logger.info(f"Deleted subnet {subnet_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidSubnetID.NotFound":
                raise
    
    def _delete_security_group(self, sg_id: str) -> None:
        """Delete security group"""
        try:
            self._ec2_client.delete_security_group(GroupId=sg_id)
            self.logger.info(f"Deleted security group {sg_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidGroupId.NotFound":
                raise
    
    def _get_ami_for_os(self, os_type: str) -> str:
        """Get appropriate AMI ID for OS type"""
        # In a production implementation, this would maintain a mapping
        # of OS types to current AMI IDs, possibly with automatic updates
        ami_mapping = {
            "ubuntu.20.04": "ami-0abcdef1234567890",  # Ubuntu 20.04 LTS
            "ubuntu.18.04": "ami-0123456789abcdef0",  # Ubuntu 18.04 LTS
            "centos.7": "ami-0987654321fedcba0",      # CentOS 7
            "windows.10": "ami-0fedcba0123456789",    # Windows 10
            "kali.2021": "ami-0456789012345678a"      # Kali Linux
        }
        
        return ami_mapping.get(os_type, self.default_ami)
    
    def _get_instance_type(self, memory_mb: Optional[int], vcpus: Optional[int]) -> str:
        """Select appropriate EC2 instance type based on requirements"""
        memory_gb = (memory_mb or 1024) / 1024
        cpu_count = vcpus or 1
        
        # Simple mapping based on requirements
        if memory_gb <= 1 and cpu_count <= 1:
            return "t3.micro"
        elif memory_gb <= 2 and cpu_count <= 1:
            return "t3.small"
        elif memory_gb <= 4 and cpu_count <= 2:
            return "t3.medium"
        elif memory_gb <= 8 and cpu_count <= 2:
            return "t3.large"
        elif memory_gb <= 16 and cpu_count <= 4:
            return "t3.xlarge"
        else:
            return "t3.2xlarge"
    
    def _get_instance_info(self, instance_id: str) -> Dict[str, Any]:
        """Get current instance information"""
        try:
            response = self._ec2_client.describe_instances(InstanceIds=[instance_id])
            
            if not response["Reservations"]:
                return {}
            
            instance = response["Reservations"][0]["Instances"][0]
            
            return {
                "instance_state": instance["State"]["Name"],
                "private_ip": instance.get("PrivateIpAddress"),
                "public_ip": instance.get("PublicIpAddress"),
                "instance_type": instance["InstanceType"],
                "launch_time": instance.get("LaunchTime", "").strftime("%Y-%m-%d %H:%M:%S") if instance.get("LaunchTime") else None,
                "availability_zone": instance["Placement"]["AvailabilityZone"]
            }
            
        except ClientError:
            return {}
    
    def _wait_for_instance_state(self, instance_id: str, expected_state: str, timeout: int = 300) -> None:
        """Wait for instance to reach expected state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self._ec2_client.describe_instances(InstanceIds=[instance_id])
                
                if response["Reservations"]:
                    current_state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
                    if current_state == expected_state:
                        return
                    
                    # Check for error states
                    if current_state in ["terminated", "shutting-down"] and expected_state not in ["terminated", "shutting-down"]:
                        raise ResourceCreationError(f"Instance {instance_id} entered unexpected state: {current_state}")
                
                time.sleep(10)
                
            except ClientError as e:
                if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound" and expected_state == "terminated":
                    return  # Instance was terminated
                raise
        
        raise ResourceCreationError(f"Instance {instance_id} did not reach state {expected_state} within {timeout} seconds")