#!/usr/bin/env python3
"""
批量修复 logging 类型注解导入问题

找到所有使用 logging.Logger 类型注解但没有导入 logging 的文件，并自动修复。
"""

import os
import re
from pathlib import Path

def fix_logging_imports():
    """修复所有 logging 导入问题"""
    
    # 需要修复的文件列表
    files_to_fix = [
        "/home/ubuntu/cyris/src/cyris/infrastructure/providers/libvirt_provider.py",
        "/home/ubuntu/cyris/src/cyris/infrastructure/network/bridge_manager.py", 
        "/home/ubuntu/cyris/src/cyris/infrastructure/network/firewall_manager.py",
        "/home/ubuntu/cyris/src/cyris/services/orchestrator.py",
        "/home/ubuntu/cyris/src/cyris/services/monitoring.py",
        "/home/ubuntu/cyris/src/cyris/services/cleanup_service.py",
        "/home/ubuntu/cyris/src/cyris/services/layer3_network_service.py",
        "/home/ubuntu/cyris/src/cyris/core/exceptions.py"
    ]
    
    fixed_count = 0
    
    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"⚠️ 文件不存在: {file_path}")
            continue
            
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了 logging.Logger 但没有导入 logging
        if 'logging.Logger' in content and 'import logging' not in content:
            print(f"🔧 修复文件: {file_path}")
            
            # 查找 unified logger 导入行
            unified_logger_pattern = r'from cyris\.core\.unified_logger import get_logger'
            match = re.search(unified_logger_pattern, content)
            
            if match:
                # 在 unified logger 导入后添加 logging 导入
                new_import_line = match.group(0) + '\nimport logging  # Keep for type annotations'
                content = content.replace(match.group(0), new_import_line)
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✅ 已修复: {file_path}")
                fixed_count += 1
            else:
                print(f"⚠️ 未找到 unified logger 导入行: {file_path}")
        else:
            print(f"✅ 无需修复: {file_path}")
    
    print(f"\n🎉 修复完成！共修复了 {fixed_count} 个文件")

if __name__ == "__main__":
    fix_logging_imports()