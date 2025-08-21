"""
Integration tests for infrastructure providers.

These tests verify that the infrastructure providers properly implement
the provider interface and can manage resources correctly.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time
import subprocess

from src.cyris.infrastructure.providers.base_provider import (
    InfrastructureProvider, ResourceInfo, ResourceStatus, 
    InfrastructureError, ConnectionError
)
from src.cyris.infrastructure.providers.kvm_provider import KVMProvider
from src.cyris.infrastructure.providers.aws_provider import AWSProvider
from src.cyris.domain.entities.host import Host
from src.cyris.domain.entities.guest import Guest


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_hosts():
    """Create sample host configurations"""
    return [
        Host(
            id="test-host-1",
            mgmt_addr="192.168.1.10",
            virbr_addr="10.0.0.1"
        )
    ]


@pytest.fixture
def sample_guests():
    """Create sample guest configurations"""
    return [
        Guest(
            id="test-guest-1",
            host_id="test-host-1",
            os_type="ubuntu.20.04",
            memory_mb=2048,
            vcpus=2
        )
    ]


class TestKVMProvider:
    """Test KVM provider functionality"""
    
    @pytest.fixture
    def kvm_config(self, temp_dir):
        """Create KVM provider configuration"""
        return {
            "libvirt_uri": "test:///default",  # Use test URI for mocking
            "storage_pool": "test-pool",
            "network_prefix": "test-cyris",
            "vm_template_dir": str(temp_dir / "templates"),
            "base_image_dir": str(temp_dir / "images")
        }
    
    @pytest.fixture
    def kvm_provider(self, kvm_config):
        """Create KVM provider instance"""
        return KVMProvider(kvm_config)
    
    def test_provider_initialization(self, kvm_provider, kvm_config):
        """Test KVM provider initialization"""
        assert kvm_provider.provider_name == "kvm"
        assert kvm_provider.libvirt_uri == kvm_config["libvirt_uri"]
        assert kvm_provider.storage_pool == kvm_config["storage_pool"]
        assert not kvm_provider.is_connected()
    
    def test_provider_validation(self, kvm_provider):
        """Test configuration validation"""
        errors = kvm_provider.validate_configuration()
        assert len(errors) == 0  # Valid configuration should have no errors
        
        # Test invalid configuration
        invalid_provider = KVMProvider({})
        errors = invalid_provider.validate_configuration()
        assert len(errors) == 0  # Should use defaults
    
    @patch('libvirt.open')
    def test_connection_management(self, mock_libvirt_open, kvm_provider):
        """Test connection lifecycle"""
        # Mock libvirt connection
        mock_conn = Mock()
        mock_conn.isAlive.return_value = True
        mock_conn.getHostname.return_value = "test-host"
        mock_libvirt_open.return_value = mock_conn
        
        # Test connection
        assert not kvm_provider.is_connected()
        kvm_provider.connect()
        assert kvm_provider.is_connected()
        mock_libvirt_open.assert_called_once()
        
        # Test disconnect
        kvm_provider.disconnect()
        assert not kvm_provider.is_connected()
        mock_conn.close.assert_called_once()
    
    @patch('libvirt.open')
    def test_connection_failure(self, mock_libvirt_open, kvm_provider):
        """Test connection failure handling"""
        mock_libvirt_open.return_value = None
        
        with pytest.raises(ConnectionError):
            kvm_provider.connect()
    
    @patch('libvirt.open')
    def test_create_hosts(self, mock_libvirt_open, kvm_provider, sample_hosts):
        """Test host creation (network setup)"""
        # Mock libvirt connection
        mock_conn = Mock()
        mock_conn.isAlive.return_value = True
        mock_libvirt_open.return_value = mock_conn
        
        # Connect provider
        kvm_provider.connect()
        
        # Create hosts
        host_ids = kvm_provider.create_hosts(sample_hosts)
        
        # Verify results
        assert len(host_ids) == 1
        assert host_ids[0] == "test-host-1"
        
        # Verify resource registration
        resources = kvm_provider.list_resources(resource_type="host")
        assert len(resources) == 1
        assert resources[0].resource_id == "test-host-1"
        assert resources[0].status == ResourceStatus.ACTIVE
    
    @patch('libvirt.open')
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_create_guests(self, mock_path_exists, mock_subprocess, mock_libvirt_open, 
                          kvm_provider, sample_guests, temp_dir):
        """Test guest creation (VM creation)"""
        # Mock libvirt connection
        mock_conn = Mock()
        mock_conn.isAlive.return_value = True
        mock_libvirt_open.return_value = mock_conn
        
        # Mock VM domain
        mock_domain = Mock()
        mock_domain.create.return_value = 0
        mock_domain.state.return_value = (1, 0)  # VIR_DOMAIN_RUNNING
        mock_conn.defineXML.return_value = mock_domain
        
        # Mock subprocess calls for disk creation
        mock_subprocess.return_value = Mock(returncode=0)
        
        # Mock base image existence
        mock_path_exists.return_value = True
        
        # Connect provider
        kvm_provider.connect()
        
        # Create host mapping
        host_mapping = {"test-host-1": "host-test-host-1"}
        
        # Create guests
        guest_ids = kvm_provider.create_guests(sample_guests, host_mapping)
        
        # Verify results
        assert len(guest_ids) == 1
        assert guest_ids[0].startswith("test-cyris-test-guest-1-")
        
        # Verify VM was defined and started
        mock_conn.defineXML.assert_called_once()
        mock_domain.create.assert_called_once()
        
        # Verify resource registration
        resources = kvm_provider.list_resources(resource_type="guest")
        assert len(resources) == 1
        assert resources[0].status == ResourceStatus.ACTIVE
    
    @patch('libvirt.open')
    def test_get_status(self, mock_libvirt_open, kvm_provider, sample_hosts):
        """Test resource status retrieval"""
        # Mock libvirt connection
        mock_conn = Mock()
        mock_conn.isAlive.return_value = True
        mock_libvirt_open.return_value = mock_conn
        
        # Connect and create host
        kvm_provider.connect()
        host_ids = kvm_provider.create_hosts(sample_hosts)
        
        # Get status
        statuses = kvm_provider.get_status(host_ids)
        
        assert len(statuses) == 1
        assert statuses[host_ids[0]] == "active"
        
        # Test non-existent resource
        statuses = kvm_provider.get_status(["non-existent"])
        assert statuses["non-existent"] == "not_found"


class TestAWSProvider:
    """Test AWS provider functionality"""
    
    @pytest.fixture
    def aws_config(self):
        """Create AWS provider configuration"""
        return {
            "region": "us-east-1",
            "access_key_id": "test-access-key",
            "secret_access_key": "test-secret-key",
            "vpc_cidr": "10.0.0.0/16",
            "key_pair": "test-keypair",
            "default_ami": "ami-12345678"
        }
    
    @pytest.fixture
    def aws_provider(self, aws_config):
        """Create AWS provider instance"""
        return AWSProvider(aws_config)
    
    def test_provider_initialization(self, aws_provider, aws_config):
        """Test AWS provider initialization"""
        assert aws_provider.provider_name == "aws"
        assert aws_provider.region == aws_config["region"]
        assert aws_provider.access_key_id == aws_config["access_key_id"]
        assert not aws_provider.is_connected()
    
    @patch('boto3.Session')
    def test_connection_management(self, mock_session, aws_provider):
        """Test connection lifecycle"""
        # Mock boto3 session and clients
        mock_session_instance = Mock()
        mock_ec2_client = Mock()
        mock_ec2_resource = Mock()
        
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_ec2_client
        mock_session_instance.resource.return_value = mock_ec2_resource
        
        # Mock successful region description
        mock_ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
        
        # Test connection
        assert not aws_provider.is_connected()
        aws_provider.connect()
        assert aws_provider.is_connected()
        
        # Verify session creation
        mock_session.assert_called_once()
        mock_session_instance.client.assert_called_with("ec2")
        mock_session_instance.resource.assert_called_with("ec2")
    
    @patch('boto3.Session')
    def test_connection_failure(self, mock_session, aws_provider):
        """Test connection failure handling"""
        mock_session_instance = Mock()
        mock_ec2_client = Mock()
        
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_ec2_client
        
        # Mock connection failure
        mock_ec2_client.describe_regions.return_value = {"Regions": []}
        
        with pytest.raises(ConnectionError):
            aws_provider.connect()
    
    @patch('boto3.Session')
    def test_create_hosts(self, mock_session, aws_provider, sample_hosts):
        """Test host creation (VPC/subnet setup)"""
        # Mock boto3 session and clients
        mock_session_instance = Mock()
        mock_ec2_client = Mock()
        
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_ec2_client
        
        # Mock successful connection
        mock_ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
        
        # Mock VPC creation
        mock_ec2_client.create_vpc.return_value = {"Vpc": {"VpcId": "vpc-12345"}}
        
        # Mock waiter
        mock_waiter = Mock()
        mock_ec2_client.get_waiter.return_value = mock_waiter
        
        # Mock subnet creation
        mock_ec2_client.create_subnet.return_value = {"Subnet": {"SubnetId": "subnet-12345"}}
        
        # Mock security group creation
        mock_ec2_client.create_security_group.return_value = {"GroupId": "sg-12345"}
        
        # Connect provider
        aws_provider.connect()
        
        # Create hosts
        host_ids = aws_provider.create_hosts(sample_hosts)
        
        # Verify results
        assert len(host_ids) == 1
        assert host_ids[0] == "test-host-1"
        
        # Verify AWS API calls
        mock_ec2_client.create_vpc.assert_called_once()
        mock_ec2_client.create_security_group.assert_called_once()
        
        # Verify resource registration
        resources = aws_provider.list_resources(resource_type="host")
        assert len(resources) == 1
        assert resources[0].resource_id == "test-host-1"
    
    @patch('boto3.Session')
    def test_create_guests(self, mock_session, aws_provider, sample_guests):
        """Test guest creation (EC2 instances)"""
        # Mock boto3 session and clients
        mock_session_instance = Mock()
        mock_ec2_client = Mock()
        
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_ec2_client
        
        # Mock successful connection
        mock_ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
        
        # Connect and setup provider state
        aws_provider.connect()
        aws_provider._vpc_id = "vpc-12345"
        
        # Mock host resource
        host_resource = ResourceInfo(
            resource_id="test-host-1",
            resource_type="host",
            name="test-host-1",
            status=ResourceStatus.ACTIVE,
            metadata={
                "subnet_ids": ["subnet-12345"],
                "security_group_id": "sg-12345"
            }
        )
        aws_provider._register_resource(host_resource)
        
        # Mock instance launch
        mock_ec2_client.run_instances.return_value = {
            "Instances": [{"InstanceId": "i-12345678"}]
        }
        
        # Mock instance status check
        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-12345678",
                    "State": {"Name": "running"},
                    "InstanceType": "t3.medium",
                    "PrivateIpAddress": "10.0.1.10",
                    "PublicIpAddress": "1.2.3.4",
                    "Placement": {"AvailabilityZone": "us-east-1a"},
                    "LaunchTime": time.time()
                }]
            }]
        }
        
        # Create host mapping
        host_mapping = {"test-host-1": "test-host-1"}
        
        # Create guests
        guest_ids = aws_provider.create_guests(sample_guests, host_mapping)
        
        # Verify results
        assert len(guest_ids) == 1
        assert guest_ids[0] == "i-12345678"
        
        # Verify AWS API calls
        mock_ec2_client.run_instances.assert_called_once()
        
        # Verify resource registration
        resources = aws_provider.list_resources(resource_type="guest")
        assert len(resources) == 1
        assert resources[0].resource_id == "i-12345678"
    
    @patch('boto3.Session')
    def test_get_status(self, mock_session, aws_provider):
        """Test resource status retrieval"""
        # Mock boto3 session and clients
        mock_session_instance = Mock()
        mock_ec2_client = Mock()
        
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_ec2_client
        
        # Mock successful connection
        mock_ec2_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
        
        # Connect provider
        aws_provider.connect()
        
        # Register test resources
        host_resource = ResourceInfo(
            resource_id="test-host",
            resource_type="host", 
            name="test-host",
            status=ResourceStatus.ACTIVE,
            metadata={"vpc_id": "vpc-12345"}
        )
        aws_provider._register_resource(host_resource)
        
        guest_resource = ResourceInfo(
            resource_id="i-12345678",
            resource_type="guest",
            name="test-guest",
            status=ResourceStatus.ACTIVE,
            metadata={"instance_id": "i-12345678"}
        )
        aws_provider._register_resource(guest_resource)
        
        # Mock VPC description for host status
        mock_ec2_client.describe_vpcs.return_value = {"Vpcs": [{"VpcId": "vpc-12345"}]}
        
        # Mock instance description for guest status
        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [{
                "Instances": [{
                    "InstanceId": "i-12345678",
                    "State": {"Name": "running"}
                }]
            }]
        }
        
        # Get status
        statuses = aws_provider.get_status(["test-host", "i-12345678"])
        
        assert statuses["test-host"] == "active"
        assert statuses["i-12345678"] == "active"


class TestProviderInterface:
    """Test provider interface compliance"""
    
    def test_kvm_provider_interface(self):
        """Test that KVM provider implements the interface correctly"""
        config = {"libvirt_uri": "test:///default"}
        provider = KVMProvider(config)
        
        # Test interface methods exist
        assert hasattr(provider, 'connect')
        assert hasattr(provider, 'disconnect')
        assert hasattr(provider, 'is_connected')
        assert hasattr(provider, 'create_hosts')
        assert hasattr(provider, 'create_guests')
        assert hasattr(provider, 'destroy_hosts')
        assert hasattr(provider, 'destroy_guests')
        assert hasattr(provider, 'get_status')
        assert hasattr(provider, 'get_resource_info')
        
        # Test properties
        assert provider.provider_name == "kvm"
        assert isinstance(provider.config, dict)
    
    def test_aws_provider_interface(self):
        """Test that AWS provider implements the interface correctly"""
        config = {"region": "us-east-1"}
        provider = AWSProvider(config)
        
        # Test interface methods exist
        assert hasattr(provider, 'connect')
        assert hasattr(provider, 'disconnect')
        assert hasattr(provider, 'is_connected')
        assert hasattr(provider, 'create_hosts')
        assert hasattr(provider, 'create_guests')
        assert hasattr(provider, 'destroy_hosts')
        assert hasattr(provider, 'destroy_guests')
        assert hasattr(provider, 'get_status')
        assert hasattr(provider, 'get_resource_info')
        
        # Test properties
        assert provider.provider_name == "aws"
        assert isinstance(provider.config, dict)
    
    def test_provider_statistics(self):
        """Test provider statistics functionality"""
        config = {"libvirt_uri": "test:///default"}
        provider = KVMProvider(config)
        
        # Get initial statistics
        stats = provider.get_provider_info()
        
        assert "provider_name" in stats
        assert "connected" in stats
        assert "total_resources" in stats
        assert stats["provider_name"] == "kvm"
        assert stats["connected"] is False
        assert stats["total_resources"] == 0