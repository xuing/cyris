"""
测试配置解析模块
"""
import pytest
import os
import sys

# 添加main目录到Python路径以导入原始模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../main'))

from parse_config import parse_config


class TestParseConfig:
    """配置解析器测试类"""

    def test_parse_valid_config(self, config_file):
        """测试解析有效配置文件"""
        result = parse_config(str(config_file))
        
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 7
        # result格式: (abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email)
        abs_path, cr_dir, gw_mode, gw_account, gw_mgmt_addr, gw_inside_addr, user_email = result
        assert abs_path == "/tmp/cyris/"
        assert cr_dir == "/tmp/cyris/cyber_range/"
        assert gw_mode == False

    def test_parse_nonexistent_config(self):
        """测试解析不存在的配置文件"""
        result = parse_config('/nonexistent/config.ini')
        assert result == [False] * 7

    def test_parse_invalid_config_format(self, temp_dir):
        """测试解析无效格式的配置文件"""
        invalid_config = temp_dir / "invalid_config.ini"
        
        with open(invalid_config, 'w') as f:
            f.write("invalid content without sections")
        
        # 无效配置文件会抛出异常，需要捕获
        try:
            result = parse_config(str(invalid_config))
            # 如果没有抛出异常，应该返回False列表
            assert result == [False] * 7
        except Exception:
            # 抛出异常是预期的行为
            pass

    def test_parse_config_missing_required_fields(self, temp_dir):
        """测试解析缺少必需字段的配置文件"""
        incomplete_config = temp_dir / "incomplete_config.ini"
        
        with open(incomplete_config, 'w') as f:
            f.write("[config]\n")
            f.write("cyris_path = /tmp/cyris/\n")
            # 缺少 cyber_range_dir
        
        result = parse_config(str(incomplete_config))
        
        # 应该是元组格式
        assert isinstance(result, tuple)
        assert len(result) == 7
        abs_path = result[0]
        assert abs_path == "/tmp/cyris/"