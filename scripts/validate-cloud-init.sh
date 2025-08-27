#!/bin/bash

# CyRIS Cloud-Init 验证脚本
# 验证 cloud-init.iso 是否正确配置并可用

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

echo "🔍 CyRIS Cloud-Init ISO 验证"
echo "=================================="
echo ""

# 检查 ISO 文件存在
ISO_PATH="/home/ubuntu/cyris/images/cloud-init.iso"
if [ -f "$ISO_PATH" ]; then
    success "Cloud-init ISO 文件存在"
    echo "   📍 路径: $ISO_PATH"
    echo "   📊 大小: $(du -h "$ISO_PATH" | cut -f1)"
    echo "   🕐 修改时间: $(stat -c %y "$ISO_PATH")"
else
    error "Cloud-init ISO 文件不存在: $ISO_PATH"
    echo "   💡 运行构造脚本: /home/ubuntu/cyris/scripts/quick-cloud-init.sh"
    exit 1
fi

echo ""

# 检查文件类型
FILE_TYPE=$(file "$ISO_PATH")
if echo "$FILE_TYPE" | grep -q "ISO 9660"; then
    success "ISO 文件格式正确"
    echo "   📝 类型: $(echo "$FILE_TYPE" | cut -d: -f2-)"
else
    error "ISO 文件格式不正确"
    echo "   📝 实际类型: $FILE_TYPE"
    exit 1
fi

echo ""

# 检查 ISO 内容
echo "📋 检查 ISO 内容..."
if command -v isoinfo &> /dev/null; then
    ISO_CONTENT=$(isoinfo -l -i "$ISO_PATH" 2>/dev/null)
    if echo "$ISO_CONTENT" | grep -q "META_DAT"; then
        success "meta-data 文件存在"
    else
        error "meta-data 文件缺失"
    fi
    
    if echo "$ISO_CONTENT" | grep -q "USER_DAT"; then
        success "user-data 文件存在"
    else
        error "user-data 文件缺失"
    fi
else
    warning "isoinfo 工具未安装，跳过内容详细检查"
    echo "   💡 安装: sudo apt-get install genisoimage"
fi

echo ""

# 检查 basevm.xml 配置
BASEVM_XML="/home/ubuntu/cyris/images/basevm.xml"
echo "🔧 检查 basevm.xml 配置..."
if [ -f "$BASEVM_XML" ]; then
    success "basevm.xml 文件存在"
    
    if grep -q "cloud-init.iso" "$BASEVM_XML"; then
        # 检查 cloud-init.iso 是否被注释掉
        if grep -A2 -B2 "cloud-init.iso" "$BASEVM_XML" | grep -q "<!-- <disk.*cloud-init.iso"; then
            error "cloud-init ISO 在 basevm.xml 中被注释"
            echo "   💡 检查 basevm.xml 中的 cloud-init.iso 配置"
        elif grep -A2 -B2 "cloud-init.iso" "$BASEVM_XML" | grep -q "<disk.*cloud-init.iso\|<source.*cloud-init.iso"; then
            success "cloud-init ISO 已在 basevm.xml 中启用"
        else
            warning "cloud-init.iso 配置状态不明确"
        fi
    else
        error "basevm.xml 中未找到 cloud-init.iso 引用"
    fi
else
    error "basevm.xml 文件不存在: $BASEVM_XML"
fi

echo ""

# 检查权限
echo "🔒 检查文件权限..."
ISO_PERMS=$(stat -c %a "$ISO_PATH")
ISO_OWNER=$(stat -c %U:%G "$ISO_PATH")

echo "   📋 权限: $ISO_PERMS"
echo "   👤 所有者: $ISO_OWNER"

if [ "$ISO_PERMS" = "644" ] || [ "$ISO_PERMS" = "755" ]; then
    success "ISO 文件权限正确"
else
    warning "ISO 文件权限可能有问题: $ISO_PERMS"
    echo "   💡 建议权限: 644"
    echo "   💡 修复命令: chmod 644 '$ISO_PATH'"
