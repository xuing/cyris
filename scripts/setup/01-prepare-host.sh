#!/bin/bash

# 现代化主机准备脚本
# 兼容Ubuntu 24.04 LTS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

error() {
    log "ERROR: $1" >&2
    exit 1
}

check_ubuntu() {
    if ! command -v lsb_release &> /dev/null; then
        error "lsb_release not found. This script is designed for Ubuntu systems."
    fi
    
    local ubuntu_version
    ubuntu_version=$(lsb_release -rs)
    log "Detected Ubuntu version: $ubuntu_version"
    
    # 检查是否为支持的Ubuntu版本
    case "$ubuntu_version" in
        20.04|22.04|24.04)
            log "Ubuntu version $ubuntu_version is supported"
            ;;
        *)
            log "WARNING: Ubuntu version $ubuntu_version may not be fully supported"
            ;;
    esac
}

install_system_packages() {
    log "Updating package list..."
    apt update
    
    log "Installing system packages..."
    
    # 基础包
    local packages=(
        # Python开发环境
        "python3-full"
        "python3-pip"
        "python3-venv"
        "python3-dev"
        
        # 虚拟化支持
        "qemu-kvm"
        "libvirt-daemon-system"
        "libvirt-clients"
        "bridge-utils" 
        "virt-manager"
        
        # 网络工具
        "tcpreplay"
        "wireshark-common"
        "sshpass"
        "pssh"
        
        # 邮件工具
        "sendemail"
        
        # 系统工具
        "curl"
        "wget"
        "git"
        "htop"
        "tree"
    )
    
    # Ubuntu 24.04 特定调整
    local ubuntu_version
    ubuntu_version=$(lsb_release -rs)
    
    if [[ "$ubuntu_version" == "24.04" ]]; then
        # Ubuntu 24.04 可能需要的额外包或替代包
        packages+=("python3.12-venv")
    fi
    
    # 安装包
    apt install -y "${packages[@]}"
    
    log "System packages installed successfully"
}

setup_libvirt() {
    log "Setting up libvirt..."
    
    # 启动并启用libvirtd服务
    systemctl enable libvirtd
    systemctl start libvirtd
    
    # 检查服务状态
    if systemctl is-active --quiet libvirtd; then
        log "libvirtd service is running"
    else
        error "Failed to start libvirtd service"
    fi
    
    # 添加当前用户到libvirt组
    local current_user="${SUDO_USER:-$USER}"
    if [[ -n "$current_user" && "$current_user" != "root" ]]; then
        usermod -a -G libvirt "$current_user"
        log "Added user '$current_user' to libvirt group"
        log "NOTE: User needs to logout and login again for group changes to take effect"
    fi
}

setup_kvm() {
    log "Setting up KVM..."
    
    # 检查CPU虚拟化支持
    if [[ -r /proc/cpuinfo ]] && grep -q -E "vmx|svm" /proc/cpuinfo; then
        log "CPU virtualization support detected"
    else
        log "WARNING: CPU virtualization support may not be available"
    fi
    
    # 检查KVM模块
    if lsmod | grep -q kvm; then
        log "KVM modules are loaded"
    else
        log "Loading KVM modules..."
        modprobe kvm
        modprobe kvm_intel || modprobe kvm_amd || log "WARNING: Could not load KVM modules"
    fi
    
    # 设置KVM设备权限
    if [[ -c /dev/kvm ]]; then
        chmod 666 /dev/kvm || log "WARNING: Could not set KVM device permissions"
        log "KVM device permissions set"
    else
        log "WARNING: /dev/kvm device not found"
    fi
}

verify_installation() {
    log "Verifying installation..."
    
    # 检查Python
    if command -v python3 &> /dev/null; then
        local python_version
        python_version=$(python3 --version)
        log "✓ Python: $python_version"
    else
        error "✗ Python3 not found"
    fi
    
    # 检查虚拟环境支持
    if python3 -m venv --help &> /dev/null; then
        log "✓ Python venv support available"
    else
        error "✗ Python venv support not available"
    fi
    
    # 检查libvirt
    if systemctl is-active --quiet libvirtd; then
        log "✓ libvirtd service is running"
    else
        log "✗ libvirtd service is not running"
    fi
    
    # 检查virsh
    if command -v virsh &> /dev/null; then
        log "✓ virsh command available"
    else
        log "✗ virsh command not available"
    fi
    
    # 检查网络工具
    if command -v brctl &> /dev/null; then
        log "✓ Bridge utilities available"
    else
        log "✗ Bridge utilities not available"
    fi
    
    log "Host preparation verification completed"
}

main() {
    log "Starting CyRIS host preparation..."
    log "Project root: $PROJECT_ROOT"
    
    # 检查是否以root权限运行
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root. Use: sudo $0"
    fi
    
    # 执行步骤
    check_ubuntu
    install_system_packages
    setup_libvirt
    setup_kvm
    verify_installation
    
    log "🎉 Host preparation completed successfully!"
    log ""
    log "Next steps:"
    log "1. Logout and login again to apply group changes"
    log "2. Run: python3 -m venv .venv"
    log "3. Run: source .venv/bin/activate"
    log "4. Run: pip install -r requirements.txt"
}

# 只有在直接运行脚本时才执行main函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi