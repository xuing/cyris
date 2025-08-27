#!/bin/bash

# 快速构造 cloud-init.iso 的简化版本
# 适用于快速测试和开发

set -e

IMAGES_DIR="/home/ubuntu/cyris/images"
TEMP_DIR=$(mktemp -d)

echo "🚀 快速构造 cloud-init.iso..."

# 检查 genisoimage 工具
if ! command -v genisoimage &> /dev/null; then
    echo "❌ 需要安装 genisoimage 工具"
    echo "运行: sudo apt-get install genisoimage"
    exit 1
fi

# 创建 meta-data
cat > "$TEMP_DIR/meta-data" << 'EOF'
instance-id: cyris-vm
local-hostname: cyris-desktop
EOF

# 创建 user-data
cat > "$TEMP_DIR/user-data" << 'EOF'
#cloud-config

users:
  - default
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
  - name: trainee01
    sudo: ALL=(ALL) NOPASSWD:ALL  
    shell: /bin/bash
    groups: users,admin
    lock_passwd: false

# 设置密码
chpasswd:
  list: |
    ubuntu:ubuntu123
    trainee01:trainee123
  expire: False

# 启用密码登录
ssh_pwauth: True

# 安装基础软件
packages:
  - openssh-server
  - net-tools
  - curl
  - vim

# 启动配置
runcmd:
  - systemctl enable ssh
  - systemctl start ssh
  - dhclient -v
  - echo "Cloud-init setup completed" > /var/log/cyris-init.log

# 网络配置
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: true
    eth0:
      dhcp4: true

final_message: "CyRIS VM ready for use!"
EOF

# 备份现有文件
if [ -f "$IMAGES_DIR/cloud-init.iso" ]; then
    cp "$IMAGES_DIR/cloud-init.iso" "$IMAGES_DIR/cloud-init.iso.backup"
    echo "✅ 已备份现有 ISO"
fi

# 创建 ISO
echo "📦 创建 ISO 镜像..."
genisoimage -output "$IMAGES_DIR/cloud-init.iso" \
            -volid cidata \
            -joliet \
            -rock \
            "$TEMP_DIR"

# 设置权限
chmod 644 "$IMAGES_DIR/cloud-init.iso"
chown libvirt-qemu:kvm "$IMAGES_DIR/cloud-init.iso" 2>/dev/null || true

# 清理
rm -rf "$TEMP_DIR"

echo "✅ cloud-init.iso 创建完成!"
echo "📍 位置: $IMAGES_DIR/cloud-init.iso"
echo "📊 大小: $(du -h "$IMAGES_DIR/cloud-init.iso" | cut -f1)"

# 验证内容
if command -v isoinfo &> /dev/null; then
    echo "📋 ISO 内容:"
    isoinfo -l -i "$IMAGES_DIR/cloud-init.iso" | head -10
fi

echo ""
echo "🎯 使用方法:"
echo "VM 将自动使用此 ISO 进行初始化"
echo "用户: ubuntu/trainee01"  
echo "密码: ubuntu123/trainee123"
echo "SSH: 已启用密码认证"