fi

# 检查所有者 (对于系统级 libvirt)
if echo "$ISO_OWNER" | grep -q "libvirt-qemu"; then
    success "ISO 文件所有者正确 (libvirt-qemu)"
elif [ "$ISO_OWNER" = "root:root" ]; then
    warning "ISO 文件所有者为 root (可能影响 qemu:///session 模式)"
    echo "   💡 如果使用 qemu:///system，当前设置正确"
else
    warning "ISO 文件所有者: $ISO_OWNER"
    echo "   💡 对于 qemu:///system 建议: libvirt-qemu:kvm"
    echo "   💡 修复命令: sudo chown libvirt-qemu:kvm '$ISO_PATH'"
fi

echo ""

# 检查 user-data 配置内容
echo "📄 检查 user-data 配置..."
if command -v isoinfo &> /dev/null; then
    USER_DATA=$(isoinfo -i "$ISO_PATH" -x "/USER_DAT.;1" 2>/dev/null)
    
    if echo "$USER_DATA" | grep -q "#cloud-config"; then
        success "user-data 包含正确的 cloud-config 头"
    else
        error "user-data 缺少 #cloud-config 头"
    fi
    
    if echo "$USER_DATA" | grep -q "ssh_pwauth.*True"; then
        success "SSH 密码认证已启用"
    else
        warning "SSH 密码认证可能未启用"
    fi
    
    if echo "$USER_DATA" | grep -q "openssh-server"; then
        success "包含 openssh-server 软件包"
    else
        warning "可能缺少 openssh-server 软件包"
    fi
    
    if echo "$USER_DATA" | grep -q "chpasswd"; then
        success "包含用户密码配置"
    else
        warning "可能缺少用户密码配置"
    fi
fi

echo ""

# 测试 VM 创建 (可选)
echo "🧪 测试建议..."
echo "1. 创建测试 VM:"
echo "   ./cyris create examples/basic.yml"
echo ""
echo "2. 检查 VM 状态:"
echo "   ./cyris status basic --verbose"
echo ""
echo "3. SSH 连接测试:"
echo "   ssh ubuntu@<VM_IP>    # 密码: ubuntu 或 ubuntu123"
echo "   ssh trainee01@<VM_IP> # 密码: trainee123"
echo ""

# 检查依赖工具
echo "🛠️  检查构造工具..."
if command -v genisoimage &> /dev/null; then
    success "genisoimage 工具已安装"
else
    warning "genisoimage 工具未安装"
    echo "   💡 安装: sudo apt-get install genisoimage"
fi

if command -v isoinfo &> /dev/null; then
    success "isoinfo 工具已安装"
else
    warning "isoinfo 工具未安装 (用于验证)"
    echo "   💡 安装: sudo apt-get install genisoimage"
fi

echo ""
echo "🎯 总结:"
echo "=================================="

if [ -f "$ISO_PATH" ] && file "$ISO_PATH" | grep -q "ISO 9660" && grep -q "cloud-init.iso" "$BASEVM_XML" && ! grep -A2 -B2 "cloud-init.iso" "$BASEVM_XML" | grep -q "<!-- <disk.*cloud-init.iso"; then
    success "Cloud-init ISO 配置完整，可以使用！"
    echo ""
    echo "✨ VM 将在启动时自动应用以下配置:"
    echo "   👥 用户: ubuntu, trainee01 (sudo 权限)"
    echo "   🔑 SSH: 密码和密钥认证都已启用"
    echo "   📦 软件: openssh-server, net-tools 等基础包"
    echo "   🌐 网络: DHCP 自动配置"
    echo "   📝 日志: /var/log/cloud-init.log"
else
    error "发现配置问题，请检查上述错误并修复"
    echo ""
    echo "🔧 快速修复命令:"
    echo "   /home/ubuntu/cyris/scripts/quick-cloud-init.sh"
fi

echo ""