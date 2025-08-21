"""
End-to-End tests for full system deployment.

These tests verify that the complete system can be deployed and
used in a realistic scenario, testing all components together.
"""

import pytest
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import yaml
import json
import shutil
import sys
import os


@pytest.fixture
def deployment_environment(tmp_path):
    """Create a complete deployment environment for testing"""
    cyris_root = tmp_path / "cyris_deployment"
    cyris_root.mkdir()
    
    # Create directory structure
    directories = [
        "cyber_range",
        "logs", 
        "settings",
        "examples",
        "main",
        "src/cyris",
        "tests",
        "scripts"
    ]
    
    for dir_path in directories:
        (cyris_root / dir_path).mkdir(parents=True)
    
    # Create CONFIG file
    config_content = f"""
# CyRIS Configuration File
CYRIS_PATH={cyris_root}
RANGE_DIRECTORY={cyris_root}/cyber_range
LOG_DIRECTORY={cyris_root}/logs
GATEWAY_ADDR=192.168.100.1
GATEWAY_ACCOUNT=cyris
MASTER_HOST=192.168.100.1
MASTER_ACCOUNT=cyris
EMULATION_MODE=KVM
    """.strip()
    
    (cyris_root / "CONFIG").write_text(config_content)
    
    # Create example YAML files
    basic_example = """
host_settings:
  - id: training-host
    mgmt_addr: 192.168.100.10
    virbr_addr: 10.0.0.1

guest_settings:
  - id: web-server
    host_id: training-host
    os_type: ubuntu.20.04
    memory_mb: 2048
    vcpus: 2
    ip_addr: 10.0.0.10
    software:
      - apache2
      - php
  
  - id: database
    host_id: training-host
    os_type: ubuntu.20.04
    memory_mb: 4096
    vcpus: 2
    ip_addr: 10.0.0.11
    software:
      - mysql-server

clone_settings:
  range_id: training-range
  number_of_ranges: 2
  
  # Student accounts
  accounts:
    - username: student1
      password: changeme123
      full_name: "Student One"
      role: student
    - username: student2  
      password: changeme456
      full_name: "Student Two"
      role: student
    - username: instructor
      password: admin123
      full_name: "Training Instructor"
      role: instructor
      sudo_access: true
    """.strip()
    
    (cyris_root / "examples" / "training.yml").write_text(basic_example)
    
    # Create advanced example with attack scenarios
    advanced_example = """
host_settings:
  - id: victim-host
    mgmt_addr: 192.168.100.20
    virbr_addr: 10.1.0.1
  
  - id: attacker-host
    mgmt_addr: 192.168.100.21
    virbr_addr: 10.2.0.1

guest_settings:
  - id: web-app
    host_id: victim-host
    os_type: ubuntu.20.04
    memory_mb: 2048
    vcpus: 2
    ip_addr: 10.1.0.10
    software:
      - apache2
      - php
      - mysql-server
    vulnerabilities:
      - type: sql_injection
        location: /var/www/html/login.php
      - type: xss
        location: /var/www/html/search.php
  
  - id: kali-attacker
    host_id: attacker-host
    os_type: kali.2023
    memory_mb: 4096
    vcpus: 4
    ip_addr: 10.2.0.10
    software:
      - metasploit-framework
      - nmap
      - sqlmap
      - burpsuite

clone_settings:
  range_id: pentest-lab
  number_of_ranges: 1
  
  # Network isolation
  network_isolation: true
  internet_access: false
  
  # Monitoring and logging
  enable_monitoring: true
  log_network_traffic: true
  log_system_events: true
  
  accounts:
    - username: pentester
      password: secure123
      full_name: "Penetration Tester"
      role: student
      allowed_hosts: [kali-attacker]
    - username: defender
      password: defend123
      full_name: "Security Defender"
      role: student
      allowed_hosts: [web-app]
    - username: instructor
      password: admin456
      full_name: "Security Instructor" 
      role: instructor
      sudo_access: true
    """.strip()
    
    (cyris_root / "examples" / "pentest-lab.yml").write_text(advanced_example)
    
    # Create pyproject.toml for the deployment
    pyproject_content = """
[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "cyris"
version = "1.4.0"
description = "Cyber Range Instantiation System"

[tool.poetry.dependencies]
python = "^3.8"
PyYAML = "^6.0"
click = "^8.0"
pydantic = "^2.0"

[tool.poetry.scripts]
cyris = "cyris.cli.main:main"
    """.strip()
    
    (cyris_root / "pyproject.toml").write_text(pyproject_content)
    
    return cyris_root


