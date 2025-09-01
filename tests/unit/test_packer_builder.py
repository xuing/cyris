"""
Unit Tests for Packer Image Builder

Tests the Packer automation provider functionality including template generation,
build execution, and image caching without requiring actual Packer installation.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from cyris.infrastructure.automation.packer_builder import (
    PackerBuilder,
    PackerError,
    ImageCache
)
from cyris.infrastructure.automation import (
    AutomationStatus,
    AutomationResult
)
from cyris.config.automation_settings import PackerSettings


class TestPackerBuilder:
    """Test Packer builder functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def packer_settings(self, temp_dir):
        """Create test Packer settings"""
        return PackerSettings(
            enabled=True,
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates", 
            output_dir=temp_dir / "output",
            timeout=300,
            retry_count=2,
            parallel_builds=1,
            memory_size=1024,
            disk_size="10G"
        )
    
    @pytest.fixture
    def mock_packer_binary(self, temp_dir):
        """Create mock packer binary"""
        packer_binary = temp_dir / "packer"
        packer_binary.touch()
        packer_binary.chmod(0o755)
        return packer_binary
    
    @pytest.fixture
    def packer_builder(self, packer_settings, mock_packer_binary):
        """Create Packer builder with mocked binary"""
        with patch.object(PackerBuilder, '_find_packer_binary', return_value=mock_packer_binary):
            builder = PackerBuilder(packer_settings)
            return builder
    
    def test_packer_builder_initialization(self, packer_builder, packer_settings):
        """Test Packer builder initialization"""
        assert packer_builder.provider_type == "packer"
        assert packer_builder.is_enabled is True
        assert packer_builder.settings == packer_settings
        assert packer_builder.packer_binary is not None
        assert isinstance(packer_builder.image_cache, ImageCache)
    
    def test_find_packer_binary_success(self, temp_dir):
        """Test finding Packer binary in system"""
        # Create mock binary in temp location
        mock_binary = temp_dir / "packer"
        mock_binary.touch()
        mock_binary.chmod(0o755)
        
        settings = PackerSettings(binary_path=mock_binary)
        builder = PackerBuilder(settings)
        
        assert builder.packer_binary == mock_binary
    
    def test_find_packer_binary_not_found(self, packer_settings):
        """Test handling when Packer binary not found"""
        with patch.object(PackerBuilder, '_find_packer_binary', return_value=None):
            builder = PackerBuilder(packer_settings)
            assert builder.packer_binary is None
    
    @pytest.mark.asyncio
    async def test_connect_success(self, packer_builder):
        """Test successful connection to Packer"""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Packer v1.9.0", b""))
        
        mock_process.communicate = AsyncMock(return_value=(b"Packer v1.9.0", b""))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            # Don't patch asyncio.wait_for, let it work naturally with the AsyncMock
            await packer_builder.connect()
            
            assert packer_builder.is_connected is True
    
    @pytest.mark.asyncio
    async def test_connect_binary_not_found(self, packer_settings):
        """Test connection failure when binary not found"""
        with patch.object(PackerBuilder, '_find_packer_binary', return_value=None):
            builder = PackerBuilder(packer_settings)
            
            with pytest.raises(PackerError, match="Packer binary not found"):
                await builder.connect()
    
    @pytest.mark.asyncio
    async def test_connect_version_check_failed(self, packer_builder):
        """Test connection failure when version check fails"""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Command not found"))
        
        mock_process.communicate = AsyncMock(return_value=(b"", b"Command not found"))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            with pytest.raises(PackerError, match="version check failed"):
                await packer_builder.connect()
    
    @pytest.mark.asyncio
    async def test_validate_configuration_success(self, packer_builder):
        """Test successful configuration validation"""
        with patch('shutil.disk_usage', return_value=Mock(free=10*1024**3)):  # 10GB free
            with patch('shutil.which', return_value="/usr/bin/tool"):
                issues = await packer_builder.validate_configuration()
                assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_validate_configuration_issues(self, packer_builder):
        """Test configuration validation with issues"""
        with patch('shutil.disk_usage', return_value=Mock(free=1*1024**3)):  # 1GB free (insufficient)
            with patch('shutil.which', return_value=None):  # Missing tools
                issues = await packer_builder.validate_configuration()
                
                assert len(issues) > 0
                assert any("disk space" in issue.lower() for issue in issues)
                assert any("missing" in issue.lower() for issue in issues)
    
    @pytest.mark.asyncio
    async def test_execute_build_operation_cached(self, packer_builder):
        """Test build operation using cached images"""
        # Mock cached images
        mock_cache = Mock()
        mock_cache.get_cached_images = AsyncMock(return_value={
            "qcow2": Path("/cache/image.qcow2")
        })
        packer_builder.image_cache = mock_cache
        
        parameters = {
            "template_name": "ubuntu-22.04",
            "output_formats": ["qcow2"],
            "ssh_keys": [],
            "custom_config": {}
        }
        
        result = await packer_builder.execute_operation("build", parameters)
        
        assert result.status == AutomationStatus.COMPLETED
        assert "cached" in result.output.lower()
        assert "cached_images" in result.artifacts
    
    @pytest.mark.asyncio  
    async def test_execute_build_operation_success(self, packer_builder):
        """Test successful build operation"""
        # Mock empty cache (force build)
        mock_cache = Mock()
        mock_cache.get_cached_images = AsyncMock(return_value=None)
        mock_cache.cache_images = AsyncMock()
        packer_builder.image_cache = mock_cache
        
        # Mock successful build
        with patch.object(packer_builder, '_generate_packer_template', AsyncMock(return_value="mock template")):
            with patch.object(packer_builder, '_run_packer_build', AsyncMock(return_value="Build completed")):
                with patch.object(packer_builder, '_process_build_results', AsyncMock(return_value={
                    "qcow2": Path("/output/ubuntu.qcow2")
                })):
                    
                    parameters = {
                        "template_name": "ubuntu-22.04",
                        "output_formats": ["qcow2"],
                        "ssh_keys": ["ssh-rsa AAAAB3..."],
                        "custom_config": {},
                        "force_rebuild": True
                    }
                    
                    result = await packer_builder.execute_operation("build", parameters)
                    
                    assert result.status == AutomationStatus.COMPLETED
                    assert result.output == "Build completed"
                    assert "built_images" in result.artifacts
    
    @pytest.mark.asyncio
    async def test_execute_build_operation_failure(self, packer_builder):
        """Test build operation failure"""
        # Mock cache to force build
        mock_cache = Mock()
        mock_cache.get_cached_images = AsyncMock(return_value=None)
        packer_builder.image_cache = mock_cache
        
        # Mock build failure
        with patch.object(packer_builder, '_generate_packer_template', AsyncMock(side_effect=PackerError("Template generation failed"))):
            
            parameters = {
                "template_name": "ubuntu-22.04",
                "output_formats": ["qcow2"]
            }
            
            result = await packer_builder.execute_operation("build", parameters)
            
            assert result.status == AutomationStatus.FAILED
            assert "Template generation failed" in result.error_message
    
    @pytest.mark.asyncio
    async def test_execute_validate_operation(self, packer_builder):
        """Test template validation operation"""
        template_path = packer_builder.settings.working_dir / "test.pkr.hcl"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text("# Test template")
        
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Template validated successfully", b""))
        
        mock_process.communicate = AsyncMock(return_value=(b"Template validated successfully", b""))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            parameters = {"template_path": str(template_path)}
            result = await packer_builder.execute_operation("validate", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "validated successfully" in result.output.lower()
    
    @pytest.mark.asyncio
    async def test_execute_inspect_operation(self, packer_builder):
        """Test template inspection operation"""  
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Template inspection results", b""))
        
        mock_process.communicate = AsyncMock(return_value=(b"Template inspection results", b""))
        
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
            parameters = {"template_path": "/mock/template.pkr.hcl"}
            result = await packer_builder.execute_operation("inspect", parameters)
            
            assert result.status == AutomationStatus.COMPLETED
            assert "inspection results" in result.output.lower()
    
    def test_generate_cache_key(self, packer_builder):
        """Test cache key generation"""
        key1 = packer_builder._generate_cache_key(
            "ubuntu-22.04", 
            ["key1", "key2"], 
            {"memory": 2048}
        )
        
        key2 = packer_builder._generate_cache_key(
            "ubuntu-22.04",
            ["key2", "key1"],  # Different order
            {"memory": 2048}
        )
        
        key3 = packer_builder._generate_cache_key(
            "ubuntu-22.04",
            ["key1", "key2"],
            {"memory": 4096}  # Different config
        )
        
        # Same content should produce same key (order-independent)
        assert key1 == key2
        
        # Different content should produce different key  
        assert key1 != key3
        
        # Keys should be reasonable length
        assert len(key1) == 16
    
    @pytest.mark.asyncio
    async def test_generate_default_ubuntu_template(self, packer_builder):
        """Test generation of default Ubuntu template"""
        template = await packer_builder._generate_default_template(
            "ubuntu-22.04",
            ["qcow2", "vmdk"],
            ["ssh-rsa AAAAB3..."],
            {}
        )
        
        assert "ubuntu" in template.lower()
        assert "qcow2" in template
        assert "vmdk" in template
        assert "ssh-rsa AAAAB3..." in template
        assert "cloud-init" in template
    
    def test_generate_ssh_key_provisioner(self, packer_builder):
        """Test SSH key provisioner generation"""
        ssh_keys = ["ssh-rsa AAAAB3NzaC1yc2E...", "ssh-ed25519 AAAAC3NzaC1lZDI1..."]
        
        provisioner = packer_builder._generate_ssh_key_provisioner(ssh_keys)
        
        assert 'provisioner "shell"' in provisioner
        assert "authorized_keys" in provisioner
        assert all(key in provisioner for key in ssh_keys)
    
    def test_generate_format_conversions(self, packer_builder):
        """Test format conversion commands generation"""
        conversions = packer_builder._generate_format_conversions(["qcow2", "vmdk", "vhd"])
        
        assert "qemu-img convert" in conversions
        assert "vmdk" in conversions
        assert "vhd" in conversions
        # qcow2 should not be converted (it's the default)
        assert conversions.count("qemu-img") == 2
    
    @pytest.mark.asyncio
    async def test_operation_tracking(self, packer_builder):
        """Test operation tracking functionality"""
        # Start operation
        parameters = {"template_name": "test"}
        
        # Mock to avoid actual execution
        with patch.object(packer_builder, '_execute_build', AsyncMock()):
            result = await packer_builder.execute_operation("build", parameters)
            
            # Should be tracked during execution
            assert result.operation_id in packer_builder._active_operations
            
            # Clean up
            await packer_builder.cleanup_artifacts(result.operation_id)
            assert result.operation_id not in packer_builder._active_operations


class TestImageCache:
    """Test image caching functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def cache_settings(self, temp_dir):
        """Create cache settings"""
        return PackerSettings(
            output_dir=temp_dir,
            cache_retention_days=30
        )
    
    @pytest.fixture
    def image_cache(self, cache_settings):
        """Create image cache instance"""
        return ImageCache(cache_settings)
    
    @pytest.mark.asyncio
    async def test_cache_and_retrieve_images(self, image_cache, temp_dir):
        """Test caching and retrieving images"""
        cache_key = "test-cache-key"
        
        # Create test images
        test_images = {
            "qcow2": temp_dir / "test.qcow2",
            "vmdk": temp_dir / "test.vmdk"
        }
        
        for image_path in test_images.values():
            image_path.write_text("mock image content")
        
        # Cache images
        await image_cache.cache_images(cache_key, test_images)
        
        # Retrieve cached images
        cached_images = await image_cache.get_cached_images(cache_key)
        
        assert cached_images is not None
        assert len(cached_images) == 2
        assert "qcow2" in cached_images
        assert "vmdk" in cached_images
        assert all(path.exists() for path in cached_images.values())
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, image_cache, temp_dir):
        """Test cache expiration handling"""
        cache_key = "expired-cache-key"
        
        # Create expired cache directory
        cache_path = image_cache.cache_dir / cache_key
        cache_path.mkdir(parents=True)
        
        # Create mock cached image
        cached_image = cache_path / "image.qcow2"
        cached_image.write_text("expired image")
        
        # Set modification time to past (simulate expiration)
        import os
        past_time = datetime.now() - timedelta(days=35)  # Older than retention period
        past_timestamp = past_time.timestamp()
        os.utime(cached_image, (past_timestamp, past_timestamp))
        os.utime(cache_path, (past_timestamp, past_timestamp))
        
        # Try to retrieve expired cache
        cached_images = await image_cache.get_cached_images(cache_key)
        
        assert cached_images is None  # Should return None for expired cache
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, image_cache, temp_dir):
        """Test cleanup of expired cache entries"""
        # Create multiple cache entries
        cache_keys = ["cache1", "cache2", "cache3"]
        
        for i, cache_key in enumerate(cache_keys):
            cache_path = image_cache.cache_dir / cache_key
            cache_path.mkdir(parents=True)
            
            cached_image = cache_path / "image.qcow2"
            cached_image.write_text(f"cached image {i}")
            
            # Make first two expired, last one fresh
            if i < 2:
                past_time = datetime.now() - timedelta(days=35)  # Expired
            else:
                past_time = datetime.now() - timedelta(days=5)   # Fresh
            
            import os
            past_timestamp = past_time.timestamp()
            os.utime(cached_image, (past_timestamp, past_timestamp))
            os.utime(cache_path, (past_timestamp, past_timestamp))
        
        # Run cleanup
        cleaned_count = await image_cache.cleanup_expired_cache()
        
        assert cleaned_count == 2  # Should clean up 2 expired entries
        
        # Verify fresh cache still exists
        fresh_cache_path = image_cache.cache_dir / cache_keys[2]
        assert fresh_cache_path.exists()
        
        # Verify expired caches are gone
        for expired_key in cache_keys[:2]:
            expired_cache_path = image_cache.cache_dir / expired_key
            assert not expired_cache_path.exists()


class TestPackerIntegration:
    """Integration tests for Packer builder (mocked)"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.mark.asyncio
    async def test_end_to_end_build_workflow(self, temp_dir):
        """Test complete build workflow from start to finish"""
        # Setup
        settings = PackerSettings(
            working_dir=temp_dir / "working",
            templates_dir=temp_dir / "templates",
            output_dir=temp_dir / "output",
            timeout=60
        )
        
        # Create mock Packer binary
        mock_binary = temp_dir / "packer"
        mock_binary.touch()
        mock_binary.chmod(0o755)
        
        with patch.object(PackerBuilder, '_find_packer_binary', return_value=mock_binary):
            builder = PackerBuilder(settings)
            
            # Mock all external dependencies
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Packer v1.9.0", b""))
            
            mock_process.communicate = AsyncMock(return_value=(b"Packer v1.9.0", b""))
            
            with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=mock_process)):
                    with patch.object(builder, '_run_packer_build', AsyncMock(return_value="Build completed")):
                        # Create mock output file for the test
                        mock_output_file = temp_dir / "ubuntu.qcow2"
                        mock_output_file.write_text("mock qcow2 image content")
                        
                        with patch.object(builder, '_process_build_results', AsyncMock(return_value={
                            "qcow2": mock_output_file
                        })):
                            
                            # Connect
                            await builder.connect()
                            assert builder.is_connected
                            
                            # Validate configuration
                            with patch('shutil.disk_usage', return_value=Mock(free=10*1024**3)):
                                with patch('shutil.which', return_value="/usr/bin/tool"):
                                    issues = await builder.validate_configuration()
                                    assert len(issues) == 0
                            
                            # Execute build
                            parameters = {
                                "template_name": "ubuntu-22.04",
                                "output_formats": ["qcow2"],
                                "ssh_keys": ["ssh-rsa AAAAB3..."],
                                "force_rebuild": True
                            }
                            
                            result = await builder.execute_operation("build", parameters)
                            
                            assert result.status == AutomationStatus.COMPLETED
                            assert result.output == "Build completed"
                            assert "built_images" in result.artifacts
                            
                            # Cleanup
                            await builder.cleanup_artifacts(result.operation_id)
                            await builder.disconnect()