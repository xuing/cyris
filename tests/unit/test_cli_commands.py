#!/usr/bin/env python3

"""
Unit tests for CLI commands (destroy --rm, rm command)
Following TDD principles: test CLI command behavior with mocked orchestrator
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.cli.main import cli, destroy, rm
from cyris.services.orchestrator import RangeStatus, RangeMetadata
from cyris.config.settings import CyRISSettings
from datetime import datetime


class TestCLIDestroyCommand:
    """Test destroy command with --rm option"""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator for CLI testing"""
        orchestrator = Mock()
        
        # Mock range metadata
        test_metadata = RangeMetadata(
            range_id="test_range",
            name="Test Range", 
            description="Test Description",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        
        orchestrator.get_range.return_value = test_metadata
        orchestrator.destroy_range.return_value = True
        orchestrator.remove_range.return_value = True
        
        return orchestrator
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_destroy_command_basic(self, runner, mock_orchestrator):
        """Test basic destroy command"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # Test with confirmation through main CLI group
            result = runner.invoke(cli, ['destroy', 'test_range'], input='y\n')
            assert result.exit_code == 0
            assert "destroyed successfully" in result.output
            
            # Verify orchestrator was called
            mock_orchestrator.destroy_range.assert_called_once_with('test_range')
            mock_orchestrator.remove_range.assert_not_called()
    
    def test_destroy_command_with_rm_flag(self, runner, mock_orchestrator):
        """Test destroy command with --rm flag"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # Test with --rm flag
            result = runner.invoke(cli, ['destroy', '--rm', 'test_range'], input='y\n')
            assert result.exit_code == 0
            # Check for both messages separately as they appear in different lines
            assert "destroyed successfully" in result.output
            assert "removed completely" in result.output
            
            # Verify both destroy and remove were called
            mock_orchestrator.destroy_range.assert_called_once_with('test_range')
            mock_orchestrator.remove_range.assert_called_once_with('test_range', force=False)
    
    def test_destroy_command_with_force_and_rm(self, runner, mock_orchestrator):
        """Test destroy command with --force and --rm flags"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # Test with both --force and --rm flags
            result = runner.invoke(cli, ['destroy', '--force', '--rm', 'test_range'])
            assert result.exit_code == 0
            # Check for both messages separately
            assert "destroyed successfully" in result.output
            assert "removed completely" in result.output
            
            # Verify both calls with force=True
            mock_orchestrator.destroy_range.assert_called_once_with('test_range')
            mock_orchestrator.remove_range.assert_called_once_with('test_range', force=True)
    
    def test_destroy_command_cancel(self, runner, mock_orchestrator):
        """Test destroy command cancellation"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # Test cancellation
            result = runner.invoke(cli, ['destroy', 'test_range'], input='n\n')
            assert result.exit_code == 0
            assert "Operation cancelled" in result.output
            
            # Verify orchestrator was not called
            mock_orchestrator.destroy_range.assert_not_called()
    
    def test_destroy_nonexistent_range(self, runner, mock_orchestrator):
        """Test destroy command with non-existent range"""
        mock_orchestrator.get_range.return_value = None
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            result = runner.invoke(cli, ['destroy', 'nonexistent'], input='y\n')
            assert result.exit_code == 1
            assert "not found" in result.output
    
    def test_destroy_failure(self, runner, mock_orchestrator):
        """Test destroy command failure handling"""
        mock_orchestrator.destroy_range.return_value = False
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            result = runner.invoke(cli, ['destroy', 'test_range'], input='y\n')
            assert result.exit_code == 1
            assert "Failed to destroy" in result.output


class TestCLIRmCommand:
    """Test rm command"""
    
    @pytest.fixture
    def mock_orchestrator_with_destroyed_range(self):
        """Mock orchestrator with a destroyed range"""
        orchestrator = Mock()
        
        # Mock destroyed range metadata
        destroyed_metadata = RangeMetadata(
            range_id="destroyed_range",
            name="Destroyed Range",
            description="Test Description", 
            created_at=datetime.now(),
            status=RangeStatus.DESTROYED
        )
        
        orchestrator.get_range.return_value = destroyed_metadata
        orchestrator.remove_range.return_value = True
        
        return orchestrator
    
    @pytest.fixture  
    def mock_orchestrator_with_active_range(self):
        """Mock orchestrator with an active range"""
        orchestrator = Mock()
        
        # Mock active range metadata
        active_metadata = RangeMetadata(
            range_id="active_range",
            name="Active Range",
            description="Test Description",
            created_at=datetime.now(), 
            status=RangeStatus.ACTIVE
        )
        
        orchestrator.get_range.return_value = active_metadata
        orchestrator.remove_range.return_value = True
        
        return orchestrator
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_rm_destroyed_range_success(self, runner, mock_orchestrator_with_destroyed_range):
        """Test removing a destroyed range successfully"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_destroyed_range):
            result = runner.invoke(cli, ['rm', 'destroyed_range'], input='y\n')
            assert result.exit_code == 0
            assert "removed completely" in result.output
            
            # Verify remove was called
            mock_orchestrator_with_destroyed_range.remove_range.assert_called_once_with('destroyed_range', force=False)
    
    def test_rm_active_range_without_force(self, runner, mock_orchestrator_with_active_range):
        """Test removing an active range without force fails"""
        mock_orchestrator_with_active_range.remove_range.return_value = False
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_active_range):
            result = runner.invoke(cli, ['rm', 'active_range'], input='y\n')
            assert result.exit_code == 1
            assert "Failed to remove" in result.output
    
    def test_rm_active_range_with_force(self, runner, mock_orchestrator_with_active_range):
        """Test removing an active range with force succeeds"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_active_range):
            result = runner.invoke(cli, ['rm', '--force', 'active_range'], input='y\n')
            assert result.exit_code == 0
            assert "removed completely" in result.output
            
            # Verify remove was called with force=True
            mock_orchestrator_with_active_range.remove_range.assert_called_once_with('active_range', force=True)
    
    def test_rm_nonexistent_range(self, runner):
        """Test removing a range that doesn't exist"""
        mock_orchestrator = Mock()
        mock_orchestrator.get_range.return_value = None
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            result = runner.invoke(cli, ['rm', 'nonexistent'], input='y\n')
            assert result.exit_code == 1
            assert "not found" in result.output
    
    def test_rm_cancel(self, runner, mock_orchestrator_with_destroyed_range):
        """Test rm command cancellation"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_destroyed_range):
            result = runner.invoke(cli, ['rm', 'destroyed_range'], input='n\n')
            assert result.exit_code == 0  # CLI returns 0 on cancel
            assert "Operation cancelled" in result.output
            
            # Verify remove was not called
            mock_orchestrator_with_destroyed_range.remove_range.assert_not_called()
    
    def test_rm_force_without_confirmation(self, runner, mock_orchestrator_with_destroyed_range):
        """Test rm with force flag still requires confirmation"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_destroyed_range):
            # Even with --force, user confirmation is still required for safety
            result = runner.invoke(cli, ['rm', '--force', 'destroyed_range'], input='y\n')
            assert result.exit_code == 0
            assert "removed completely" in result.output
            
            mock_orchestrator_with_destroyed_range.remove_range.assert_called_once_with('destroyed_range', force=True)
    
    def test_rm_shows_range_info(self, runner, mock_orchestrator_with_destroyed_range):
        """Test that rm command shows range information before removal"""
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_destroyed_range):
            result = runner.invoke(cli, ['rm', 'destroyed_range'], input='y\n')
            assert result.exit_code == 0
            
            # Check that range info is displayed
            assert "Range: Destroyed Range" in result.output
            assert "Status: destroyed" in result.output
            assert "Created:" in result.output
    
    def test_rm_failure_handling(self, runner, mock_orchestrator_with_destroyed_range):
        """Test rm command failure handling"""
        mock_orchestrator_with_destroyed_range.remove_range.return_value = False
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator_with_destroyed_range):
            result = runner.invoke(cli, ['rm', 'destroyed_range'], input='y\n')
            assert result.exit_code == 1
            assert "Failed to remove" in result.output