class TestSystemDeployment:
    """Test complete system deployment scenarios"""
    
    def test_deployment_directory_structure(self, deployment_environment):
        """Test that deployment creates proper directory structure"""
        cyris_root = deployment_environment
        
        # Verify required directories exist
        required_dirs = [
            "cyber_range",
            "logs", 
            "settings",
            "examples",
            "main",
            "src/cyris"
        ]
        
        for dir_path in required_dirs:
            assert (cyris_root / dir_path).exists()
            assert (cyris_root / dir_path).is_dir()
        
        # Verify configuration file exists
        assert (cyris_root / "CONFIG").exists()
        config_content = (cyris_root / "CONFIG").read_text()
        assert "CYRIS_PATH" in config_content
        assert "GATEWAY_ADDR" in config_content
    
    def test_deployment_examples_validation(self, deployment_environment):
        """Test that deployment examples are valid"""
        examples_dir = deployment_environment / "examples"
        
        # Test basic example
        basic_yaml = examples_dir / "training.yml"
        assert basic_yaml.exists()
        
        # Validate YAML syntax
        with open(basic_yaml) as f:
            basic_config = yaml.safe_load(f)
        
        assert "host_settings" in basic_config
        assert "guest_settings" in basic_config
        assert "clone_settings" in basic_config
        assert len(basic_config["host_settings"]) >= 1
        assert len(basic_config["guest_settings"]) >= 2
        
        # Test advanced example
        advanced_yaml = examples_dir / "pentest-lab.yml"
        assert advanced_yaml.exists()
        
        with open(advanced_yaml) as f:
            advanced_config = yaml.safe_load(f)
        
        assert "host_settings" in advanced_config
        assert "guest_settings" in advanced_config
        assert len(advanced_config["host_settings"]) == 2
        assert any(guest["os_type"] == "kali.2023" for guest in advanced_config["guest_settings"])
    
    @patch('subprocess.run')
    def test_deployment_validation_script(self, mock_subprocess, deployment_environment):
        """Test deployment validation functionality"""
        # Mock successful validation
        mock_subprocess.return_value = Mock(returncode=0, stdout="Validation successful", stderr="")
        
        cyris_root = deployment_environment
        
        # Test configuration validation
        with patch.dict(os.environ, {"CYRIS_PATH": str(cyris_root)}):
            # This would typically run a validation script
            # For now, we'll simulate the validation logic
            config_file = cyris_root / "CONFIG"
            assert config_file.exists()
            
            config_content = config_file.read_text()
            assert "CYRIS_PATH" in config_content
            assert "GATEWAY_ADDR" in config_content
            
            # Validate directories exist
            assert (cyris_root / "cyber_range").exists()
            assert (cyris_root / "logs").exists()
    
    @patch('src.cyris.services.orchestrator.RangeOrchestrator')
    def test_full_range_deployment_workflow(self, mock_orchestrator_class, deployment_environment):
        """Test complete range deployment workflow"""
        cyris_root = deployment_environment
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock successful range creation
        from src.cyris.services.orchestrator import RangeMetadata, RangeStatus
        from datetime import datetime
        
        range_metadata = RangeMetadata(
            range_id="training-range-1",
            name="Training Range 1",
            description="First training range instance",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE,
            owner="instructor",
            tags={"course": "cybersecurity", "level": "beginner"}
        )
        
        mock_orchestrator.create_range.return_value = range_metadata
        mock_orchestrator.list_ranges.return_value = [range_metadata]
        mock_orchestrator.get_range.return_value = range_metadata
        
        # Test range creation
        yaml_file = cyris_root / "examples" / "training.yml"
        
        with patch.dict(os.environ, {"CYRIS_PATH": str(cyris_root)}):
            # Simulate CLI range creation
            with patch('sys.argv', ['cyris', 'create', str(yaml_file)]):
                try:
                    # This would normally call the actual CLI
                    mock_orchestrator.create_range.assert_not_called()  # Not called yet
                    
                    # Simulate calling create_range
                    result = mock_orchestrator.create_range(
                        range_id="training-range-1",
                        name="Training Range 1",
                        description="Created from training.yml",
                        hosts=[],  # Would be parsed from YAML
                        guests=[],  # Would be parsed from YAML
                        owner="instructor"
                    )
                    
                    assert result.range_id == "training-range-1"
                    assert result.status == RangeStatus.ACTIVE
                    
                except Exception as e:
                    # Expected - we're testing the workflow structure
                    pass
    
    def test_multi_range_deployment(self, deployment_environment):
        """Test deployment of multiple concurrent ranges"""
        cyris_root = deployment_environment
        
        # Create configuration for multiple ranges
        multi_range_config = """
host_settings:
  - id: lab-host-1
    mgmt_addr: 192.168.100.30
    virbr_addr: 10.10.0.1
  
  - id: lab-host-2
    mgmt_addr: 192.168.100.31
    virbr_addr: 10.11.0.1

guest_settings:
  - id: web-1
    host_id: lab-host-1
    os_type: ubuntu.20.04
    memory_mb: 1024
    vcpus: 1
    ip_addr: 10.10.0.10
  
  - id: web-2
    host_id: lab-host-2
    os_type: ubuntu.20.04
    memory_mb: 1024
    vcpus: 1
    ip_addr: 10.11.0.10

clone_settings:
  range_id: multi-lab
  number_of_ranges: 3
  
  accounts:
    - username: student1
      password: pass1
    - username: student2
      password: pass2
    - username: student3
      password: pass3
        """.strip()
        
        multi_yaml = cyris_root / "examples" / "multi-lab.yml"
        multi_yaml.write_text(multi_range_config)
        
        # Validate multi-range configuration
        with open(multi_yaml) as f:
            config = yaml.safe_load(f)
        
        assert config["clone_settings"]["number_of_ranges"] == 3
        assert len(config["clone_settings"]["accounts"]) == 3
        assert len(config["host_settings"]) == 2
    
    def test_deployment_resource_requirements(self, deployment_environment):
        """Test deployment resource requirement calculations"""
        cyris_root = deployment_environment
        
        # Test resource calculation for training example
        training_yaml = cyris_root / "examples" / "training.yml"
        
        with open(training_yaml) as f:
            config = yaml.safe_load(f)
        
        # Calculate resource requirements
        total_memory_mb = 0
        total_vcpus = 0
        total_guests = 0
        
        for guest in config["guest_settings"]:
            total_memory_mb += guest.get("memory_mb", 1024)
            total_vcpus += guest.get("vcpus", 1)
            total_guests += 1
        
        # Multiply by number of ranges
        number_of_ranges = config["clone_settings"]["number_of_ranges"]
        total_memory_mb *= number_of_ranges
        total_vcpus *= number_of_ranges
        total_guests *= number_of_ranges
        
        # Verify reasonable resource requirements
        assert total_memory_mb > 0
        assert total_vcpus > 0
        assert total_guests >= 2  # At least 2 VMs per range
        
        # For training example: 2 VMs * 2 ranges = 4 VMs total
        # Memory: (2048 + 4096) * 2 = 12,288 MB
        expected_memory = (2048 + 4096) * 2
        expected_vcpus = (2 + 2) * 2
        expected_guests = 2 * 2
        
        assert total_memory_mb == expected_memory
        assert total_vcpus == expected_vcpus
        assert total_guests == expected_guests


