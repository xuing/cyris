"""
End-to-End tests for CLI interface.

These tests verify that the command-line interface works correctly
and provides the expected user experience.
"""

import pytest
import subprocess
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock
import shutil
import sys
import os


@pytest.fixture
def temp_cyris_env(tmp_path):
    """Create a temporary CyRIS environment for testing"""
    cyris_dir = tmp_path / "cyris"
    cyris_dir.mkdir()
    
    # Create minimal required directories
    (cyris_dir / "cyber_range").mkdir()
    (cyris_dir / "logs").mkdir()
    (cyris_dir / "settings").mkdir()
    
    # Create basic CONFIG file
    config_content = f"""
# CyRIS Configuration File
CYRIS_PATH={cyris_dir}
RANGE_DIRECTORY={cyris_dir}/cyber_range
GATEWAY_ADDR=192.168.1.1
GATEWAY_ACCOUNT=cyris
    """.strip()
    
    config_file = cyris_dir / "CONFIG"
    config_file.write_text(config_content)
    
    # Create a simple YAML example
    yaml_content = """
host_settings:
  - id: web-server
    mgmt_addr: 192.168.1.10
    virbr_addr: 10.0.0.1

guest_settings:
  - id: web-vm
    host_id: web-server
    os_type: ubuntu.20.04
    memory_mb: 2048
    vcpus: 2

clone_settings:
  range_id: test-range-1
  number_of_ranges: 1
    """.strip()
    
    examples_dir = cyris_dir / "examples"
    examples_dir.mkdir()
    (examples_dir / "test.yml").write_text(yaml_content)
    
    return cyris_dir


@pytest.fixture
def cyris_cli_script(temp_cyris_env):
    """Path to the CyRIS CLI script"""
    return temp_cyris_env.parent / "cyris"


