#!/bin/bash

# Python环境设置脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

error() {
    log "ERROR: $1" >&2
    exit 1
}

check_python() {
    log "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        error "Python3 is not installed. Please run 01-prepare-host.sh first."
    fi
    
    local python_version
    python_version=$(python3 --version 2>&1)
    log "Found: $python_version"
    
    # 检查venv支持
    if ! python3 -m venv --help &> /dev/null; then
        error "Python venv module is not available. Please install python3-venv package."
    fi
    
    log "Python environment check passed"
}

create_virtual_environment() {
    log "Setting up Python virtual environment..."
    
    if [[ -d "$VENV_PATH" ]]; then
        log "Virtual environment already exists at: $VENV_PATH"
        log "Removing existing environment to ensure clean setup..."
        rm -rf "$VENV_PATH"
    fi
    
    log "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    
    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        error "Failed to create virtual environment"
    fi
    
    log "Virtual environment created successfully"
}

install_dependencies() {
    log "Installing Python dependencies..."
    
    # 激活虚拟环境
    source "$VENV_PATH/bin/activate"
    
    # 升级pip
    log "Upgrading pip..."
    pip install --upgrade pip
    
    # 安装核心依赖
    log "Installing core dependencies..."
    pip install \
        "pytest>=7.0.0" \
        "pytest-cov>=4.0.0" \
        "pytest-mock>=3.10.0" \
        "pydantic>=2.0.0" \
        "pydantic-settings>=2.0.0" \
        "pyyaml>=6.0.0" \
        "boto3>=1.34.0" \
        "paramiko>=3.0.0" \
        "psutil>=5.9.0" \
        "structlog>=23.0.0" \
        "click>=8.0.0"
    
    # 安装开发依赖
    log "Installing development dependencies..."
    pip install \
        "black>=23.0.0" \
        "flake8>=6.0.0" \
        "mypy>=1.0.0" \
        "pre-commit>=3.0.0"
    
    log "Dependencies installed successfully"
}

generate_requirements() {
    log "Generating requirements.txt..."
    
    source "$VENV_PATH/bin/activate"
    pip freeze > "$PROJECT_ROOT/requirements.txt"
    
    log "Requirements file generated: $PROJECT_ROOT/requirements.txt"
}

verify_installation() {
    log "Verifying Python environment..."
    
    source "$VENV_PATH/bin/activate"
    
    # 检查Python版本
    local python_version
    python_version=$(python --version 2>&1)
    log "✓ Virtual environment Python: $python_version"
    
    # 检查关键包
    local packages=(
        "pytest"
        "pydantic"
        "yaml"
        "boto3" 
        "paramiko"
        "structlog"
        "click"
    )
    
    for package in "${packages[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            local version
            version=$(python -c "import $package; print($package.__version__)" 2>/dev/null || echo "unknown")
            log "✓ $package: $version"
        else
            log "✗ $package: not available"
        fi
    done
    
    # 测试pytest
    if python -m pytest --version &> /dev/null; then
        log "✓ pytest is working"
    else
        log "✗ pytest is not working"
    fi
    
    log "Python environment verification completed"
}

create_activation_script() {
    log "Creating activation helper script..."
    
    local activate_script="$PROJECT_ROOT/activate-env.sh"
    
    cat > "$activate_script" << 'EOF'
#!/bin/bash
# CyRIS虚拟环境激活脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${SCRIPT_DIR}/.venv"

if [[ -f "$VENV_PATH/bin/activate" ]]; then
    echo "激活CyRIS虚拟环境..."
    source "$VENV_PATH/bin/activate"
    echo "✓ 虚拟环境已激活"
    echo "当前Python: $(which python)"
    echo "要退出虚拟环境，输入: deactivate"
else
    echo "错误: 虚拟环境不存在于 $VENV_PATH"
    echo "请先运行: scripts/setup/02-setup-python-env.sh"
    exit 1
fi
EOF
    
    chmod +x "$activate_script"
    log "Activation script created: $activate_script"
}

main() {
    log "Starting Python environment setup..."
    log "Project root: $PROJECT_ROOT"
    log "Virtual environment path: $VENV_PATH"
    
    # 执行步骤
    check_python
    create_virtual_environment
    install_dependencies
    generate_requirements
    verify_installation
    create_activation_script
    
    log "🎉 Python environment setup completed successfully!"
    log ""
    log "To activate the environment, run:"
    log "  source .venv/bin/activate"
    log "Or use the helper script:"
    log "  source activate-env.sh"
    log ""
    log "To run tests:"
    log "  source .venv/bin/activate"
    log "  python -m pytest tests/unit/ -v"
}

# 只有在直接运行脚本时才执行main函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi