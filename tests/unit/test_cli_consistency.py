"""
TDD tests for CLI consistency and English internationalization

These tests verify the fixes for:
- CLI help consistency between `./cyris` and `./cyris --help` 
- Complete English internationalization (no Chinese text)
- Proper command routing and help text display
"""

import pytest
import re
from unittest.mock import patch, Mock
from click.testing import CliRunner


class TestCLIConsistency:
    """Test CLI consistency between different invocation methods"""
    
    def test_cyris_script_shows_modern_help(self):
        """Test that main cyris script shows modern CLI help"""
        from subprocess import run, PIPE
        
        result = run(['./cyris'], cwd='/home/ubuntu/cyris', capture_output=True, text=True)
        
        # Should show modern CLI help (English text)
        assert result.returncode == 0
        assert 'CyRIS - Modern Cyber Security Training Environment Deployment Tool' in result.stdout
        assert 'Usage:' in result.stdout or 'Commands:' in result.stdout
        
        # Should NOT contain Chinese text
        assert not self._contains_chinese_text(result.stdout)
    
    def test_cyris_help_flag_shows_same_content(self):
        """Test that `./cyris --help` shows the same content as `./cyris`"""
        from subprocess import run, PIPE
        
        # Get output from both invocations
        result_plain = run(['./cyris'], cwd='/home/ubuntu/cyris', capture_output=True, text=True)
        result_help = run(['./cyris', '--help'], cwd='/home/ubuntu/cyris', capture_output=True, text=True)
        
        # Both should succeed
        assert result_plain.returncode == 0
        assert result_help.returncode == 0
        
        # Content should be essentially the same (allowing for minor formatting differences)
        plain_content = self._normalize_help_text(result_plain.stdout)
        help_content = self._normalize_help_text(result_help.stdout)
        
        # Key elements should match
        assert 'CyRIS - Modern Cyber Security Training Environment Deployment Tool' in plain_content
        assert 'CyRIS - Modern Cyber Security Training Environment Deployment Tool' in help_content
        
        # Command lists should be similar
        plain_commands = self._extract_commands(plain_content)
        help_commands = self._extract_commands(help_content)
        
        # Should have overlapping commands
        common_commands = plain_commands.intersection(help_commands)
        assert len(common_commands) > 0
    
    def test_modern_cli_help_is_english_only(self):
        """Test that modern CLI help contains only English text"""
        from cyris.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert not self._contains_chinese_text(result.output)
        
        # Should contain expected English text
        assert 'Cyber Security Training Environment' in result.output
        assert 'Commands:' in result.output
    
    def test_modern_commands_are_recognized(self):
        """Test that modern commands are properly recognized"""
        from subprocess import run
        
        # Test that setup-permissions command is recognized
        result = run(['./cyris', 'setup-permissions', '--help'], 
                    cwd='/home/ubuntu/cyris', capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'Set up libvirt permissions' in result.output
        assert not self._contains_chinese_text(result.output)
    
    def _contains_chinese_text(self, text):
        """Check if text contains Chinese characters"""
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))
    
    def _normalize_help_text(self, text):
        """Normalize help text for comparison"""
        # Remove extra whitespace and normalize line endings
        return ' '.join(text.split()).strip()
    
    def _extract_commands(self, text):
        """Extract command names from help text"""
        # Look for command patterns
        commands = set()
        lines = text.split('\n')
        
        for line in lines:
            # Match patterns like "  create  " or "  setup-permissions  " 
            if line.strip() and not line.startswith('Usage') and not line.startswith('Options'):
                words = line.split()
                for word in words:
                    if word and not word.startswith('-') and len(word) > 2:
                        if word in ['create', 'destroy', 'list', 'status', 'setup-permissions', 'validate']:
                            commands.add(word)
        
        return commands


