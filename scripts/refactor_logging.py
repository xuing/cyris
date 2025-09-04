#!/usr/bin/env python3
"""
Logging Refactoring Script

This script automatically refactors all print() statements and logging.getLogger()
calls throughout the CyRIS codebase to use the unified logging system.

Usage:
    python scripts/refactor_logging.py --dry-run  # See what would be changed
    python scripts/refactor_logging.py           # Apply changes
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Add src to path for importing unified logger
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory tree"""
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in {
            '__pycache__', '.git', '.pytest_cache', 'node_modules',
            '.venv', 'venv', 'env', 'build', 'dist'
        }]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    return python_files

def analyze_file(file_path: Path) -> Dict[str, List[Tuple[int, str]]]:
    """Analyze a file for logging patterns that need refactoring"""
    patterns = {
        'print_statements': [],
        'logging_getlogger': [],
        'logger_assignments': [],
        'import_logging': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return patterns
    
    for i, line in enumerate(lines, 1):
        # Find print statements
        if re.search(r'\bprint\s*\(', line):
            patterns['print_statements'].append((i, line.strip()))
        
        # Find logging.getLogger calls
        if re.search(r'logging\.getLogger\s*\(', line):
            patterns['logging_getlogger'].append((i, line.strip()))
        
        # Find logger assignments
        if re.search(r'self\.logger\s*=.*logging\.getLogger', line):
            patterns['logger_assignments'].append((i, line.strip()))
        
        # Find import logging statements
        if re.search(r'^\s*import\s+logging\s*$', line):
            patterns['import_logging'].append((i, line.strip()))
    
    return patterns

def generate_component_name(file_path: Path) -> str:
    """Generate appropriate component name from file path"""
    # Remove src/cyris/ prefix and .py suffix
    relative_path = str(file_path).replace('src/cyris/', '').replace('.py', '')
    
    # Extract meaningful component name
    parts = relative_path.split('/')
    
    if len(parts) >= 2:
        return parts[-1]  # Use filename as component
    else:
        return parts[0]

def refactor_file(file_path: Path, dry_run: bool = False) -> bool:
    """Refactor a single file to use unified logging"""
    patterns = analyze_file(file_path)
    
    # Skip files that don't need changes
    if not any(patterns.values()):
        return False
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Refactoring: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False
    
    modified = False
    component_name = generate_component_name(file_path)
    
    # Track if we need to add unified logger import
    needs_unified_import = False
    has_existing_import = False
    
    # Check if file already imports unified logger
    if 'from ..core.unified_logger import' in content or 'from ...core.unified_logger import' in content:
        has_existing_import = True
    
    new_lines = []
    
    for i, line in enumerate(lines):
        new_line = line
        
        # Replace import logging
        if re.search(r'^\s*import\s+logging\s*$', line):
            # Determine correct relative import based on file location
            if 'src/cyris/services/' in str(file_path):
                import_line = "from ..core.unified_logger import get_logger"
            elif 'src/cyris/infrastructure/' in str(file_path):
                import_line = "from ...core.unified_logger import get_logger"
            elif 'src/cyris/cli/' in str(file_path):
                import_line = "from ..core.unified_logger import get_logger"
            elif 'src/cyris/tools/' in str(file_path):
                import_line = "from ..core.unified_logger import get_logger"
            elif 'src/cyris/config/' in str(file_path):
                import_line = "from ..core.unified_logger import get_logger"
            else:
                import_line = "from cyris.core.unified_logger import get_logger"
            
            new_line = f"# import logging  # Replaced with unified logger\n{import_line}"
            modified = True
            needs_unified_import = False  # Already added
            
        # Replace logging.getLogger calls
        elif re.search(r'logging\.getLogger\s*\(\s*__name__\s*\)', line):
            new_line = re.sub(
                r'logging\.getLogger\s*\(\s*__name__\s*\)',
                f'get_logger(__name__, "{component_name}")',
                line
            )
            modified = True
            needs_unified_import = True
            
        # Replace self.logger assignments
        elif re.search(r'self\.logger\s*=.*logging\.getLogger\s*\(\s*__name__\s*\)', line):
            indent = len(line) - len(line.lstrip())
            new_line = ' ' * indent + f'self.logger = get_logger(__name__, "{component_name}")'
            modified = True
            needs_unified_import = True
        
        # Replace simple print statements (conservative approach)
        elif re.search(r'^\s*print\s*\(', line):
            # Only replace simple print statements, not those in complex expressions
            print_match = re.search(r'^\s*print\s*\((.*)\)\s*$', line)
            if print_match:
                indent = len(line) - len(line.lstrip())
                args = print_match.group(1)
                
                # Convert print arguments to logger call
                if args.strip().startswith('f"') or args.strip().startswith("f'"):
                    # f-string
                    new_line = ' ' * indent + f'self.logger.info({args})'
                else:
                    # Regular string or variables
                    new_line = ' ' * indent + f'self.logger.info({args})'
                
                modified = True
                needs_unified_import = True
        
        new_lines.append(new_line)
    
    # Add unified logger import if needed and not already present
    if needs_unified_import and not has_existing_import and not any('unified_logger' in line for line in new_lines):
        # Find the best place to add import
        import_index = 0
        for i, line in enumerate(new_lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                import_index = i + 1
            elif line.strip() == '' and import_index > 0:
                break
        
        # Determine correct relative import
        if 'src/cyris/services/' in str(file_path):
            import_line = "from ..core.unified_logger import get_logger"
        elif 'src/cyris/infrastructure/' in str(file_path):
            import_line = "from ...core.unified_logger import get_logger" 
        elif 'src/cyris/cli/' in str(file_path):
            import_line = "from ..core.unified_logger import get_logger"
        elif 'src/cyris/tools/' in str(file_path):
            import_line = "from ..core.unified_logger import get_logger"
        elif 'src/cyris/config/' in str(file_path):
            import_line = "from ..core.unified_logger import get_logger"
        else:
            import_line = "from cyris.core.unified_logger import get_logger"
        
        new_lines.insert(import_index, import_line)
    
    if modified and not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            print(f"  ✅ Modified {file_path}")
        except Exception as e:
            print(f"  ❌ Error writing {file_path}: {e}")
            return False
    elif modified:
        print(f"  📝 Would modify {file_path}")
        # Show first few changes
        for pattern_name, items in patterns.items():
            if items:
                print(f"    - {pattern_name}: {len(items)} occurrences")
    
    return modified

def main():
    """Main refactoring function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Refactor CyRIS logging to use unified system")
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without modifying files')
    parser.add_argument('--directory', type=str, default='src', help='Directory to refactor (default: src)')
    
    args = parser.parse_args()
    
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    target_dir = project_root / args.directory
    
    if not target_dir.exists():
        print(f"Error: Directory {target_dir} does not exist")
        sys.exit(1)
    
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Refactoring logging in: {target_dir}")
    
    # Find all Python files
    python_files = find_python_files(target_dir)
    print(f"Found {len(python_files)} Python files")
    
    # Process each file
    modified_count = 0
    
    for file_path in python_files:
        try:
            if refactor_file(file_path, args.dry_run):
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Summary:")
    print(f"  📁 Files processed: {len(python_files)}")
    print(f"  ✏️  Files {'would be modified' if args.dry_run else 'modified'}: {modified_count}")
    
    if args.dry_run:
        print(f"\nRun without --dry-run to apply changes")

if __name__ == '__main__':
    main()