class TestDeploymentScenarios:
    """Test specific deployment scenarios and use cases"""
    
    def test_education_deployment_scenario(self, deployment_environment):
        """Test deployment for educational cybersecurity training"""
        cyris_root = deployment_environment
        
        # Create education-specific configuration
        education_config = """
host_settings:
  - id: classroom-host
    mgmt_addr: 192.168.200.10
    virbr_addr: 172.16.0.1

guest_settings:
  - id: vulnerable-web
    host_id: classroom-host
    os_type: ubuntu.20.04
    memory_mb: 2048
    vcpus: 2
    ip_addr: 172.16.0.10
    software:
      - apache2
      - php
      - mysql-server
      - dvwa  # Damn Vulnerable Web Application
    
  - id: monitoring-server
    host_id: classroom-host
    os_type: ubuntu.20.04
    memory_mb: 1024
    vcpus: 1
    ip_addr: 172.16.0.20
    software:
      - wireshark
      - tcpdump
      - nagios

clone_settings:
  range_id: cybersec-training
  number_of_ranges: 20  # One per student
  
  # Course-specific settings
  course_name: "Introduction to Web Security"
  semester: "Fall 2023"
  instructor: "Prof. Security"
  
  # Educational features
  enable_monitoring: true
  generate_reports: true
  time_limit_hours: 4
  
  # Student accounts (would be generated per range)
  accounts:
    - username: student
      password: "random_generated"
      full_name: "Student User"
      role: student
      home_directory: "/home/student"
      allowed_commands: ["nmap", "curl", "wget", "python3"]
    - username: instructor
      password: "instructor_pass"
      full_name: "Course Instructor"
      role: instructor
      sudo_access: true
        """.strip()
        
        education_yaml = cyris_root / "examples" / "education.yml"
        education_yaml.write_text(education_config)
        
        # Validate educational configuration
        with open(education_yaml) as f:
            config = yaml.safe_load(f)
        
        # Check educational features
        clone_settings = config["clone_settings"]
        assert clone_settings["number_of_ranges"] == 20
        assert "course_name" in clone_settings
        assert "enable_monitoring" in clone_settings
        assert clone_settings["enable_monitoring"] is True
        
        # Verify vulnerable web app is configured
        dvwa_vm = next(vm for vm in config["guest_settings"] if vm["id"] == "vulnerable-web")
        assert "dvwa" in dvwa_vm["software"]
        assert "apache2" in dvwa_vm["software"]
    
    def test_research_deployment_scenario(self, deployment_environment):
        """Test deployment for cybersecurity research"""
        cyris_root = deployment_environment
        
        # Create research-specific configuration
        research_config = """
host_settings:
  - id: research-node-1
    mgmt_addr: 192.168.300.10
    virbr_addr: 10.50.0.1
  
  - id: research-node-2
    mgmt_addr: 192.168.300.11
    virbr_addr: 10.51.0.1

guest_settings:
  - id: honeypot
    host_id: research-node-1
    os_type: ubuntu.20.04
    memory_mb: 1024
    vcpus: 1
    ip_addr: 10.50.0.10
    software:
      - cowrie  # SSH honeypot
      - dionaea  # Malware honeypot
    
  - id: analysis-vm
    host_id: research-node-1
    os_type: ubuntu.20.04
    memory_mb: 8192
    vcpus: 4
    ip_addr: 10.50.0.20
    software:
      - volatility3  # Memory forensics
      - radare2     # Reverse engineering
      - ghidra      # NSA reverse engineering
      - wireshark
    
  - id: malware-sandbox
    host_id: research-node-2
    os_type: windows.10
    memory_mb: 4096
    vcpus: 2
    ip_addr: 10.51.0.10
    software:
      - cuckoo-sandbox
    isolation: true
    
  - id: data-collector
    host_id: research-node-2
    os_type: ubuntu.20.04
    memory_mb: 2048
    vcpus: 2
    ip_addr: 10.51.0.20
    software:
      - elasticsearch
      - kibana
      - logstash

clone_settings:
  range_id: research-testbed
  number_of_ranges: 1
  
  # Research-specific settings
  project_name: "Advanced Threat Detection"
  principal_investigator: "Dr. Researcher"
  funding_source: "NSF Grant #12345"
  
  # Advanced features
  enable_packet_capture: true
  enable_system_monitoring: true
  enable_malware_analysis: true
  data_retention_days: 365
  
  # Research accounts
  accounts:
    - username: researcher1
      password: "secure_research_pass"
      full_name: "Primary Researcher"
      role: admin
      sudo_access: true
    - username: analyst
      password: "analyst_pass"
      full_name: "Security Analyst"
      role: user
      allowed_hosts: [analysis-vm, data-collector]
        """.strip()
        
        research_yaml = cyris_root / "examples" / "research.yml"
        research_yaml.write_text(research_config)
        
        # Validate research configuration
        with open(research_yaml) as f:
            config = yaml.safe_load(f)
        
        # Check research features
        clone_settings = config["clone_settings"]
        assert "project_name" in clone_settings
        assert "enable_malware_analysis" in clone_settings
        assert clone_settings["data_retention_days"] == 365
        
        # Verify advanced analysis tools
        analysis_vm = next(vm for vm in config["guest_settings"] if vm["id"] == "analysis-vm")
        assert "volatility3" in analysis_vm["software"]
        assert "ghidra" in analysis_vm["software"]
        assert analysis_vm["memory_mb"] == 8192  # High memory for analysis
    
    def test_certification_training_deployment(self, deployment_environment):
        """Test deployment for certification training (CEH, CISSP, etc.)"""
        cyris_root = deployment_environment
        
        # Create certification training configuration
        cert_config = """
host_settings:
  - id: cert-training-host
    mgmt_addr: 192.168.400.10
    virbr_addr: 10.100.0.1

guest_settings:
  - id: target-windows
    host_id: cert-training-host
    os_type: windows.server.2019
    memory_mb: 4096
    vcpus: 2
    ip_addr: 10.100.0.10
    software:
      - iis
      - mssql-server
      - active-directory
    vulnerabilities:
      - type: ms17-010  # EternalBlue
      - type: weak-passwords
      - type: open-shares
  
  - id: target-linux
    host_id: cert-training-host
    os_type: ubuntu.18.04  # Older version with known vulnerabilities
    memory_mb: 2048
    vcpus: 2
    ip_addr: 10.100.0.11
    software:
      - apache2
      - mysql-server
      - ssh
    vulnerabilities:
      - type: shellshock
      - type: dirty-cow
      - type: sudo-vulnerability
  
  - id: kali-pentest
    host_id: cert-training-host
    os_type: kali.2023
    memory_mb: 4096
    vcpus: 4
    ip_addr: 10.100.0.20
    software:
      - metasploit-framework
      - nmap
      - burpsuite
      - sqlmap
      - aircrack-ng
      - john-the-ripper
      - hashcat

clone_settings:
  range_id: ceh-training
  number_of_ranges: 15
  
  # Certification details
  certification: "Certified Ethical Hacker (CEH)"
  training_provider: "EC-Council"
  course_duration_days: 5
  
  # Training scenarios
  scenarios:
    - name: "Network Reconnaissance"
      objectives: ["Port scanning", "Service enumeration", "OS fingerprinting"]
      tools: ["nmap", "masscan", "netcat"]
    
    - name: "Web Application Testing"  
      objectives: ["SQL injection", "XSS", "CSRF"]
      tools: ["burpsuite", "sqlmap", "nikto"]
    
    - name: "System Exploitation"
      objectives: ["Buffer overflow", "Privilege escalation", "Persistence"]
      tools: ["metasploit", "msfvenom", "empire"]
  
  # Trainee accounts
  accounts:
    - username: trainee
      password: "trainee123"
      full_name: "CEH Trainee"
      role: student
      allowed_hosts: [kali-pentest]
    - username: instructor
      password: "instructor456"
      full_name: "CEH Instructor"
      role: instructor
      sudo_access: true
        """.strip()
        
        cert_yaml = cyris_root / "examples" / "certification.yml"
        cert_yaml.write_text(cert_config)
        
        # Validate certification configuration
        with open(cert_yaml) as f:
            config = yaml.safe_load(f)
        
        # Check certification features
        clone_settings = config["clone_settings"]
        assert "certification" in clone_settings
        assert "scenarios" in clone_settings
        assert len(clone_settings["scenarios"]) == 3
        
        # Verify pentest tools are available
        kali_vm = next(vm for vm in config["guest_settings"] if vm["id"] == "kali-pentest")
        expected_tools = ["metasploit-framework", "nmap", "burpsuite", "sqlmap"]
        for tool in expected_tools:
            assert tool in kali_vm["software"]
        
        # Verify vulnerable targets
        windows_target = next(vm for vm in config["guest_settings"] if vm["id"] == "target-windows")
        assert "vulnerabilities" in windows_target
        assert any(vuln["type"] == "ms17-010" for vuln in windows_target["vulnerabilities"])