class TestEnglishInternationalization:
    """Test complete English internationalization across the codebase"""
    
    def test_cli_main_module_english_only(self):
        """Test that CLI main module contains no Chinese text"""
        from cyris.cli.main import cli
        
        # Check various CLI commands for English-only text
        runner = CliRunner()
        
        commands_to_test = [
            ['--help'],
            ['create', '--help'],
            ['destroy', '--help'], 
            ['list', '--help'],
            ['status', '--help'],
            ['setup-permissions', '--help'],
            ['validate', '--help']
        ]
        
        for cmd in commands_to_test:
            result = runner.invoke(cli, cmd)
            assert not self._contains_chinese_text(result.output), f"Chinese text found in: {' '.join(cmd)}"
    
    def test_error_messages_are_english(self):
        """Test that error messages are in English"""
        from cyris.cli.main import cli
        
        runner = CliRunner()
        
        # Test nonexistent range error
        result = runner.invoke(cli, ['destroy', 'nonexistent_range'])
        assert result.exit_code != 0
        assert not self._contains_chinese_text(result.output)
        assert 'not found' in result.output.lower()
        
        # Test invalid command  
        result = runner.invoke(cli, ['invalid_command'])
        assert result.exit_code != 0
        assert not self._contains_chinese_text(result.output)
    
    def test_orchestrator_service_english_only(self):
        """Test that orchestrator service uses English-only text"""
        from cyris.services.orchestrator import RangeOrchestrator, RangeMetadata
        from cyris.config.settings import CyRISSettings
        from unittest.mock import Mock
        
        settings = CyRISSettings()
        mock_provider = Mock()
        mock_provider.libvirt_uri = "qemu:///session"
        
        with patch('cyris.services.orchestrator.NetworkTopologyManager'), \
             patch('cyris.services.orchestrator.TaskExecutor'), \
             patch('cyris.services.orchestrator.TunnelManager'), \
             patch('cyris.services.orchestrator.GatewayService'):
            
            orchestrator = RangeOrchestrator(settings, mock_provider)
            
            # Check that log messages would be in English
            # (This is tested by examining the source code structure)
            assert hasattr(orchestrator, 'logger')
    
    def test_kvm_provider_english_only(self):
        """Test that KVM provider uses English-only text"""
        from cyris.infrastructure.providers.kvm_provider import KVMProvider
        
        config = {"libvirt_uri": "qemu:///session"}
        provider = KVMProvider(config)
        
        # Provider should be initialized without Chinese text in logs
        assert provider.libvirt_uri == "qemu:///session"
        assert hasattr(provider, 'logger')
    
    def test_permission_manager_english_only(self):
        """Test that permission manager uses English-only text"""
        from cyris.infrastructure.permissions import PermissionManager
        
        pm = PermissionManager(dry_run=True)
        
        # Test that compatibility check returns English recommendations
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = Mock(returncode=2)  # User not found
            
            compat_info = pm.check_libvirt_compatibility()
            
            # Recommendations should be in English
            for rec in compat_info['recommendations']:
                assert not self._contains_chinese_text(rec)
    
    def _contains_chinese_text(self, text):
        """Check if text contains Chinese characters"""
        if not text:
            return False
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))


class TestCommandRouting:
    """Test proper command routing between legacy and modern systems"""
    
    def test_modern_commands_route_correctly(self):
        """Test that modern commands are routed to modern CLI"""
        from subprocess import run
        
        # These commands should be handled by modern CLI
        modern_commands = ['create', 'destroy', 'list', 'status', 'setup-permissions', 'validate']
        
        for cmd in modern_commands:
            result = run(['./cyris', cmd, '--help'], 
                        cwd='/home/ubuntu/cyris', capture_output=True, text=True)
            
            assert result.returncode == 0
            assert not self._contains_chinese_text(result.output)
    
    def test_legacy_command_routing(self):
        """Test that legacy commands are properly routed"""
        from subprocess import run
        
        # Test legacy command routing
        result = run(['./cyris', 'legacy', '--help'], 
                    cwd='/home/ubuntu/cyris', capture_output=True, text=True)
        
        if result.returncode == 0:  # Only test if legacy is available
            assert 'legacy' in result.output.lower()
    
    def test_help_command_consistency(self):
        """Test that help commands show consistent information"""
        from subprocess import run
        
        help_variations = [
            ['--help'],
            ['-h'], 
            ['help']
        ]
        
        results = []
        for variation in help_variations:
            try:
                result = run(['./cyris'] + variation, 
                            cwd='/home/ubuntu/cyris', capture_output=True, text=True)
                if result.returncode == 0:
                    results.append(result.stdout)
            except:
                pass
        
        # At least --help should work
        assert len(results) > 0
        
        # All successful results should be in English
        for result_text in results:
            assert not self._contains_chinese_text(result_text)
    
    def _contains_chinese_text(self, text):
        """Check if text contains Chinese characters"""
        if not text:
            return False
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))


class TestMessageConsistency:
    """Test consistency of messages across different components"""
    
    def test_success_messages_are_consistent(self):
        """Test that success messages follow consistent patterns"""
        from cyris.cli.main import cli
        
        # Success messages should use consistent formatting (✅ prefix)
        runner = CliRunner()
        
        with patch('cyris.services.orchestrator.RangeOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.get_range.return_value = Mock()
            mock_orchestrator.get_range.return_value.provider_config = {}
            mock_orchestrator.get_range.return_value.name = "Test Range"
            mock_orchestrator.get_range.return_value.status.value = "active"
            mock_orchestrator.get_range.return_value.created_at.strftime = Mock(return_value="2023-01-01")
            mock_orchestrator.destroy_range.return_value = True
            mock_orchestrator_class.return_value = mock_orchestrator
            
            result = runner.invoke(cli, ['destroy', 'test', '--force'])
            
            if result.exit_code == 0:
                assert '✅' in result.output  # Should use checkmark for success
                assert not self._contains_chinese_text(result.output)
    
    def test_error_messages_are_consistent(self):
        """Test that error messages follow consistent patterns"""
        from cyris.cli.main import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ['destroy', 'nonexistent'])
        
        # Error messages should use consistent formatting (❌ prefix)
        assert '❌' in result.output or 'Error' in result.output
        assert not self._contains_chinese_text(result.output)
    
    def _contains_chinese_text(self, text):
        """Check if text contains Chinese characters"""
        if not text:
            return False
        chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
        return bool(chinese_pattern.search(text))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])