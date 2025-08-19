#!/bin/bash

# CyRIS 现代化部署主脚本
# 一键部署整个系统

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    log "ERROR: $1" >&2
    exit 1
}

usage() {
    cat << EOF
CyRIS 现代化部署脚本

用法: $0 [选项]

选项:
    -h, --help              显示此帮助信息
    -v, --validate-only     仅运行验证，不执行部署
    -s, --skip-host-prep   跳过主机准备步骤
    -p, --python-only      仅设置Python环境
    -t, --test-only        仅运行测试验证
    --dry-run              显示将要执行的步骤但不实际运行

示例:
    $0                     # 完整部署
    $0 --validate-only     # 仅验证现有部署
    $0 --python-only       # 仅设置Python环境
    $0 --dry-run           # 查看部署步骤
EOF
}

check_requirements() {
    log "Checking system requirements..."
    
    # 检查是否为Ubuntu
    if ! command -v lsb_release &> /dev/null; then
        error "This script is designed for Ubuntu systems"
    fi
    
    local ubuntu_version
    ubuntu_version=$(lsb_release -rs)
    log "Detected Ubuntu $ubuntu_version"
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        log "Python3 not found - will be installed during host preparation"
    fi
    
    log "System requirements check completed"
}

run_host_preparation() {
    log "Running host preparation..."
    
    if [[ $EUID -ne 0 ]]; then
        log "Host preparation requires root privileges"
        if command -v sudo &> /dev/null; then
            log "Running with sudo..."
            sudo "$SCRIPT_DIR/scripts/setup/01-prepare-host.sh"
        else
            error "sudo not available. Please run as root: sudo $0"
        fi
    else
        "$SCRIPT_DIR/scripts/setup/01-prepare-host.sh"
    fi
    
    log "Host preparation completed"
}

run_python_setup() {
    log "Setting up Python environment..."
    
    "$SCRIPT_DIR/scripts/setup/02-setup-python-env.sh"
    
    log "Python environment setup completed"
}

run_validation() {
    log "Running deployment validation..."
    
    if "$SCRIPT_DIR/scripts/validation/validate-deployment.sh"; then
        log "✓ Validation passed"
        return 0
    else
        log "✗ Validation failed"
        return 1
    fi
}

show_deployment_steps() {
    log "CyRIS 部署步骤预览:"
    log "=================="
    log "1. 系统要求检查"
    log "2. 主机环境准备 (需要root权限)"
    log "   - 安装系统包 (KVM, libvirt, Python等)"
    log "   - 配置虚拟化环境"
    log "   - 设置用户权限"
    log "3. Python环境设置"
    log "   - 创建虚拟环境"
    log "   - 安装Python依赖"
    log "   - 生成requirements.txt"
    log "4. 部署验证"
    log "   - 环境检查"
    log "   - 运行单元测试"
    log "   - 生成验证报告"
    log ""
}

main() {
    # 解析命令行参数
    local validate_only=false
    local skip_host_prep=false
    local python_only=false
    local test_only=false
    local dry_run=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--validate-only)
                validate_only=true
                shift
                ;;
            -s|--skip-host-prep)
                skip_host_prep=true
                shift
                ;;
            -p|--python-only)
                python_only=true
                shift
                ;;
            -t|--test-only)
                test_only=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done
    
    log "🚀 CyRIS 现代化部署开始"
    log "项目目录: $SCRIPT_DIR"
    
    if [[ "$dry_run" == true ]]; then
        show_deployment_steps
        return 0
    fi
    
    # 验证模式
    if [[ "$validate_only" == true ]]; then
        if run_validation; then
            log "🎉 验证成功！系统已正确部署"
            return 0
        else
            log "❌ 验证失败，请检查部署"
            return 1
        fi
    fi
    
    # 仅测试模式
    if [[ "$test_only" == true ]]; then
        log "Running tests only..."
        source "$SCRIPT_DIR/.venv/bin/activate" 2>/dev/null || error "Virtual environment not found. Run full deployment first."
        
        if python -m pytest tests/unit/ -v; then
            log "✓ Tests passed"
        else
            log "✗ Tests failed"
            return 1
        fi
        return 0
    fi
    
    # 系统要求检查
    check_requirements
    
    # 主机准备
    if [[ "$skip_host_prep" == false && "$python_only" == false ]]; then
        run_host_preparation
    else
        log "Skipping host preparation"
    fi
    
    # Python环境设置
    run_python_setup
    
    # 如果只是Python环境设置，跳过验证
    if [[ "$python_only" == true ]]; then
        log "✓ Python environment setup completed"
        log ""
        log "To activate the environment:"
        log "  source .venv/bin/activate"
        log ""
        log "To run tests:"
        log "  source .venv/bin/activate"
        log "  python -m pytest tests/unit/ -v"
        return 0
    fi
    
    # 部署验证
    if run_validation; then
        log ""
        log "🎉 CyRIS 现代化部署成功完成！"
        log ""
        log "系统已准备就绪。使用以下命令:"
        log ""
        log "激活环境:"
        log "  source .venv/bin/activate"
        log ""
        log "运行测试:"
        log "  python -m pytest tests/unit/ -v"
        log ""
        log "运行原始CyRIS:"
        log "  python main/cyris.py examples/basic.yml CONFIG"
        log ""
        log "查看现代化文档:"
        log "  cat MODERNIZATION_DESIGN.md"
        log ""
        return 0
    else
        log "❌ 部署验证失败，请检查错误信息"
        return 1
    fi
}

# 只有在直接运行脚本时才执行main函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi