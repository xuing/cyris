#!/bin/bash

# CyRIS Cloud-Init ISO 构造脚本
# 用于生成 VM 自动化配置的 cloud-init ISO 镜像

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGES_DIR="$PROJECT_ROOT/images"
TEMP_DIR=$(mktemp -d)

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖工具..."
    
    local missing_tools=()
    
    if ! command -v genisoimage &> /dev/null; then
        missing_tools+=("genisoimage")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "缺少必要工具: ${missing_tools[*]}"
        log_info "安装命令: sudo apt-get install genisoimage"
        exit 1
    fi
    
    log_success "所有依赖工具已安装"
}

# 生成 SSH 密钥对 (如果不存在)
generate_ssh_key() {
    local ssh_dir="$PROJECT_ROOT/.ssh"
    local key_path="$ssh_dir/cyris_rsa"
    
    if [ ! -f "$key_path" ]; then
        log_info "生成 CyRIS SSH 密钥对..."
        mkdir -p "$ssh_dir"
        ssh-keygen -t rsa -b 2048 -f "$key_path" -N "" -C "cyris-system"
        log_success "SSH 密钥对已生成: $key_path"
    else
        log_info "使用现有 SSH 密钥: $key_path"
    fi
    
    echo "$key_path.pub"
}

# 创建 meta-data 文件
create_meta_data() {
    local temp_dir="$1"
    local instance_id="${2:-cyris-base-vm}"
    local hostname="${3:-cyris-base}"
    
    log_info "创建 meta-data 文件..."
    
    cat > "$temp_dir/meta-data" << EOF
instance-id: $instance_id
local-hostname: $hostname
EOF
    
    log_success "meta-data 文件已创建"
}

# 创建 user-data 文件
create_user_data() {
    local temp_dir="$1"
    local ssh_pub_key_path="$2"
    
    log_info "创建 user-data 文件..."
    
    # 读取 SSH 公钥
    local ssh_public_key=""
    if [ -f "$ssh_pub_key_path" ]; then
        ssh_public_key=$(cat "$ssh_pub_key_path")
        log_info "使用 SSH 公钥: ${ssh_public_key:0:50}..."
    else
        log_warning "SSH 公钥文件不存在，使用占位符"
        ssh_public_key="ssh-rsa PLACEHOLDER_KEY_WILL_BE_REPLACED"
    fi
    
    cat > "$temp_dir/user-data" << EOF
#cloud-config

# 用户配置
users:
  # 保留默认用户
  - default
  
  # Ubuntu 系统用户 (管理员)
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    ssh_authorized_keys:
      - $ssh_public_key
  
  # CyRIS 训练用户
  - name: trainee01
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    groups: users,admin
    lock_passwd: false
    ssh_authorized_keys:
      - $ssh_public_key
  
  # 可选: 添加更多训练用户
  - name: trainee02
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    shell: /bin/bash
    groups: users
    lock_passwd: false

# 设置用户密码 (仅用于演示，生产环境建议仅使用密钥)
chpasswd:
  list: |
    ubuntu:ubuntu123
    trainee01:trainee123
    trainee02:trainee456
  expire: False

# 启用密码认证 (用于测试，生产环境建议关闭)
ssh_pwauth: True

# 软件包安装
packages:
  - openssh-server
  - curl
  - wget
  - vim
  - nano
  - net-tools
  - htop
  - tree
  - git
  - python3
  - python3-pip

# 系统配置命令
runcmd:
  # 启用 SSH 服务
  - systemctl enable ssh
  - systemctl start ssh
  
  # 配置网络 (确保网络接口启用)
  - dhclient -v
  
  # 创建日志目录
  - mkdir -p /var/log/cyris
  
  # 设置时区
  - timedatectl set-timezone UTC
  
  # 记录初始化完成
  - echo "CyRIS Cloud-init setup completed at \$(date)" >> /var/log/cyris/setup.log
  - echo "SSH service status: \$(systemctl is-active ssh)" >> /var/log/cyris/setup.log
  - echo "Network interfaces:" >> /var/log/cyris/setup.log
  - ip addr show >> /var/log/cyris/setup.log

# 网络配置
network:
  version: 2
  ethernets:
    ens3:
      dhcp4: true
      dhcp6: false

# 文件写入 (可选配置文件)
write_files:
  - path: /etc/motd
    content: |
      
      ====================================
      Welcome to CyRIS Training Environment
      ====================================
      
      This VM is part of a cybersecurity training range.
      
      Available users:
      - ubuntu (admin)
      - trainee01 (student)
      - trainee02 (student)
      
      For support, check /var/log/cyris/
      
    permissions: '0644'
  
  - path: /home/ubuntu/.bashrc.cyris
    content: |
      # CyRIS specific bash configuration
      export CYRIS_ENV=true
      export PS1='\[\e[1;32m\][CyRIS]\[\e[0m\] \u@\h:\w\$ '
      
      # Useful aliases
      alias ll='ls -la'
      alias la='ls -la'
      alias ..='cd ..'
      alias cyris-status='systemctl status ssh && ip addr show'
    permissions: '0644'
    owner: ubuntu:ubuntu

# 最终配置
final_message: |
  CyRIS VM initialization completed successfully!
  
  VM Details:
  - SSH Service: Active
  - Network: DHCP configured
  - Users: ubuntu, trainee01, trainee02
  
  Access methods:
  - SSH with keys or passwords
  - Console access available
  
  Log files: /var/log/cyris/setup.log
EOF
    
    log_success "user-data 文件已创建"
}

