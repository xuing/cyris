# CyRIS Cloud-Init ISO 构造指南

## 📋 概述

Cloud-init ISO 是 CyRIS 系统中用于 VM 自动化初始化的关键组件。它包含了用户配置、网络设置、软件包安装等自动化脚本，确保 VM 启动后能够正确配置并可通过 SSH 访问。

## 🎯 现有状态

你的系统已经有一个可用的 cloud-init.iso：

```bash
# 位置
/home/ubuntu/cyris/images/cloud-init.iso

# 文件信息
-rwxr-xr-x 1 libvirt-qemu kvm 374784 Aug 21 20:46 cloud-init.iso

# 格式
ISO 9660 CD-ROM filesystem data 'cidata'
```

### 当前配置内容
- **用户**: ubuntu, trainee01 (都有 sudo 权限)
- **密码**: ubuntu/ubuntu, trainee01/trainee123  
- **SSH**: 启用密码认证 + SSH 密钥认证
- **软件包**: openssh-server, curl, wget, vim, net-tools
- **服务**: SSH 自动启用和启动

## 🔧 构造方法

### 方法一: 使用完整脚本 (推荐)

```bash
# 使用完整功能的构造脚本
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh

# 自定义选项
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh \
    --instance-id "my-vm" \
    --hostname "my-host" \
    --output "/path/to/output.iso"

# 查看帮助
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh --help
```

### 方法二: 快速构造 (测试用)

```bash
# 快速重新构造现有 ISO
/home/ubuntu/cyris/scripts/quick-cloud-init.sh
```

### 方法三: 手动构造

```bash
# 1. 创建工作目录
TEMP_DIR=$(mktemp -d)

# 2. 创建 meta-data 文件
cat > "$TEMP_DIR/meta-data" << EOF
instance-id: cyris-vm
local-hostname: cyris-desktop
EOF

# 3. 创建 user-data 文件
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

chpasswd:
  list: |
    ubuntu:ubuntu123
    trainee01:trainee123
  expire: False

ssh_pwauth: True

packages:
  - openssh-server
  - net-tools
  - curl
  - vim

runcmd:
  - systemctl enable ssh
  - systemctl start ssh
  - dhclient -v
  - echo "Setup complete" > /var/log/cyris-init.log

network:
  version: 2
  ethernets:
    ens3:
      dhcp4: true
    eth0:
      dhcp4: true
EOF

# 4. 构造 ISO
genisoimage -output /home/ubuntu/cyris/images/cloud-init.iso \
            -volid cidata \
            -joliet \
            -rock \
            "$TEMP_DIR"

# 5. 设置权限
chmod 644 /home/ubuntu/cyris/images/cloud-init.iso
chown libvirt-qemu:kvm /home/ubuntu/cyris/images/cloud-init.iso

# 6. 清理
rm -rf "$TEMP_DIR"
```

## 📁 文件结构

Cloud-init ISO 包含以下核心文件：

```
cloud-init.iso
├── meta-data          # VM 元数据 (instance-id, hostname)
├── user-data          # 用户和系统配置 (主要配置文件)
└── network-config     # 网络配置 (可选)
```

### meta-data 示例
```yaml
instance-id: cyris-vm
local-hostname: cyris-desktop
```

### user-data 核心配置

```yaml
#cloud-config

# 用户配置
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false

# 密码设置
chpasswd:
  list: |
    ubuntu:password123
  expire: False

# SSH 配置
ssh_pwauth: True

# 软件包安装
packages:
  - openssh-server
  - net-tools

# 启动时执行
runcmd:
  - systemctl enable ssh
  - systemctl start ssh
  - dhclient -v
```

## 🔍 验证和测试

### 验证 ISO 内容
```bash
# 检查文件类型
file /home/ubuntu/cyris/images/cloud-init.iso

# 列出 ISO 内容
isoinfo -l -i /home/ubuntu/cyris/images/cloud-init.iso

# 查看 user-data 内容
isoinfo -i /home/ubuntu/cyris/images/cloud-init.iso -x "/USER_DAT.;1"

# 查看 meta-data 内容  
isoinfo -i /home/ubuntu/cyris/images/cloud-init.iso -x "/META_DAT.;1"
```

### 测试 VM 初始化
```bash
# 1. 确保 basevm.xml 中已启用 cloud-init ISO
grep -A5 "cloud-init.iso" /home/ubuntu/cyris/images/basevm.xml

# 2. 创建测试 VM
./cyris create examples/basic.yml

# 3. 检查 VM 状态
./cyris status basic --verbose

# 4. 测试 SSH 连接
# 获取 VM IP 后测试
ssh ubuntu@<VM_IP>  # 密码: ubuntu123
ssh trainee01@<VM_IP>  # 密码: trainee123
```

## 🚨 常见问题

### 问题 1: VM 无法获取网络配置
**原因**: cloud-init ISO 未正确挂载或网络配置不正确
**解决**: 
```bash
# 检查 XML 配置
grep -A10 "cloud-init" /home/ubuntu/cyris/images/basevm.xml

# 重新构造 ISO 
/home/ubuntu/cyris/scripts/quick-cloud-init.sh
```

### 问题 2: SSH 无法连接
**原因**: SSH 服务未启动或防火墙阻止
**解决**:
```bash
# 通过控制台检查
virsh console <vm-name>

# 检查 SSH 服务
sudo systemctl status ssh

# 检查网络
ip addr show
```

### 问题 3: 用户密码不正确
**原因**: cloud-init 配置中密码设置问题
**解决**:
```bash
# 更新 user-data 中的 chpasswd 配置
# 重新构造 ISO
# 重新创建 VM
```

## 📚 高级配置

### SSH 密钥认证
```yaml
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAA... your-public-key
```

### 自定义软件安装
```yaml
packages:
  - docker.io
  - python3-pip
  - nginx

runcmd:
  - pip3 install flask
  - systemctl enable docker
  - systemctl start docker
```

### 网络高级配置
```yaml
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: true
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
```

## 🎉 最佳实践

1. **备份现有 ISO**: 修改前先备份
2. **测试配置**: 用小规模测试验证配置
3. **权限设置**: 确保 libvirt 有读取权限
4. **日志检查**: VM 内检查 `/var/log/cloud-init.log`
5. **网络验证**: 确保 DHCP 和网络接口正确配置

## 🔄 维护更新

```bash
# 定期重新构造 (更新软件包等)
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh

# 备份重要配置
cp /home/ubuntu/cyris/images/cloud-init.iso /backup/cloud-init-$(date +%Y%m%d).iso

# 版本管理
git add images/cloud-init.iso
git commit -m "update cloud-init configuration"
```

---

📖 **总结**: 你的 cloud-init.iso 已经正确配置并可用。如需重新构造或自定义，可使用提供的脚本工具。关键是确保 basevm.xml 中已启用 ISO 挂载，这样 VM 才能自动应用配置。