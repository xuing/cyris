"""
Unit Tests for AWS Infrastructure Builder

Tests the AWS automation provider functionality including EC2 deployment,
VPC management, and resource tracking without requiring actual AWS credentials.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from cyris.infrastructure.automation.aws_builder import (
    AWSBuilder,
    AWSError,
    ResourceTracker
)
from cyris.infrastructure.automation import (
    AutomationStatus,
    AutomationResult
)
from cyris.config.automation_settings import AWSSettings


class TestAWSBuilder:
    """Test AWS builder functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def aws_settings(self, temp_dir):
        """Create test AWS settings"""
        return AWSSettings(
            enabled=True,
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            use_iam_roles=False,
            region="us-east-1",
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates",
            timeout=300,
            retry_count=2,
            default_instance_type="t3.micro",
            key_pair_name="cyris-keypair"
        )
    
    @pytest.fixture
    def aws_builder(self, aws_settings):
        """Create AWS builder with mocked clients"""
        builder = AWSBuilder(aws_settings)
        return builder
    
    def test_aws_builder_initialization(self, aws_builder, aws_settings):
        """Test AWS builder initialization"""
        assert aws_builder.provider_type == "aws"
        assert aws_builder.is_enabled is True
        assert aws_builder.settings == aws_settings
        assert isinstance(aws_builder.resource_tracker, ResourceTracker)
        assert aws_builder.ec2_client is None  # Not connected yet
    
    @pytest.mark.asyncio
    async def test_connect_success(self, aws_builder):
        """Test successful connection to AWS"""
        # Mock boto3 session and clients
        mock_session = Mock()
        mock_ec2_client = Mock()
        mock_ec2_resource = Mock()
        mock_cf_client = Mock()
        
        mock_session.client.side_effect = lambda service: {
            'ec2': mock_ec2_client,
            'cloudformation': mock_cf_client
        }.get(service)
        mock_session.resource.return_value = mock_ec2_resource
        
        # Mock describe_regions response
        mock_ec2_client.describe_regions.return_value = {
            'Regions': [
                {'RegionName': 'us-east-1'},
                {'RegionName': 'us-west-2'}
            ]
        }
        
        with patch('boto3.Session', return_value=mock_session):
            await aws_builder.connect()
            
            assert aws_builder.is_connected is True
            assert aws_builder.ec2_client == mock_ec2_client
            assert aws_builder.ec2_resource == mock_ec2_resource
            assert aws_builder.cloudformation_client == mock_cf_client
    
    @pytest.mark.asyncio
    async def test_connect_invalid_region(self, aws_builder):
        """Test connection failure with invalid region"""
        aws_builder.settings.region = "invalid-region"
        
        mock_session = Mock()
        mock_ec2_client = Mock()
        mock_session.client.return_value = mock_ec2_client
        
        mock_ec2_client.describe_regions.return_value = {
            'Regions': [{'RegionName': 'us-east-1'}]
        }
        
        with patch('boto3.Session', return_value=mock_session):
            with pytest.raises(AWSError, match="Region invalid-region not available"):
                await aws_builder.connect()
    
    @pytest.mark.asyncio
    async def test_connect_authentication_failed(self, aws_builder):
        """Test connection failure with invalid credentials"""
        from botocore.exceptions import ClientError
        
        mock_session = Mock()
        mock_ec2_client = Mock()
        mock_session.client.return_value = mock_ec2_client
        
        # Mock authentication error
        error_response = {'Error': {'Code': 'InvalidUserID.NotFound', 'Message': 'Invalid user'}}
        mock_ec2_client.describe_regions.side_effect = ClientError(error_response, 'DescribeRegions')
        
        with patch('boto3.Session', return_value=mock_session):
            with pytest.raises(AWSError, match="AWS authentication failed"):
                await aws_builder.connect()
    
    @pytest.mark.asyncio
    async def test_validate_configuration_success(self, aws_builder):
        """Test successful configuration validation"""
        # Mock connection
        aws_builder._is_connected = True
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{'ZoneName': 'us-east-1a'}]
        }
        
        issues = await aws_builder.validate_configuration()
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_configuration_issues(self, aws_builder):
        """Test configuration validation with issues"""
        # Clear required settings to cause validation issues
        aws_builder.settings.region = ""
        aws_builder.settings.access_key_id = None
        aws_builder.settings.use_iam_roles = False
        
        issues = await aws_builder.validate_configuration()
        
        assert len(issues) > 0
        assert any("region is required" in issue.lower() for issue in issues)
        assert any("access key id is required" in issue.lower() for issue in issues)
    
    @pytest.mark.asyncio
    async def test_execute_deploy_operation_direct(self, aws_builder):
        """Test successful deploy operation using direct API"""
        # Mock AWS clients
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_resource = Mock()
        
        # Mock guest object
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.instance_type = "t3.micro"
        mock_guest.ami_id = "ami-12345678"
        mock_guest.ssh_keys = ["ssh-rsa AAAAB3..."]
        
        # Mock AWS responses
        with patch.object(aws_builder, '_deploy_direct', AsyncMock(return_value={
            'vpc': {'vpc_id': 'vpc-12345'},
            'security_groups': [{'group_id': 'sg-12345'}],
            'instances': [{'instance_id': 'i-12345', 'instance_name': 'test-vm'}]
        })):
            with patch.object(aws_builder.resource_tracker, 'track_deployment', AsyncMock()):
                
                parameters = {
                    "hosts": [],
                    "guests": [mock_guest],
                    "network_config": {"vpc": {"cidr_block": "10.0.0.0/16"}},
                    "deployment_method": "direct"
                }
                
                result = await aws_builder.execute_operation("deploy", parameters)
                
                assert result.status == AutomationStatus.COMPLETED
                assert "Successfully deployed" in result.output
                assert "deployed_resources" in result.artifacts
                assert result.artifacts["deployment_method"] == "direct"
    
    @pytest.mark.asyncio
    async def test_execute_deploy_operation_terraform(self, aws_builder):
        """Test deploy operation using Terraform"""
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        
        with patch.object(aws_builder, '_deploy_with_terraform', AsyncMock(return_value={
            'terraform_workspace': '/tmp/terraform-op123',
            'config_path': '/tmp/terraform-op123/main.tf',
            'status': 'terraform_ready'
        })):
            with patch.object(aws_builder.resource_tracker, 'track_deployment', AsyncMock()):
                
                parameters = {
                    "hosts": [],
                    "guests": [mock_guest],
                    "network_config": {},
                    "deployment_method": "terraform"
                }
                
                result = await aws_builder.execute_operation("deploy", parameters)
                
                assert result.status == AutomationStatus.COMPLETED
                assert result.artifacts["deployment_method"] == "terraform"
    
    @pytest.mark.asyncio
    async def test_execute_deploy_operation_failure(self, aws_builder):
        """Test deploy operation failure with cleanup"""
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        
        # Mock deployment failure
        with patch.object(aws_builder, '_deploy_direct', AsyncMock(side_effect=AWSError("Deployment failed"))):
            with patch.object(aws_builder, '_cleanup_failed_deployment', AsyncMock()) as cleanup_mock:
                
                parameters = {
                    "hosts": [],
                    "guests": [mock_guest],
                    "deployment_method": "direct"
                }
                
                result = await aws_builder.execute_operation("deploy", parameters)
                
                assert result.status == AutomationStatus.FAILED
                assert "Deployment failed" in result.error_message
                cleanup_mock.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_destroy_operation(self, aws_builder):
        """Test destroy operation"""
        resource_ids = ["i-12345", "sg-67890"]
        
        with patch.object(aws_builder, '_destroy_resources', AsyncMock(return_value=[
            {'resource_id': 'i-12345', 'resource_type': 'ec2_instance', 'action': 'terminated'}
        ])):
            
            parameters = {
                "resource_ids": resource_ids,
                "force_destroy": False
            }
            
            result = await aws_builder.execute_operation("destroy", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "Successfully destroyed" in result.output
            assert "destroyed_resources" in result.artifacts
    
    @pytest.mark.asyncio
    async def test_execute_validate_operation(self, aws_builder):
        """Test validate operation"""
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.instance_type = "t3.micro"
        
        with patch.object(aws_builder, '_validate_instance_config', AsyncMock(return_value={"errors": [], "warnings": []})):
            with patch.object(aws_builder, '_validate_network_config', AsyncMock(return_value={"errors": [], "warnings": []})):
                with patch.object(aws_builder, '_validate_aws_quotas', AsyncMock(return_value={"errors": [], "warnings": []})):
                    
                    parameters = {
                        "hosts": [],
                        "guests": [mock_guest],
                        "network_config": {"vpc": {"cidr_block": "10.0.0.0/16"}}
                    }
                    
                    result = await aws_builder.execute_operation("validate", parameters)
                    
                    assert result.status == AutomationStatus.COMPLETED
                    assert "validation passed" in result.output.lower()
                    assert result.artifacts["valid"] is True
    
    @pytest.mark.asyncio
    async def test_execute_list_operation(self, aws_builder):
        """Test list operation"""
        with patch.object(aws_builder, '_list_instances', AsyncMock(return_value=[
            {'instance_id': 'i-12345', 'state': 'running', 'instance_type': 't3.micro'}
        ])):
            with patch.object(aws_builder, '_list_vpcs', AsyncMock(return_value=[
                {'vpc_id': 'vpc-12345', 'state': 'available', 'cidr_block': '10.0.0.0/16'}
            ])):
                with patch.object(aws_builder, '_list_security_groups', AsyncMock(return_value=[
                    {'group_id': 'sg-12345', 'group_name': 'default'}
                ])):
                    
                    parameters = {"resource_type": "all", "tag_filters": {}}
                    
                    result = await aws_builder.execute_operation("list", parameters)
                    
                    assert result.status == AutomationStatus.COMPLETED
                    assert "Found" in result.output
                    assert "resources" in result.artifacts
                    assert "instances" in result.artifacts["resources"]
    
    @pytest.mark.asyncio
    async def test_create_vpc(self, aws_builder):
        """Test VPC creation"""
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_client.create_vpc.return_value = {
            'Vpc': {'VpcId': 'vpc-12345'}
        }
        aws_builder.ec2_client.create_tags.return_value = {}
        
        vpc_config = {"cidr_block": "10.0.0.0/16"}
        
        vpc = await aws_builder._create_vpc(vpc_config, "test-op")
        
        assert vpc['vpc_id'] == 'vpc-12345'
        assert vpc['cidr_block'] == '10.0.0.0/16'
        assert vpc['operation_id'] == 'test-op'
        
        # Verify create_vpc was called with correct parameters
        aws_builder.ec2_client.create_vpc.assert_called_once_with({'CidrBlock': '10.0.0.0/16'})
    
    @pytest.mark.asyncio
    async def test_create_security_groups(self, aws_builder):
        """Test security group creation"""
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_client.create_security_group.return_value = {
            'GroupId': 'sg-12345'
        }
        aws_builder.ec2_client.authorize_security_group_ingress.return_value = {}
        aws_builder.settings.vpc_id = 'vpc-12345'
        
        security_groups = await aws_builder._create_security_groups({}, "test-op")
        
        assert len(security_groups) == 1
        assert security_groups[0]['group_id'] == 'sg-12345'
        assert security_groups[0]['operation_id'] == 'test-op'
    
    @pytest.mark.asyncio
    async def test_create_instance(self, aws_builder):
        """Test EC2 instance creation"""
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_client.run_instances.return_value = {
            'Instances': [{
                'InstanceId': 'i-12345',
                'State': {'Name': 'pending'}
            }]
        }
        
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.instance_type = "t3.micro"
        mock_guest.ami_id = "ami-12345678"
        mock_guest.ssh_keys = ["ssh-rsa AAAAB3..."]
        
        security_groups = [{'group_id': 'sg-12345'}]
        
        instance = await aws_builder._create_instance(mock_guest, security_groups, "test-op")
        
        assert instance['instance_id'] == 'i-12345'
        assert instance['instance_name'] == 'test-vm'
        assert instance['instance_type'] == 't3.micro'
        assert instance['state'] == 'pending'
    
    def test_generate_user_data(self, aws_builder):
        """Test user data generation for cloud-init"""
        mock_guest = Mock()
        mock_guest.ssh_keys = ["ssh-rsa AAAAB3NzaC1yc2EAAAADA...", "ssh-ed25519 AAAAC3NzaC1lZDI1..."]
        
        user_data = aws_builder._generate_user_data(mock_guest)
        
        assert "#!/bin/bash" in user_data
        assert "CyRIS Instance Initialization" in user_data
        assert "yum update -y" in user_data
        assert "ssh-rsa AAAAB3NzaC1yc2EAAAADA..." in user_data
        assert "ssh-ed25519 AAAAC3NzaC1lZDI1..." in user_data
        assert "authorized_keys" in user_data
    
    @pytest.mark.asyncio
    async def test_generate_terraform_aws_config(self, aws_builder):
        """Test Terraform configuration generation for AWS"""
        mock_guest = Mock()
        mock_guest.name = "test-vm"
        mock_guest.instance_type = "t3.micro"
        
        config = await aws_builder._generate_terraform_aws_config(
            [], [mock_guest], {"vpc": {"cidr_block": "10.0.0.0/16"}}
        )
        
        assert "terraform" in config
        assert "aws" in config
        assert "hashicorp/aws" in config
        assert aws_builder.settings.region in config
        assert "test-vm" in config
        assert "t3.micro" in config
        assert "aws_vpc" in config
        assert "10.0.0.0/16" in config
    
    @pytest.mark.asyncio
    async def test_list_instances(self, aws_builder):
        """Test instance listing"""
        aws_builder.ec2_client = Mock()
        aws_builder.ec2_client.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'InstanceType': 't3.micro',
                    'LaunchTime': datetime.now(),
                    'Tags': [
                        {'Key': 'Name', 'Value': 'test-vm'},
                        {'Key': 'CyRIS-Operation', 'Value': 'test-op'}
                    ]
                }]
            }]
        }
        
        instances = await aws_builder._list_instances({})
        
        assert len(instances) == 1
        assert instances[0]['instance_id'] == 'i-12345'
        assert instances[0]['state'] == 'running'
        assert instances[0]['instance_type'] == 't3.micro'
        assert instances[0]['tags']['Name'] == 'test-vm'
    
    def test_generate_resource_summary(self, aws_builder):
        """Test resource summary generation"""
        deployed_resources = {
            'vpc': {'vpc_id': 'vpc-12345'},
            'instances': [
                {'instance_id': 'i-12345'},
                {'instance_id': 'i-67890'}
            ],
            'security_groups': [{'group_id': 'sg-12345'}]
        }
        
        summary = aws_builder._generate_resource_summary(deployed_resources)
        
        assert summary['total_resources'] == 4  # 1 VPC + 2 instances + 1 SG
        assert summary['resource_types']['instances'] == 2
        assert summary['resource_types']['security_groups'] == 1
        assert summary['estimated_cost_per_hour'] > 0
    
    @pytest.mark.asyncio
    async def test_validate_instance_config(self, aws_builder):
        """Test instance configuration validation"""
        mock_guest = Mock()
        mock_guest.instance_type = "t3.micro"
        mock_guest.ami_id = "ami-12345678"
        
        validation = await aws_builder._validate_instance_config(mock_guest)
        
        assert len(validation['errors']) == 0
        assert len(validation['warnings']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_instance_config_missing_fields(self, aws_builder):
        """Test instance validation with missing fields"""
        mock_guest = Mock()
        # Remove required attributes to simulate missing configuration
        del mock_guest.instance_type
        del mock_guest.ami_id
        aws_builder.settings.default_instance_type = None
        aws_builder.settings.default_ami_id = None
        
        validation = await aws_builder._validate_instance_config(mock_guest)
        
        assert len(validation['errors']) >= 2
        assert any("instance type" in error.lower() for error in validation['errors'])
        assert any("ami id" in error.lower() for error in validation['errors'])
    
    @pytest.mark.asyncio
    async def test_validate_network_config(self, aws_builder):
        """Test network configuration validation"""
        network_config = {
            "vpc": {
                "cidr_block": "10.0.0.0/16"
            }
        }
        
        validation = await aws_builder._validate_network_config(network_config)
        
        assert len(validation['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_network_config_invalid_cidr(self, aws_builder):
        """Test network validation with invalid CIDR"""
        network_config = {
            "vpc": {
                "cidr_block": "invalid-cidr"
            }
        }
        
        validation = await aws_builder._validate_network_config(network_config)
        
        assert len(validation['errors']) > 0
        assert any("cidr" in error.lower() for error in validation['errors'])
    
    @pytest.mark.asyncio
    async def test_validate_aws_quotas(self, aws_builder):
        """Test AWS quota validation"""
        # Create many guests to trigger quota warning
        guests = [Mock(name=f"guest-{i}") for i in range(25)]
        
        validation = await aws_builder._validate_aws_quotas(guests)
        
        assert len(validation['warnings']) > 0
        assert any("exceed default ec2 limits" in warning.lower() for warning in validation['warnings'])
    
    @pytest.mark.asyncio
    async def test_operation_tracking(self, aws_builder):
        """Test operation tracking functionality"""
        # Start operation
        parameters = {"hosts": [], "guests": [Mock(name="test")]}
        
        # Mock to avoid actual execution
        with patch.object(aws_builder, '_execute_deploy', AsyncMock()):
            result = await aws_builder.execute_operation("deploy", parameters)
            
            # Should be tracked during execution
            assert result.operation_id in aws_builder._active_operations
            
            # Clean up
            await aws_builder.cleanup_artifacts(result.operation_id)
            assert result.operation_id not in aws_builder._active_operations


class TestResourceTracker:
    """Test AWS resource tracking functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def tracker_settings(self, temp_dir):
        """Create resource tracker settings"""
        return AWSSettings(
            working_dir=temp_dir,
            templates_dir=temp_dir / "templates"
        )
    
    @pytest.fixture
    def resource_tracker(self, tracker_settings):
        """Create resource tracker instance"""
        return ResourceTracker(tracker_settings)
    
    @pytest.mark.asyncio
    async def test_track_deployment(self, resource_tracker):
        """Test deployment tracking"""
        deployment_id = "test-deployment-123"
        resources = {
            "instances": [{"instance_id": "i-12345"}],
            "vpc": {"vpc_id": "vpc-12345"}
        }
        
        # Currently a placeholder implementation
        await resource_tracker.track_deployment(deployment_id, resources)
        
        # Test passes if no exception is raised
        assert True
    
    @pytest.mark.asyncio
    async def test_get_deployment_resources(self, resource_tracker):
        """Test deployment resource retrieval"""
        deployment_id = "test-deployment-123"
        
        # Currently returns empty list (placeholder)
        resources = await resource_tracker.get_deployment_resources(deployment_id)
        
        assert isinstance(resources, list)


class TestAWSIntegration:
    """Integration tests for AWS builder (mocked)"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_end_to_end_aws_workflow(self, temp_dir):
        """Test complete AWS workflow from start to finish"""
        # Setup
        settings = AWSSettings(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            use_iam_roles=False,
            region="us-east-1",
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates",
            timeout=60,
            key_pair_name="test-keypair"
        )
        
        builder = AWSBuilder(settings)
        
        # Mock all AWS dependencies
        mock_session = Mock()
        mock_ec2_client = Mock()
        mock_ec2_resource = Mock()
        mock_cf_client = Mock()
        
        mock_session.client.side_effect = lambda service: {
            'ec2': mock_ec2_client,
            'cloudformation': mock_cf_client
        }.get(service)
        mock_session.resource.return_value = mock_ec2_resource
        
        # Mock AWS API responses
        mock_ec2_client.describe_regions.return_value = {
            'Regions': [{'RegionName': 'us-east-1'}]
        }
        mock_ec2_client.describe_availability_zones.return_value = {
            'AvailabilityZones': [{'ZoneName': 'us-east-1a'}]
        }
        
        with patch('boto3.Session', return_value=mock_session):
            with patch.object(builder, '_deploy_direct', AsyncMock(return_value={
                'instances': [{'instance_id': 'i-12345', 'instance_name': 'test-vm'}]
            })):
                with patch.object(builder.resource_tracker, 'track_deployment', AsyncMock()):
                    
                    # Connect
                    await builder.connect()
                    assert builder.is_connected
                    
                    # Validate configuration
                    issues = await builder.validate_configuration()
                    assert len(issues) == 0
                    
                    # Execute deployment
                    mock_guest = Mock()
                    mock_guest.name = "test-vm"
                    mock_guest.instance_type = "t3.micro"
                    
                    parameters = {
                        "hosts": [],
                        "guests": [mock_guest],
                        "network_config": {"vpc": {"cidr_block": "10.0.0.0/16"}},
                        "deployment_method": "direct"
                    }
                    
                    result = await builder.execute_operation("deploy", parameters)
                    
                    assert result.status == AutomationStatus.COMPLETED
                    assert "Successfully deployed" in result.output
                    assert "deployed_resources" in result.artifacts
                    
                    # Cleanup
                    await builder.cleanup_artifacts(result.operation_id)
                    await builder.disconnect()