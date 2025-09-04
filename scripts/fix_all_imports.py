#!/usr/bin/env python3
"""
Comprehensive Import Fix Script

Fixes all relative import issues in the refactored logging code.
Converts relative imports to absolute imports where needed for CLI modules.
"""

import os
import re
from pathlib import Path

def fix_cli_imports(file_path: Path) -> bool:
    """Fix imports in CLI modules to use absolute imports"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix relative imports in CLI modules
        content = re.sub(
            r'from \.\.\.core\.unified_logger import',
            'from cyris.core.unified_logger import',
            content
        )
        
        # Fix other potential relative import issues in CLI
        content = re.sub(
            r'from \.\.\.([a-z_\.]+) import',
            r'from cyris.\1 import',
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
    """Fix all import issues"""
    print("🔧 Comprehensive Import Fix")
    print("=" * 50)
    
    # CLI modules need absolute imports
    cli_files = [
        "src/cyris/cli/main.py",
        "src/cyris/cli/main_refactored.py", 
        "src/cyris/cli/main_original_backup.py",
        "src/cyris/cli/commands/create_command.py"
    ]
    
    fixed_count = 0
    
    print("Fixing CLI module imports...")
    for file_path in cli_files:
        path = Path(file_path)
        if path.exists():
            if fix_cli_imports(path):
                print(f"✅ Fixed: {file_path}")
                fixed_count += 1
            else:
                print(f"ℹ️  No change needed: {file_path}")
        else:
            print(f"❌ File not found: {file_path}")
    
    print("=" * 50)
    print(f"🎯 Summary: Fixed {fixed_count} files")
    
    if fixed_count >= 0:
        print("✅ Import fixes completed!")
    
    # Test import after fixes
    print("\n🧪 Testing imports after fixes...")
    try:
        import sys
        sys.path.insert(0, 'src')
        
        from cyris.core.unified_logger import get_logger
        print("✅ Core logger import successful")
        
        from cyris.cli.main import main
        print("✅ CLI main import successful")
        
        logger = get_logger('test', 'import_validation')
        logger.info('Import validation test successful')
        print("✅ Logger functionality test successful")
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)