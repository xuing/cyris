#!/usr/bin/env python3
"""
Fix Import Paths Script

Fixes incorrect import paths in the refactored logging code.
Changes "from ..core.unified_logger" to "from ...core.unified_logger"
for files that are not in the core module.
"""

import os
import re
from pathlib import Path

def fix_import_path(file_path: Path) -> bool:
    """Fix import path in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix the specific import pattern
        content = re.sub(
            r'from \.\.core\.unified_logger import',
            'from ...core.unified_logger import',
            content
        )
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def main():
    """Fix import paths in all affected files"""
    files_to_fix = [
        "src/cyris/config/parser.py",
        "src/cyris/services/orchestrator.py", 
        "src/cyris/services/monitoring.py",
        "src/cyris/services/cleanup_service.py",
        "src/cyris/services/task_executor.py",
        "src/cyris/services/network_service.py",
        "src/cyris/services/gateway_service.py",
        "src/cyris/services/range_discovery.py",
        "src/cyris/services/layer3_network_service.py",
        "src/cyris/cli/main.py",
        "src/cyris/cli/commands/create_command.py",
        "src/cyris/cli/main_refactored.py",
        "src/cyris/cli/main_original_backup.py",
        "src/cyris/tools/ssh_manager.py",
        "src/cyris/tools/user_manager.py",
        "src/cyris/tools/ssh_reliability_integration.py",
        "src/cyris/tools/vm_ip_manager.py",
        "src/cyris/tools/vm_diagnostics.py"
    ]
    
    fixed_count = 0
    
    print("🔧 Fixing import paths...")
    print("=" * 50)
    
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            if fix_import_path(path):
                print(f"✅ Fixed: {file_path}")
                fixed_count += 1
            else:
                print(f"ℹ️  No change needed: {file_path}")
        else:
            print(f"❌ File not found: {file_path}")
    
    print("=" * 50)
    print(f"🎯 Summary: Fixed {fixed_count} files")
    
    if fixed_count > 0:
        print("✅ Import path fixes completed successfully!")
    else:
        print("ℹ️  No fixes were needed")

if __name__ == "__main__":
    main()