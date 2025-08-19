"""
测试配置文件 - pytest fixture定义
"""
import pytest
import tempfile
import os
import yaml
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def temp_dir():
    """临时目录fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """示例配置fixture"""
    return {
        'cyris_path': '/tmp/cyris/',
        'cyber_range_dir': '/tmp/cyris/cyber_range/',
        'gw_mode': 'off'
    }


@pytest.fixture
def sample_yaml_description():
    """示例YAML描述文件fixture"""
    return {
        'host_settings': [
            {
                'id': 'host_1',
                'mgmt_addr': 'localhost',
                'virbr_addr': '192.168.122.1',
                'account': 'cyuser'
            }
        ],
        'guest_settings': [
            {
                'id': 'desktop',
                'basevm_host': 'host_1',
                'basevm_config_file': '/home/cyuser/images/basevm.xml',
                'basevm_type': 'kvm'
            }
        ],
        'clone_settings': [
            {
                'range_id': 123,
                'hosts': [
                    {
                        'host_id': 'host_1',
                        'instance_number': 1,
                        'guests': [
                            {
                                'guest_id': 'desktop',
                                'number': 1,
                                'entry_point': True
                            }
                        ],
                        'topology': [
                            {
                                'type': 'custom',
                                'networks': [
                                    {
                                        'name': 'office',
                                        'members': ['desktop.eth0']
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def config_file(temp_dir, sample_config):
    """配置文件fixture"""
    config_path = temp_dir / "config.ini"
    
    with open(config_path, 'w') as f:
        f.write("[config]\n")
        for key, value in sample_config.items():
            f.write(f"{key} = {value}\n")
    
    return config_path


@pytest.fixture
def yaml_file(temp_dir, sample_yaml_description):
    """YAML描述文件fixture"""
    yaml_path = temp_dir / "test_range.yml"
    
    with open(yaml_path, 'w') as f:
        yaml.dump(sample_yaml_description, f, default_flow_style=False)
    
    return yaml_path


@pytest.fixture
def mock_paramiko():
    """模拟paramiko SSH客户端"""
    with patch('paramiko.SSHClient') as mock_ssh:
        mock_client = Mock()
        mock_ssh.return_value = mock_client
        
        # 设置默认的SSH操作返回值
        mock_client.exec_command.return_value = (
            Mock(),  # stdin
            Mock(read=Mock(return_value=b"success")),  # stdout  
            Mock(read=Mock(return_value=b""))  # stderr
        )
        
        yield mock_client


@pytest.fixture
def mock_boto3():
    """模拟boto3 AWS客户端"""
    with patch('boto3.client') as mock_client:
        mock_ec2 = Mock()
        mock_client.return_value = mock_ec2
        
        # 设置默认的AWS操作返回值
        mock_ec2.create_instances.return_value = {
            'Instances': [
                {'InstanceId': 'i-1234567890abcdef0'}
            ]
        }
        
        yield mock_ec2


@pytest.fixture
def mock_subprocess():
    """模拟subprocess调用"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="success",
            stderr=""
        )
        yield mock_run


class MockHost:
    """模拟Host实体"""
    def __init__(self, host_id="test_host", mgmt_addr="localhost"):
        self.host_id = host_id
        self.mgmt_addr = mgmt_addr
        self.account = "testuser"


class MockGuest:
    """模拟Guest实体"""
    def __init__(self, guest_id="test_guest", basevm_type="kvm"):
        self.guest_id = guest_id
        self.basevm_type = basevm_type
        self.basevm_host = "test_host"


@pytest.fixture
def mock_host():
    """模拟主机实体fixture"""
    return MockHost()


@pytest.fixture
def mock_guest():
    """模拟虚拟机实体fixture"""
    return MockGuest()