class TestCLIIntegrationDestroyRm:
    """Integration tests for destroy and rm commands workflow"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_destroy_then_rm_workflow(self, runner):
        """Test the complete destroy then rm workflow"""
        mock_orchestrator = Mock()
        
        # Initially active range
        active_metadata = RangeMetadata(
            range_id="workflow_test",
            name="Workflow Test",
            description="Test Description",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        
        # After destroy, range becomes destroyed
        destroyed_metadata = RangeMetadata(
            range_id="workflow_test", 
            name="Workflow Test",
            description="Test Description",
            created_at=datetime.now(),
            status=RangeStatus.DESTROYED
        )
        
        # Setup mock behavior
        mock_orchestrator.get_range.side_effect = [
            active_metadata,      # First call (destroy command)
            destroyed_metadata,   # Second call (rm command)
        ]
        mock_orchestrator.destroy_range.return_value = True
        mock_orchestrator.remove_range.return_value = True
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # Step 1: Destroy the range
            result = runner.invoke(cli, ['destroy','workflow_test'], input='y\n')
            assert result.exit_code == 0
            assert "destroyed successfully" in result.output
            
            # Step 2: Remove the range
            result = runner.invoke(cli, ['rm','workflow_test'], input='y\n')
            assert result.exit_code == 0
            assert "removed completely" in result.output
            
            # Verify the calls
            assert mock_orchestrator.destroy_range.call_count == 1
            assert mock_orchestrator.remove_range.call_count == 1
    
    def test_destroy_with_rm_one_step_workflow(self, runner):
        """Test the one-step destroy --rm workflow"""
        mock_orchestrator = Mock()
        
        active_metadata = RangeMetadata(
            range_id="one_step_test",
            name="One Step Test", 
            description="Test Description",
            created_at=datetime.now(),
            status=RangeStatus.ACTIVE
        )
        
        mock_orchestrator.get_range.return_value = active_metadata
        mock_orchestrator.destroy_range.return_value = True
        mock_orchestrator.remove_range.return_value = True
        
        with patch('cyris.services.orchestrator.RangeOrchestrator', return_value=mock_orchestrator):
            # One-step destroy and remove
            result = runner.invoke(cli, ['destroy','--rm', 'one_step_test'], input='y\n')
            assert result.exit_code == 0
            # Check for both messages separately as they appear in different lines
            assert "destroyed successfully" in result.output
            assert "removed completely" in result.output
            
            # Verify both operations were called
            mock_orchestrator.destroy_range.assert_called_once_with('one_step_test')
            mock_orchestrator.remove_range.assert_called_once_with('one_step_test', force=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])