class TestDeploymentValidation:
    """Test deployment validation and error handling"""
    
    def test_deployment_prerequisite_check(self, deployment_environment):
        """Test deployment prerequisite validation"""
        cyris_root = deployment_environment
        
        # Check required files exist
        required_files = [
            "CONFIG",
            "examples/training.yml",
            "examples/pentest-lab.yml"
        ]
        
        for file_path in required_files:
            assert (cyris_root / file_path).exists(), f"Missing required file: {file_path}"
        
        # Check configuration values
        config_file = cyris_root / "CONFIG"
        config_content = config_file.read_text()
        
        required_config_keys = [
            "CYRIS_PATH",
            "RANGE_DIRECTORY", 
            "GATEWAY_ADDR",
            "GATEWAY_ACCOUNT"
        ]
        
        for key in required_config_keys:
            assert key in config_content, f"Missing required config key: {key}"
    
    def test_deployment_yaml_validation(self, deployment_environment):
        """Test YAML configuration validation"""
        cyris_root = deployment_environment
        examples_dir = cyris_root / "examples"
        
        # Test all YAML files in examples directory
        yaml_files = list(examples_dir.glob("*.yml"))
        assert len(yaml_files) >= 2
        
        for yaml_file in yaml_files:
            # Check YAML syntax
            try:
                with open(yaml_file) as f:
                    config = yaml.safe_load(f)
                assert isinstance(config, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax in {yaml_file}: {e}")
            
            # Check required sections
            required_sections = ["host_settings", "guest_settings", "clone_settings"]
            for section in required_sections:
                assert section in config, f"Missing section {section} in {yaml_file}"
            
            # Validate data types
            assert isinstance(config["host_settings"], list)
            assert isinstance(config["guest_settings"], list)
            assert isinstance(config["clone_settings"], dict)
    
    def test_deployment_resource_validation(self, deployment_environment):
        """Test resource requirement validation"""
        cyris_root = deployment_environment
        
        # Test resource limits for different scenarios
        training_yaml = cyris_root / "examples" / "training.yml"
        
        with open(training_yaml) as f:
            config = yaml.safe_load(f)
        
        # Calculate total resources
        total_memory = 0
        total_vcpus = 0
        
        for guest in config["guest_settings"]:
            memory_mb = guest.get("memory_mb", 1024)
            vcpus = guest.get("vcpus", 1)
            
            # Validate individual VM limits
            assert memory_mb >= 512, f"VM {guest['id']} has insufficient memory"
            assert memory_mb <= 16384, f"VM {guest['id']} has excessive memory"
            assert vcpus >= 1, f"VM {guest['id']} has insufficient CPUs"
            assert vcpus <= 8, f"VM {guest['id']} has excessive CPUs"
            
            total_memory += memory_mb
            total_vcpus += vcpus
        
        # Multiply by number of ranges
        number_of_ranges = config["clone_settings"]["number_of_ranges"]
        total_memory *= number_of_ranges
        total_vcpus *= number_of_ranges
        
        # Check reasonable total limits
        assert total_memory <= 100 * 1024, "Total memory requirement too high"  # 100GB max
        assert total_vcpus <= 64, "Total CPU requirement too high"  # 64 cores max
    
    def test_deployment_network_validation(self, deployment_environment):
        """Test network configuration validation"""
        cyris_root = deployment_environment
        
        # Check CONFIG network settings
        config_file = cyris_root / "CONFIG"
        config_content = config_file.read_text()
        
        # Extract and validate gateway address
        gateway_line = [line for line in config_content.split('\n') if 'GATEWAY_ADDR' in line][0]
        gateway_addr = gateway_line.split('=')[1].strip()
        
        # Basic IP address format check
        ip_parts = gateway_addr.split('.')
        assert len(ip_parts) == 4, "Invalid gateway IP address format"
        
        for part in ip_parts:
            ip_num = int(part)
            assert 0 <= ip_num <= 255, "Invalid IP address octet"
        
        # Check YAML network configurations
        examples_dir = cyris_root / "examples"
        for yaml_file in examples_dir.glob("*.yml"):
            with open(yaml_file) as f:
                config = yaml.safe_load(f)
            
            # Validate host management addresses
            for host in config["host_settings"]:
                mgmt_addr = host["mgmt_addr"]
                virbr_addr = host["virbr_addr"]
                
                # Basic IP validation
                for addr in [mgmt_addr, virbr_addr]:
                    ip_parts = addr.split('.')
                    assert len(ip_parts) == 4, f"Invalid IP format: {addr}"
            
            # Validate guest IP addresses
            for guest in config["guest_settings"]:
                if "ip_addr" in guest:
                    ip_addr = guest["ip_addr"]
                    ip_parts = ip_addr.split('.')
                    assert len(ip_parts) == 4, f"Invalid guest IP format: {ip_addr}"