# 创建 network-config 文件 (可选)
create_network_config() {
    local temp_dir="$1"
    
    log_info "创建 network-config 文件..."
    
    cat > "$temp_dir/network-config" << EOF
version: 2
ethernets:
  ens3:
    dhcp4: true
    dhcp6: false
  eth0:
    dhcp4: true
    dhcp6: false
EOF
    
    log_success "network-config 文件已创建"
}

# 构造 ISO 镜像
create_iso() {
    local temp_dir="$1"
    local output_path="$2"
    
    log_info "构造 cloud-init ISO 镜像..."
    
    # 确保输出目录存在
    mkdir -p "$(dirname "$output_path")"
    
    # 创建 ISO
    genisoimage -output "$output_path" \
                -volid cidata \
                -joliet \
                -rock \
                -input-charset utf-8 \
                "$temp_dir"
    
    # 设置适当权限
    chmod 644 "$output_path"
    
    # 如果是系统级别的 libvirt，设置 libvirt 用户权限
    if [ -f /etc/libvirt/qemu.conf ] && grep -q "user.*=.*libvirt-qemu" /etc/libvirt/qemu.conf; then
        chown libvirt-qemu:kvm "$output_path" 2>/dev/null || true
    fi
    
    log_success "ISO 镜像已创建: $output_path"
}

# 验证 ISO 内容
verify_iso() {
    local iso_path="$1"
    
    log_info "验证 ISO 镜像内容..."
    
    if ! command -v isoinfo &> /dev/null; then
        log_warning "isoinfo 工具未安装，跳过 ISO 内容验证"
        return 0
    fi
    
    echo "ISO 内容列表:"
    isoinfo -l -i "$iso_path" | grep -E "META_DAT|USER_DAT|NETWORK"
    
    log_success "ISO 镜像验证完成"
}

# 主函数
main() {
    local instance_id="cyris-base-vm"
    local hostname="cyris-base"
    local output_path="$IMAGES_DIR/cloud-init.iso"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--instance-id)
                instance_id="$2"
                shift 2
                ;;
            -h|--hostname)
                hostname="$2"
                shift 2
                ;;
            -o|--output)
                output_path="$2"
                shift 2
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  -i, --instance-id ID    设置实例 ID (默认: cyris-base-vm)"
                echo "  -h, --hostname NAME     设置主机名 (默认: cyris-base)"
                echo "  -o, --output PATH       设置输出路径 (默认: $IMAGES_DIR/cloud-init.iso)"
                echo "      --help              显示此帮助信息"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看使用说明"
                exit 1
                ;;
        esac
    done
    
    log_info "开始创建 Cloud-Init ISO..."
    log_info "实例 ID: $instance_id"
    log_info "主机名: $hostname"
    log_info "输出路径: $output_path"
    
    # 检查依赖
    check_dependencies
    
    # 生成 SSH 密钥对
    ssh_pub_key_path=$(generate_ssh_key)
    
    # 创建临时工作目录
    log_info "创建临时工作目录: $TEMP_DIR"
    
    # 创建配置文件
    create_meta_data "$TEMP_DIR" "$instance_id" "$hostname"
    create_user_data "$TEMP_DIR" "$ssh_pub_key_path"
    create_network_config "$TEMP_DIR"
    
    # 显示文件内容 (调试用)
    echo ""
    log_info "生成的配置文件内容:"
    echo "--- meta-data ---"
    cat "$TEMP_DIR/meta-data"
    echo ""
    echo "--- user-data (前20行) ---"
    head -20 "$TEMP_DIR/user-data"
    echo "..."
    echo ""
    
    # 备份现有 ISO (如果存在)
    if [ -f "$output_path" ]; then
        backup_path="${output_path}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "备份现有 ISO 到: $backup_path"
        cp "$output_path" "$backup_path"
    fi
    
    # 构造 ISO
    create_iso "$TEMP_DIR" "$output_path"
    
    # 验证 ISO
    verify_iso "$output_path"
    
    # 清理临时文件
    log_info "清理临时文件..."
    rm -rf "$TEMP_DIR"
    
    # 显示最终结果
    echo ""
    log_success "Cloud-Init ISO 创建完成!"
    echo ""
    echo "文件信息:"
    ls -la "$output_path"
    echo ""
    echo "使用方法:"
    echo "1. 在 libvirt XML 中添加此 ISO 作为 CD-ROM 设备"
    echo "2. VM 启动时会自动读取并应用配置"
    echo "3. 可通过 SSH 密钥或用户密码登录"
    echo ""
    echo "SSH 密钥位置: $(dirname "$ssh_pub_key_path")"
    echo "私钥: $(dirname "$ssh_pub_key_path")/cyris_rsa"
    echo "公钥: $ssh_pub_key_path"
    echo ""
    echo "测试命令:"
    echo "ssh -i $(dirname "$ssh_pub_key_path")/cyris_rsa ubuntu@<VM_IP>"
}

# 脚本入口点
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi