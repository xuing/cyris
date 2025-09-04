#!/usr/bin/env python3
"""
Fix All Relative Imports Script

Systematically fixes all relative imports to absolute imports
for modules that might be called from CLI context.
"""

import os
import re
from pathlib import Path

def fix_relative_to_absolute(file_path: Path) -> bool:
    """Convert relative imports to absolute imports"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix unified_logger imports
        content = re.sub(
            r'from \.\.\.core\.unified_logger import',
            'from cyris.core.unified_logger import',
            content
        )
        
        # Fix other core module imports
        content = re.sub(
            r'from \.\.\.core\.([a-z_]+) import',
            r'from cyris.core.\1 import',
            content
        )
        
        # Fix config module imports  
        content = re.sub(
            r'from \.\.\.config\.([a-z_]+) import',
            r'from cyris.config.\1 import',
            content
        )
        
        # Fix domain module imports
        content = re.sub(
            r'from \.\.\.domain\.([a-z_\.]+) import',
            r'from cyris.domain.\1 import',
            content
        )
        
        # Fix services module imports
        content = re.sub(
            r'from \.\.\.services\.([a-z_]+) import',
            r'from cyris.services.\1 import',
            content
        )
        
        # Fix infrastructure module imports
        content = re.sub(
            r'from \.\.\.infrastructure\.([a-z_\.]+) import',
            r'from cyris.infrastructure.\1 import',
            content
        )
        
        # Fix tools module imports
        content = re.sub(
            r'from \.\.\.tools\.([a-z_]+) import',
            r'from cyris.tools.\1 import',
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
    """Fix all relative import issues comprehensively"""
    print("🔧 Fixing ALL Relative Imports")
    print("=" * 50)
    
    # Find all Python files with relative imports to unified_logger
    result = os.popen('grep -r "from \.\.\..*unified_logger" src/ --include="*.py" -l').read()
    files_to_fix = [line.strip() for line in result.split('\n') if line.strip()]
    
    print(f"Found {len(files_to_fix)} files with relative imports to fix:")
    
    fixed_count = 0
    
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            if fix_relative_to_absolute(path):
                print(f"✅ Fixed: {file_path}")
                fixed_count += 1
            else:
                print(f"ℹ️  No change needed: {file_path}")
        else:
            print(f"❌ File not found: {file_path}")
    
    print("=" * 50)
    print(f"🎯 Summary: Fixed {fixed_count} files")
    
    # Test imports after fixes
    print("\n🧪 Testing imports after comprehensive fixes...")
    try:
        import sys
        sys.path.insert(0, 'src')
        
        # Test core modules
        from cyris.core.unified_logger import get_logger
        print("✅ Core logger import successful")
        
        # Test CLI
        from cyris.cli.main import main  
        print("✅ CLI main import successful")
        
        # Test config (often fails due to relative imports)
        from cyris.config.parser import CyRISConfigParser
        print("✅ Config parser import successful")
        
        # Test a service
        from cyris.services.orchestrator import CyRISOrchestrator
        print("✅ Orchestrator import successful")
        
        logger = get_logger('test', 'comprehensive_validation')
        logger.info('Comprehensive import validation successful')
        print("✅ Logger functionality test successful")
        
        print("\n🎉 All critical imports working!")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)