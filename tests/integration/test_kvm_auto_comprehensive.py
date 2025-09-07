#!/usr/bin/env python3
"""
Comprehensive integration test suite for KVM-auto functionality.
Converted from root directory script to standard pytest format.

Tests:
- YAML configuration parsing for KVM-auto scenarios
- CyRIS configuration integration
- Virtualization tools availability
- VM creation workflow validation
"""

import pytest
import subprocess
import yaml
import sys
import os
from pathlib import Path
from typing import Dict, Any, List
import json

# Import CyRIS modules
from cyris.config.parser import CyRISConfigParser
from cyris.domain.entities.guest import BaseVMType
from cyris.core.exceptions import CyRISException


class TestKVMAutoComprehensive:
    """Comprehensive KVM-auto integration tests"""
    
    @pytest.fixture(scope="class")
    def test_yaml_files(self):
        """Provide test YAML files"""
        return [
            'test-kvm-auto.yml',
            'test-kvm-auto-debian.yml', 
            'test-kvm-auto-multi.yml',
            'test-kvm-auto-advanced.yml',
            'test-kvm-auto-enhanced.yml'
        ]
    
    @pytest.fixture(scope="class") 
    def required_virt_tools(self):
        """List of required virtualization tools"""
        return ['virt-builder', 'virt-install', 'virt-customize', 'virsh', 'qemu-img']
    
    def test_virtualization_tools_availability(self, required_virt_tools):
        """Test availability of required virtualization tools"""
        missing_tools = []
        
        for tool in required_virt_tools:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, timeout=10)
                if result.returncode != 0:
                    missing_tools.append(tool)
            except (subprocess.SubprocessError, FileNotFoundError):
                missing_tools.append(tool)
        
        if missing_tools:
            pytest.skip(f"Missing required tools: {', '.join(missing_tools)}")
    
    def test_yaml_configuration_parsing(self, test_yaml_files):
        """Test YAML configuration parsing for all test files"""
        for test_file in test_yaml_files:
            if not Path(test_file).exists():
                pytest.skip(f"Test file {test_file} not found")
            
            with open(test_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Basic structure validation
            has_guests = False
            kvm_auto_count = 0
            
            if isinstance(data, list):
                for section in data:
                    if 'guest_settings' in section:
                        has_guests = True
                        for guest in section['guest_settings']:
                            if guest.get('basevm_type') == 'kvm-auto':
                                kvm_auto_count += 1
            
            assert has_guests, f"No guest_settings found in {test_file}"
            assert kvm_auto_count > 0, f"No kvm-auto guests found in {test_file}"
    
    def test_cyris_config_integration(self):
        """Test CyRIS configuration parsing with kvm-auto support"""
        parser = CyRISConfigParser()
        
        test_cases = [
            ('test-kvm-auto-enhanced.yml', 'Enhanced configuration'),
            ('test-kvm-auto-multi.yml', 'Multi-VM configuration'),
        ]
        
        for test_file, description in test_cases:
            if not Path(test_file).exists():
                pytest.skip(f"Test file {test_file} not found")
            
            config = parser.parse_file(test_file)
            
            # Validate parsing results
            kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
            assert len(kvm_auto_guests) > 0, f"No kvm-auto guests found in {description}"
            
            # Validate kvm-auto specific fields
            for guest in kvm_auto_guests:
                assert hasattr(guest, 'vm_image_name'), "Missing vm_image_name field"
                assert hasattr(guest, 'vm_size'), "Missing vm_size field"
                assert hasattr(guest, 'disk_size'), "Missing disk_size field"
    
    def test_vm_image_specification_validation(self):
        """Test VM image specification validation for kvm-auto"""
        parser = CyRISConfigParser()
        
        # Test with valid configuration
        valid_config_data = {
            'guest_settings': [{
                'id': 'test-vm',
                'basevm_type': 'kvm-auto',
                'vm_image_name': 'ubuntu-20.04',
                'vm_size': '2G',
                'disk_size': '10G',
                'basevm_host': 'host1'
            }]
        }
        
        # This should not raise an exception
        config = parser.parse_dict(valid_config_data)
        kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
        assert len(kvm_auto_guests) == 1
        
        guest = kvm_auto_guests[0]
        assert guest.vm_image_name == 'ubuntu-20.04'
        assert guest.vm_size == '2G'
        assert guest.disk_size == '10G'
    
    def test_kvm_auto_guest_creation_workflow(self):
        """Test the complete kvm-auto guest creation workflow"""
        # This is a placeholder for the actual VM creation test
        # In a real scenario, this would test the full workflow
        pytest.skip("Requires actual VM infrastructure - placeholder test")
    
    def test_kvm_auto_error_handling(self):
        """Test error handling for kvm-auto configuration"""
        parser = CyRISConfigParser()
        
        # Test with missing required fields
        invalid_config_data = {
            'guest_settings': [{
                'id': 'test-vm',
                'basevm_type': 'kvm-auto',
                # Missing required fields: vm_image_name, vm_size, etc.
                'basevm_host': 'host1'
            }]
        }
        
        with pytest.raises(CyRISException):
            parser.parse_dict(invalid_config_data)


class TestKVMAutoAdvancedScenarios:
    """Advanced KVM-auto scenario tests"""
    
    def test_multi_vm_kvm_auto_configuration(self):
        """Test configuration with multiple kvm-auto VMs"""
        if not Path('test-kvm-auto-multi.yml').exists():
            pytest.skip("Multi-VM test file not found")
        
        parser = CyRISConfigParser()
        config = parser.parse_file('test-kvm-auto-multi.yml')
        
        kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
        assert len(kvm_auto_guests) >= 2, "Multi-VM test should have at least 2 kvm-auto VMs"
        
        # Ensure each VM has unique identifiers
        guest_ids = [g.guest_id for g in kvm_auto_guests]
        assert len(guest_ids) == len(set(guest_ids)), "Guest IDs should be unique"
    
    def test_kvm_auto_network_configuration(self):
        """Test network configuration for kvm-auto VMs"""
        pytest.skip("Network configuration test - requires infrastructure")
    
    def test_kvm_auto_performance_parameters(self):
        """Test performance parameter validation for kvm-auto VMs"""
        parser = CyRISConfigParser()
        
        # Test various VM sizes
        valid_sizes = ['1G', '2G', '4G', '8G']
        
        for size in valid_sizes:
            config_data = {
                'guest_settings': [{
                    'id': f'test-vm-{size}',
                    'basevm_type': 'kvm-auto',
                    'vm_image_name': 'ubuntu-20.04',
                    'vm_size': size,
                    'disk_size': '10G',
                    'basevm_host': 'host1'
                }]
            }
            
            config = parser.parse_dict(config_data)
            kvm_auto_guests = [g for g in config.guests if g.basevm_type == BaseVMType.KVM_AUTO]
            assert len(kvm_auto_guests) == 1
            assert kvm_auto_guests[0].vm_size == size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])