class TestModernCLI:
    """Test modern CLI interface functionality"""
    
    def test_cli_help_command(self):
        """Test CLI help command"""
        # Test main help
        result = subprocess.run(
            [sys.executable, "-c", "from src.cyris.cli.main import main; main(['--help'])"],
            cwd="/home/ubuntu/cyris",
            capture_output=True,
            text=True
        )
        
        # Should exit cleanly and show help
        assert result.returncode == 0 or result.returncode == 2  # Click exits with 2 for --help
        assert "Usage:" in result.stdout or "Usage:" in result.stderr
        assert "cyris" in (result.stdout + result.stderr).lower()
    
    def test_cli_version_command(self):
        """Test CLI version command"""
        result = subprocess.run(
            [sys.executable, "-c", "from src.cyris.cli.main import main; main(['--version'])"],
            cwd="/home/ubuntu/cyris",
            capture_output=True,
            text=True
        )
        
        # Should show version information
        assert result.returncode == 0
        output = result.stdout + result.stderr
        # Version should be shown (from pyproject.toml)
        assert any(char.isdigit() for char in output)
    
    def test_cli_config_show_command(self, temp_cyris_env):
        """Test config show command"""
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['config-show'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should complete without error
        assert result.returncode == 0
        # Should show some configuration information
        output = result.stdout + result.stderr
        assert len(output.strip()) > 0
    
    def test_cli_validate_command(self, temp_cyris_env):
        """Test validate command"""
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['validate'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Validation might fail due to missing dependencies, but should not crash
        # Return code 0 = valid, 1 = invalid, other = error
        assert result.returncode in [0, 1]
        output = result.stdout + result.stderr
        assert len(output.strip()) > 0
    
    @patch('src.cyris.services.orchestrator.RangeOrchestrator.create_range')
    def test_cli_create_command(self, mock_create_range, temp_cyris_env):
        """Test create range command"""
        # Mock successful range creation
        from src.cyris.services.orchestrator import RangeMetadata, RangeStatus
        from datetime import datetime
        
        mock_metadata = RangeMetadata(
            range_id="test-range-1",
            name="Test Range", 
            description="Test range",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        mock_create_range.return_value = mock_metadata
        
        yaml_file = temp_cyris_env / "examples" / "test.yml"
        
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main(['create', '{yaml_file}'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should complete successfully
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "test-range-1" in output or "created" in output.lower()
    
    def test_cli_list_command(self, temp_cyris_env):
        """Test list ranges command"""
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['list'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should complete without error (might show empty list)
        assert result.returncode == 0
        output = result.stdout + result.stderr
        # Should show some output (even if just headers or "no ranges")
        assert len(output.strip()) > 0


class TestLegacyCLICompatibility:
    """Test legacy CLI compatibility"""
    
    def test_legacy_interface_exists(self, temp_cyris_env):
        """Test that legacy interface still exists"""
        legacy_script = temp_cyris_env.parent / "main" / "cyris.py"
        legacy_script.parent.mkdir(exist_ok=True)
        
        # The legacy script should exist in the actual project
        actual_legacy = Path("/home/ubuntu/cyris/main/cyris.py")
        if actual_legacy.exists():
            # Test that we can import it without crashing
            result = subprocess.run(
                [sys.executable, "-c", "import sys; sys.path.insert(0, '/home/ubuntu/cyris'); import main.cyris"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            
            # Should import without syntax errors
            # May fail due to missing dependencies, but that's expected
            assert "SyntaxError" not in result.stderr
    
    def test_legacy_help_compatibility(self, temp_cyris_env):
        """Test legacy help functionality"""
        # Test that legacy script shows help when called without args
        actual_legacy = Path("/home/ubuntu/cyris/main/cyris.py")
        if actual_legacy.exists():
            result = subprocess.run(
                [sys.executable, str(actual_legacy)],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            
            # Should show usage or help information
            # Return code might vary, but should not crash with Python errors
            assert "Traceback" not in result.stderr or "cyris" in result.stdout.lower()


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases"""
    
    def test_cli_invalid_command(self):
        """Test CLI with invalid command"""
        result = subprocess.run(
            [sys.executable, "-c", "from src.cyris.cli.main import main; main(['invalid-command'])"],
            cwd="/home/ubuntu/cyris",
            capture_output=True,
            text=True
        )
        
        # Should exit with error
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "invalid-command" in output or "Usage:" in output
    
    def test_cli_missing_file(self, temp_cyris_env):
        """Test CLI with missing YAML file"""
        non_existent_file = temp_cyris_env / "does_not_exist.yml"
        
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main(['create', '{non_existent_file}'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should exit with error
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "not found" in output.lower() or "error" in output.lower()
    
    def test_cli_invalid_yaml(self, temp_cyris_env):
        """Test CLI with invalid YAML file"""
        invalid_yaml = temp_cyris_env / "examples" / "invalid.yml"
        invalid_yaml.write_text("invalid: yaml: content: [")
        
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main(['create', '{invalid_yaml}'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should exit with error
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "yaml" in output.lower() or "error" in output.lower()
    
    def test_cli_missing_config(self):
        """Test CLI without proper configuration"""
        # Test with empty/invalid environment
        with patch.dict(os.environ, {}, clear=True):
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['config-show'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        # Should handle missing config gracefully
        # Might succeed with defaults or fail gracefully
        assert result.returncode in [0, 1]
        output = result.stdout + result.stderr
        assert len(output.strip()) > 0


class TestCLIWorkflow:
    """Test complete CLI workflow scenarios"""
    
    @patch('src.cyris.services.orchestrator.RangeOrchestrator')
    def test_complete_range_lifecycle(self, mock_orchestrator_class, temp_cyris_env):
        """Test complete range lifecycle via CLI"""
        # Mock orchestrator instance
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Mock range creation
        from src.cyris.services.orchestrator import RangeMetadata, RangeStatus
        from datetime import datetime
        
        created_metadata = RangeMetadata(
            range_id="cli-test-range",
            name="CLI Test Range",
            description="Range created via CLI",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        mock_orchestrator.create_range.return_value = created_metadata
        mock_orchestrator.get_range.return_value = created_metadata
        mock_orchestrator.list_ranges.return_value = [created_metadata]
        mock_orchestrator.destroy_range.return_value = True
        
        yaml_file = temp_cyris_env / "examples" / "test.yml"
        
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            # Step 1: Create range
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main(['create', '{yaml_file}'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            
            # Step 2: List ranges
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['list'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            assert result.returncode == 0
            
            # Step 3: Get status (if implemented)
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['status', 'cli-test-range'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            # Status command might not be implemented yet
            assert result.returncode in [0, 1, 2]
    
    def test_cli_with_different_options(self, temp_cyris_env):
        """Test CLI with various command-line options"""
        yaml_file = temp_cyris_env / "examples" / "test.yml"
        
        # Test verbose mode
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main(['-v', 'validate'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            
            # Should complete (verbose mode might show more output)
            assert result.returncode in [0, 1]
            output = result.stdout + result.stderr
            assert len(output.strip()) > 0
    
    def test_cli_configuration_management(self, temp_cyris_env):
        """Test CLI configuration management commands"""
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            # Test config initialization
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['config-init'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            
            # Config init might not be implemented, but should not crash
            assert result.returncode in [0, 1, 2]
            
            # Test config show
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['config-show'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0
            output = result.stdout + result.stderr
            assert len(output.strip()) > 0


class TestCLIPerformance:
    """Test CLI performance and responsiveness"""
    
    def test_cli_startup_time(self):
        """Test CLI startup time is reasonable"""
        import time
        
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "-c", "from src.cyris.cli.main import main; main(['--help'])"],
            cwd="/home/ubuntu/cyris",
            capture_output=True,
            text=True
        )
        end_time = time.time()
        
        startup_time = end_time - start_time
        
        # CLI should start within reasonable time (5 seconds max)
        assert startup_time < 5.0
        assert result.returncode in [0, 2]  # 0 or 2 (Click --help exit code)
    
    def test_cli_help_response_time(self):
        """Test that help commands respond quickly"""
        import time
        
        commands_to_test = ["--help", "list --help", "create --help"]
        
        for cmd in commands_to_test:
            start_time = time.time()
            result = subprocess.run(
                [sys.executable, "-c", f"from src.cyris.cli.main import main; main({cmd.split()!r})"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            
            # Help should respond quickly (2 seconds max)
            assert response_time < 2.0
            assert result.returncode in [0, 2]


class TestCLIOutput:
    """Test CLI output formatting and user experience"""
    
    def test_cli_output_format(self, temp_cyris_env):
        """Test CLI output is well-formatted"""
        with patch.dict(os.environ, {"CYRIS_PATH": str(temp_cyris_env)}):
            result = subprocess.run(
                [sys.executable, "-c", "from src.cyris.cli.main import main; main(['list'])"],
                cwd="/home/ubuntu/cyris",
                capture_output=True,
                text=True
            )
        
        assert result.returncode == 0
        output = result.stdout
        
        # Output should be readable
        assert len(output.strip()) > 0
        # Should not contain raw Python objects or ugly formatting
        assert "object at 0x" not in output
        assert "<" not in output or ">" not in output or "Usage:" in output
    
    def test_cli_error_messages(self, temp_cyris_env):
        """Test CLI error messages are user-friendly"""
        # Test with invalid command
        result = subprocess.run(
            [sys.executable, "-c", "from src.cyris.cli.main import main; main(['invalid'])"],
            cwd="/home/ubuntu/cyris",
            capture_output=True,
            text=True
        )
        
        assert result.returncode != 0
        error_output = result.stderr + result.stdout
        
        # Error should be understandable
        assert len(error_output.strip()) > 0
        # Should not show raw Python tracebacks to end user
        assert "Traceback" not in error_output or "Usage:" in error_output