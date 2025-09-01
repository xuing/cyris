#!/usr/bin/env python3
"""
Demo script for VM IP discovery functionality

This script demonstrates how to get VM IP addresses using the new VMIPManager.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cyris.tools.vm_ip_manager import VMIPManager, get_vm_ips_cli
import logging

def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🚀 CyRIS VM IP Discovery Demo")
    print("=" * 50)
    
    # Initialize VM IP Manager
    manager = VMIPManager()
    
    try:
        # Discover all VMs
        print("\n1. 发现所有虚拟机...")
        all_vms = manager._discover_all_vms()
        print(f"   找到 {len(all_vms)} 个虚拟机: {all_vms}")
        
        if not all_vms:
            print("   没有找到虚拟机，请先创建一些VM")
            return
        
        # Test different discovery methods for each VM
        print("\n2. 测试不同的IP发现方法...")
        for vm_name in all_vms[:3]:  # Test first 3 VMs
            print(f"\n   🖥️  测试 VM: {vm_name}")
            
            # Method 1: libvirt
            try:
                vm_info = manager._get_ips_via_libvirt(vm_name)
                if vm_info:
                    print(f"      ✅ libvirt: {vm_info.ip_addresses}")
                    print(f"         状态: {vm_info.status}")
                else:
                    print(f"      ❌ libvirt: 未找到IP")
            except Exception as e:
                print(f"      ⚠️  libvirt: 错误 - {e}")
            
            # Method 2: virsh
            try:
                vm_info = manager._get_ips_via_virsh(vm_name)
                if vm_info:
                    print(f"      ✅ virsh: {vm_info.ip_addresses}")
                else:
                    print(f"      ❌ virsh: 未找到IP")
            except Exception as e:
                print(f"      ⚠️  virsh: 错误 - {e}")
            
            # Method 3: MAC addresses
            try:
                macs = manager._get_vm_mac_addresses(vm_name)
                if macs:
                    print(f"      🔗 MAC地址: {macs}")
                else:
                    print(f"      ❌ 未找到MAC地址")
            except Exception as e:
                print(f"      ⚠️  MAC查询错误: {e}")
        
        print("\n3. 综合IP发现测试...")
        # Test comprehensive discovery
        for vm_name in all_vms[:2]:  # Test first 2 VMs
            print(f"\n   🔍 综合测试 VM: {vm_name}")
            vm_info = manager.get_vm_ip_addresses(vm_name)
            
            if vm_info:
                print(f"      ✅ 发现IP地址: {vm_info.ip_addresses}")
                print(f"      📊 状态: {vm_info.status}")
                print(f"      🔍 发现方法: {vm_info.discovery_method}")
                if vm_info.mac_addresses:
                    print(f"      🔗 MAC地址: {vm_info.mac_addresses}")
            else:
                print(f"      ❌ 未能发现IP地址")
        
        # Show available commands
        print("\n4. 可用的命令示例:")
        print("   # 获取单个VM的IP地址")
        print("   ./cyris get-vm-ip <vm_name>")
        print("   ./cyris get-vm-ip desktop --range-id basic --verbose")
        print("   ./cyris get-vm-ip desktop --wait --timeout 60")
        
        print("\n   # 列出所有VM的IP地址")
        print("   ./cyris list-vm-ips")
        print("   ./cyris list-vm-ips --range-id basic --verbose")
        
        print("\n   # 直接使用virsh命令")
        print("   virsh domifaddr <vm_name>")
        print("   virsh list --all")
        
    finally:
        manager.close()

if __name__ == "__main__":
    main()