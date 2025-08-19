"""
测试现代化配置解析器
"""
import pytest
import tempfile
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cyris.config.parser import (
    parse_legacy_config, parse_modern_config, 
    create_default_config, ConfigurationError
)
from cyris.config.settings import CyRISSettings


class TestLegacyConfigParser:
    """测试传统INI配置解析器"""

    def test_parse_valid_legacy_config(self, temp_dir):
        """测试解析有效的传统配置"""
        config_file = temp_dir / "test_config.ini"
        config_content = """[config]
cyris_path = /tmp/cyris/
cyber_range_dir = /tmp/cyris/cyber_range/
gw_mode = off
gw_account = testuser
user_email = test@example.com
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        result = parse_legacy_config(config_file)
        
        assert len(result) == 7
        abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email = result
        
        assert abs_path == "/tmp/cyris/"
        assert cr_dir == "/tmp/cyris/cyber_range/"
        assert gw_mode is False
        assert gw_account == "testuser"
        assert user_email == "test@example.com"

    def test_parse_nonexistent_legacy_config(self):
        """测试解析不存在的配置文件"""
        result = parse_legacy_config("/nonexistent/config.ini")
        
        # 应该返回7个False
        assert len(result) == 7
        assert all(r is False for r in result)

    def test_parse_legacy_config_gw_mode_variations(self, temp_dir):
        """测试网关模式的各种配置值"""
        test_cases = [
            ("on", True),
            ("true", True),
            ("1", True),
            ("yes", True),
            ("off", False),
            ("false", False),
            ("0", False),
            ("no", False),
        ]
        
        for gw_value, expected in test_cases:
            config_file = temp_dir / f"test_gw_{gw_value}.ini"
            config_content = f"""[config]
cyris_path = /tmp/cyris/
gw_mode = {gw_value}
"""
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            result = parse_legacy_config(config_file)
            _, _, gw_mode, _, _, _, _ = result
            
            assert gw_mode is expected, f"Expected {expected} for gw_mode={gw_value}"


class TestModernConfigParser:
    """测试现代化配置解析器"""

    def test_parse_yaml_config(self, temp_dir):
        """测试解析YAML配置"""
        config_file = temp_dir / "config.yml"
        config_content = """
cyris_path: /tmp/cyris/
cyber_range_dir: /tmp/cyris/cyber_range/
gw_mode: false
gw_account: testuser
user_email: test@example.com
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        settings = parse_modern_config(config_file)
        
        assert isinstance(settings, CyRISSettings)
        assert str(settings.cyris_path) == "/tmp/cyris"
        assert str(settings.cyber_range_dir) == "/tmp/cyris/cyber_range"
        assert settings.gw_mode is False
        assert settings.gw_account == "testuser"
        assert settings.user_email == "test@example.com"

    def test_parse_legacy_ini_with_modern_parser(self, temp_dir):
        """测试用现代解析器解析传统INI文件"""
        config_file = temp_dir / "config.ini"
        config_content = """[config]
cyris_path = /tmp/cyris/
cyber_range_dir = /tmp/cyris/cyber_range/
gw_mode = off
"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        settings = parse_modern_config(config_file)
        
        assert isinstance(settings, CyRISSettings)
        assert str(settings.cyris_path) == "/tmp/cyris"
        assert settings.gw_mode is False

    def test_parse_nonexistent_modern_config(self):
        """测试解析不存在的现代配置文件"""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            parse_modern_config("/nonexistent/config.yml")


class TestDefaultConfigCreation:
    """测试默认配置创建"""

    def test_create_default_yaml_config(self, temp_dir):
        """测试创建默认YAML配置"""
        config_file = temp_dir / "default_config.yml"
        
        settings = create_default_config(config_file)
        
        assert isinstance(settings, CyRISSettings)
        assert config_file.exists()
        
        # 验证可以重新解析
        reloaded_settings = parse_modern_config(config_file)
        assert reloaded_settings.cyris_path == settings.cyris_path
        assert reloaded_settings.gw_mode == settings.gw_mode


class TestConfigSettings:
    """测试配置设置模型"""

    def test_settings_validation(self):
        """测试配置验证"""
        settings = CyRISSettings(
            cyris_path="/tmp/cyris",
            cyber_range_dir="/tmp/cyris/cyber_range",
            gw_mode=True,
            gw_account="testuser"
        )
        
        assert settings.cyris_path.is_absolute()
        assert settings.cyber_range_dir.is_absolute()
        assert settings.gw_mode is True
        assert settings.gw_account == "testuser"

    def test_relative_path_conversion(self):
        """测试相对路径转换为绝对路径"""
        settings = CyRISSettings(
            cyris_path="./relative/path",
            cyber_range_dir="./cyber_range"
        )
        
        assert settings.cyris_path.is_absolute()
        assert settings.cyber_range_dir.is_absolute()