# ☁️ CyRIS Cloud-Init ISO 完整指南

## 🎯 快速总结

你的 **cloud-init.iso** 已经完全配置好并可用！

```bash
✅ ISO 文件: /home/ubuntu/cyris/images/cloud-init.iso (368K)
✅ 格式: ISO 9660 CD-ROM filesystem data 'cidata'
✅ 配置: basevm.xml 中已启用
✅ 权限: libvirt-qemu:kvm (755)
✅ 内容: meta-data + user-data 完整配置
```

## 🚀 立即可用

当前配置包含：
- **用户**: `ubuntu`, `trainee01` (都有 sudo 权限)
- **密码**: `ubuntu`/`ubuntu`, `trainee01`/`trainee123`
- **SSH**: 密码认证已启用
- **软件**: openssh-server, curl, wget, vim, net-tools
- **网络**: DHCP 自动配置

## 🛠️ 可用工具

### 1. 验证现有配置
```bash
# 运行完整验证
/home/ubuntu/cyris/scripts/validate-cloud-init.sh
```

### 2. 重新构造 ISO (如需要)
```bash
# 快速重新构造
/home/ubuntu/cyris/scripts/quick-cloud-init.sh

# 完整功能构造
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh

# 自定义构造
/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh \
    --instance-id "my-vm" \
    --hostname "my-host"
```

### 3. 检查 ISO 内容
```bash
# 查看文件信息
ls -la /home/ubuntu/cyris/images/cloud-init.iso
file /home/ubuntu/cyris/images/cloud-init.iso

# 查看 ISO 内容
isoinfo -l -i /home/ubuntu/cyris/images/cloud-init.iso

# 查看配置文件
isoinfo -i /home/ubuntu/cyris/images/cloud-init.iso -x "/USER_DAT.;1"
isoinfo -i /home/ubuntu/cyris/images/cloud-init.iso -x "/META_DAT.;1"
```

## 📋 核心配置文件

### meta-data
```yaml
instance-id: cyris-base-vm
local-hostname: cyris-base
```

### user-data (核心配置)
```yaml
#cloud-config

users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
  - name: trainee01
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    groups: users,admin

chpasswd:
  list: |
    ubuntu:ubuntu
    trainee01:trainee123
  expire: False

ssh_pwauth: True

packages:
  - openssh-server
  - curl
  - wget
  - vim
  - net-tools

runcmd:
  - systemctl enable ssh
  - systemctl start ssh
  - echo "Cloud-init setup complete" > /var/log/cloud-init-setup.log
```

## 🧪 测试流程

```bash
# 1. 验证配置
/home/ubuntu/cyris/scripts/validate-cloud-init.sh

# 2. 创建测试 VM
./cyris create examples/basic.yml

# 3. 检查状态
./cyris status basic --verbose

# 4. SSH 连接测试
ssh ubuntu@<VM_IP>     # 密码: ubuntu
ssh trainee01@<VM_IP>  # 密码: trainee123
```

## 🔧 自定义方法

### 手动构造步骤
```bash
# 1. 创建工作目录
TEMP_DIR=$(mktemp -d)

# 2. 创建配置文件
cat > "$TEMP_DIR/meta-data" << EOF
instance-id: my-vm
local-hostname: my-host
EOF

cat > "$TEMP_DIR/user-data" << 'EOF'
#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false

chpasswd:
  list: |
    ubuntu:password123
  expire: False

ssh_pwauth: True

packages:
  - openssh-server
  - net-tools

runcmd:
  - systemctl enable ssh
  - systemctl start ssh
  - dhclient -v
EOF

# 3. 构造 ISO
genisoimage -output /home/ubuntu/cyris/images/cloud-init.iso \
            -volid cidata \
            -joliet \
            -rock \
            "$TEMP_DIR"

# 4. 设置权限
chmod 644 /home/ubuntu/cyris/images/cloud-init.iso
chown libvirt-qemu:kvm /home/ubuntu/cyris/images/cloud-init.iso

# 5. 清理
rm -rf "$TEMP_DIR"
```

## 🚨 故障排除

### VM 无法获取网络
```bash
# 检查 basevm.xml 中 cloud-init 是否启用
grep -A5 "cloud-init" /home/ubuntu/cyris/images/basevm.xml

# 重新构造 ISO
/home/ubuntu/cyris/scripts/quick-cloud-init.sh
```

### SSH 连接失败
```bash
# 通过控制台检查
virsh console <vm-name>

# 检查 SSH 服务
sudo systemctl status ssh

# 检查网络
ip addr show
dhclient -v
```

### 权限问题
```bash
# 修复权限
chmod 644 /home/ubuntu/cyris/images/cloud-init.iso
chown libvirt-qemu:kvm /home/ubuntu/cyris/images/cloud-init.iso
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

### 静态网络配置
```yaml
network:
  version: 2
  ethernets:
    ens3:
      addresses: [192.168.1.100/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
```

## 🎉 最佳实践

1. **定期备份**: `cp cloud-init.iso cloud-init-backup-$(date +%Y%m%d).iso`
2. **测试配置**: 先在小规模环境测试新配置
3. **日志检查**: VM 内检查 `/var/log/cloud-init.log`
4. **权限验证**: 确保 libvirt 有正确访问权限
5. **版本控制**: 重要配置变更使用 git 管理

## 📖 相关文档

- **详细指南**: `/home/ubuntu/cyris/docs/cloud-init-setup-guide.md`
- **验证脚本**: `/home/ubuntu/cyris/scripts/validate-cloud-init.sh`
- **构造脚本**: `/home/ubuntu/cyris/scripts/create-cloud-init-iso.sh`
- **快速脚本**: `/home/ubuntu/cyris/scripts/quick-cloud-init.sh`

---

🎯 **结论**: 你的 cloud-init.iso 已完全配置并验证通过，VM 创建时会自动应用用户配置、网络设置和 SSH 访问！