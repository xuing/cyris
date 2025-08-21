#!/usr/bin/env python3
"""
Script to systematically replace Chinese text with English equivalents
"""

import os
import re
from pathlib import Path

# Chinese to English translation mapping
translations = {
    # Module descriptions
    "虚拟机实体模块": "Virtual Machine Entity Module",
    "主机实体模块": "Host Entity Module", 
    "基础实体类": "Base Entity Classes",
    "配置解析器模块": "Configuration Parser Module",
    "支持传统INI格式和现代YAML格式配置": "Supports legacy INI and modern YAML configuration formats",
    "领域模型模块": "Domain Model Module",
    "配置管理模块": "Configuration Management Module",
    "领域实体模块": "Domain Entity Module",
    "现代化CLI接口模块": "Modern CLI Interface Module",
    
    # Class descriptions
    "基础虚拟机类型": "Base Virtual Machine Type",
    "操作系统类型": "Operating System Type",
    "虚拟机实体": "Virtual Machine Entity",
    "表示虚拟机的配置信息": "Represents virtual machine configuration information",
    "主机实体": "Host Entity",
    "表示物理主机或虚拟主机的配置信息": "Represents physical or virtual host configuration information",
    "基础实体类": "Base Entity Class",
    "值对象基类": "Value Object Base Class",
    "虚拟机构建器": "Virtual Machine Builder",
    "主机构建器": "Host Builder",
    "配置相关错误": "Configuration-related errors",
    
    # Field descriptions
    "虚拟机唯一标识符": "Virtual machine unique identifier",
    "基础虚拟机地址": "Base virtual machine address", 
    "Root密码": "Root password",
    "基础虚拟机所在主机": "Host where base virtual machine is located",
    "基础虚拟机配置文件路径": "Base virtual machine configuration file path",
    "操作系统类型": "Operating system type",
    "虚拟化平台类型": "Virtualization platform type",
    "基础虚拟机名称": "Base virtual machine name",
    "任务列表": "Task list",
    "主机唯一标识符": "Host unique identifier",
    "管理地址": "Management address",
    "虚拟桥接地址": "Virtual bridge address",
    "主机账户名": "Host account name",
    
    # Method descriptions
    "验证配置文件路径": "Validate configuration file path",
    "允许相对路径，但检查格式": "Allow relative paths, but check format",
    "获取虚拟机ID": "Get virtual machine ID",
    "获取基础虚拟机地址": "Get base virtual machine address",
    "设置基础虚拟机地址": "Set base virtual machine address", 
    "获取root密码": "Get root password",
    "设置root密码": "Set root password",
    "获取基础虚拟机主机": "Get base virtual machine host",
    "获取配置文件路径": "Get configuration file path",
    "获取虚拟化平台类型": "Get virtualization platform type",
    "获取任务列表": "Get task list",
    "添加任务": "Add task",
    "构建虚拟机实例": "Build virtual machine instance",
    "获取主机ID": "Get host ID",
    "获取管理地址": "Get management address", 
    "获取虚拟桥接地址": "Get virtual bridge address",
    "获取账户名": "Get account name",
    "构建主机实例": "Build host instance",
    "验证地址不为空": "Validate address is not empty",
    
    # Parser descriptions
    "解析传统INI格式配置文件": "Parse legacy INI format configuration file",
    "保持与原始parse_config函数的兼容性": "Maintain compatibility with original parse_config function", 
    "解析各个配置项": "Parse individual configuration items",
    "gw_mode 特殊处理": "Special handling for gw_mode",
    "解析现代YAML格式配置文件": "Parse modern YAML format configuration file",
    "配置文件路径": "Configuration file path",
    "解析后的配置对象": "Parsed configuration object",
    "配置文件解析或验证失败": "Configuration file parsing or validation failed",
    "尝试解析为INI格式并转换": "Try parsing as INI format and convert",
    "创建默认配置文件": "Create default configuration file",
    "默认配置对象": "Default configuration object",
    "创建YAML格式的配置文件": "Create YAML format configuration file",
    
    # Entity base descriptions
    "允许任意类型（向后兼容）": "Allow any type (backwards compatible)",
    "使用枚举值": "Use enumeration values", 
    "值对象不可变": "Value objects are immutable",
}

def replace_chinese_in_file(file_path):
    """Replace Chinese text in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply translations
        for chinese, english in translations.items():
            content = content.replace(chinese, english)
        
        # Check if any changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {file_path}")
            return True
        else:
            print(f"⚪ No changes: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all files"""
    print("🔄 Starting Chinese text replacement...")
    
    # Find all Python files in src directory
    src_dir = Path("src")
    if not src_dir.exists():
        print("❌ src directory not found")
        return
    
    python_files = list(src_dir.rglob("*.py"))
    
    updated_count = 0
    total_count = len(python_files)
    
    for file_path in python_files:
        if replace_chinese_in_file(file_path):
            updated_count += 1
    
    print(f"\n📊 Summary: {updated_count}/{total_count} files updated")
    
    # Verify no Chinese text remains
    print("\n🔍 Verifying no Chinese text remains...")
    remaining_files = []
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for Chinese characters
            if re.search(r'[\u4e00-\u9fff]', content):
                remaining_files.append(file_path)
        except Exception as e:
            print(f"⚠️ Error checking {file_path}: {e}")
    
    if remaining_files:
        print(f"⚠️ Chinese text still found in {len(remaining_files)} files:")
        for file_path in remaining_files:
            print(f"  - {file_path}")
    else:
        print("✅ All Chinese text successfully replaced!")

if __name__ == "__main__":
    main()