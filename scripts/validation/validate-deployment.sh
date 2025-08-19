#!/bin/bash

# 部署验证脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

error() {
    log "ERROR: $1" >&2
    return 1
}

validate_host_environment() {
    log "Validating host environment..."
    
    local errors=0
    
    # 检查操作系统
    if command -v lsb_release &> /dev/null; then
        local os_info
        os_info=$(lsb_release -d | cut -f2)
        log "✓ Operating System: $os_info"
    else
        log "✗ Cannot determine operating system"
        ((errors++))
    fi
    
    # 检查Python
    if command -v python3 &> /dev/null; then
        local python_version
        python_version=$(python3 --version)
        log "✓ Python: $python_version"
    else
        log "✗ Python3 not found"
        ((errors++))
    fi
    
    # 检查虚拟环境支持
    if python3 -m venv --help &> /dev/null; then
        log "✓ Python venv support available"
    else
        log "✗ Python venv support not available"
        ((errors++))
    fi
    
    # 检查KVM支持
    if [[ -c /dev/kvm ]]; then
        log "✓ KVM device available"
    else
        log "✗ KVM device not available"
        ((errors++))
    fi
    
    # 检查libvirt
    if systemctl is-active --quiet libvirtd; then
        log "✓ libvirtd service is running"
    else
        log "✗ libvirtd service is not running"
        ((errors++))
    fi
    
    # 检查网络工具
    if command -v brctl &> /dev/null; then
        log "✓ Bridge utilities available"
    else
        log "✗ Bridge utilities not available"
        ((errors++))
    fi
    
    # 检查virsh
    if command -v virsh &> /dev/null; then
        if timeout 5 virsh list &> /dev/null; then
            log "✓ virsh command working"
        else
            log "✗ virsh command not working properly"
            ((errors++))
        fi
    else
        log "✗ virsh command not available"
        ((errors++))
    fi
    
    return $errors
}

validate_python_environment() {
    log "Validating Python environment..."
    
    local errors=0
    local venv_path="$PROJECT_ROOT/.venv"
    
    # 检查虚拟环境
    if [[ -d "$venv_path" ]]; then
        log "✓ Virtual environment exists"
    else
        log "✗ Virtual environment not found at $venv_path"
        ((errors++))
        return $errors
    fi
    
    # 激活虚拟环境并检查
    if [[ -f "$venv_path/bin/activate" ]]; then
        source "$venv_path/bin/activate"
        
        # 检查Python版本
        local python_version
        python_version=$(python --version)
        log "✓ Virtual environment Python: $python_version"
        
        # 检查关键包
        local packages=(
            "pytest:pytest"
            "pydantic:pydantic"
            "yaml:PyYAML"
            "boto3:boto3"
            "paramiko:paramiko"
            "structlog:structlog"
            "click:click"
        )
        
        for package_info in "${packages[@]}"; do
            local import_name="${package_info%:*}"
            local package_name="${package_info#*:}"
            
            if python -c "import $import_name" 2>/dev/null; then
                local version
                version=$(python -c "import $import_name; print(getattr($import_name, '__version__', 'unknown'))" 2>/dev/null || echo "unknown")
                log "✓ $package_name: $version"
            else
                log "✗ $package_name: not available"
                ((errors++))
            fi
        done
        
        deactivate
    else
        log "✗ Virtual environment activation script not found"
        ((errors++))
    fi
    
    return $errors
}

validate_project_structure() {
    log "Validating project structure..."
    
    local errors=0
    
    # 检查重要目录
    local directories=(
        "src/cyris"
        "tests/unit"
        "tests/integration"
        "scripts/setup"
        "scripts/validation"
        "main"
        "examples"
    )
    
    for dir in "${directories[@]}"; do
        if [[ -d "$PROJECT_ROOT/$dir" ]]; then
            log "✓ Directory exists: $dir"
        else
            log "✗ Directory missing: $dir"
            ((errors++))
        fi
    done
    
    # 检查重要文件
    local files=(
        "README.md"
        "CLAUDE.md"
        "pyproject.toml" 
        "main/cyris.py"
        "CONFIG"
        "examples/basic.yml"
    )
    
    for file in "${files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            log "✓ File exists: $file"
        else
            log "✗ File missing: $file"
            ((errors++))
        fi
    done
    
    return $errors
}

run_unit_tests() {
    log "Running unit tests..."
    
    local venv_path="$PROJECT_ROOT/.venv"
    
    if [[ ! -d "$venv_path" ]]; then
        error "Virtual environment not found"
        return 1
    fi
    
    source "$venv_path/bin/activate"
    
    # 运行现代化模块的测试
    if python -m pytest tests/unit/test_config_parser.py tests/unit/test_domain_entities.py -v --tb=short; then
        log "✓ Modern unit tests passed"
    else
        log "✗ Modern unit tests failed"
        deactivate
        return 1
    fi
    
    # 运行简单测试验证原始模块
    if python simple_test.py; then
        log "✓ Legacy compatibility tests passed"
    else
        log "✗ Legacy compatibility tests failed"
        deactivate
        return 1
    fi
    
    deactivate
    return 0
}

validate_configuration() {
    log "Validating configuration files..."
    
    local errors=0
    
    # 检查CONFIG文件
    if [[ -f "$PROJECT_ROOT/CONFIG" ]]; then
        if grep -q "\[config\]" "$PROJECT_ROOT/CONFIG"; then
            log "✓ CONFIG file has correct format"
        else
            log "✗ CONFIG file format appears invalid"
            ((errors++))
        fi
    else
        log "✗ CONFIG file not found"
        ((errors++))
    fi
    
    # 检查示例YAML文件
    if [[ -f "$PROJECT_ROOT/examples/basic.yml" ]]; then
        local venv_path="$PROJECT_ROOT/.venv"
        if [[ -d "$venv_path" ]]; then
            source "$venv_path/bin/activate"
            if python -c "import yaml; yaml.safe_load(open('examples/basic.yml'))" 2>/dev/null; then
                log "✓ Example YAML file is valid"
            else
                log "✗ Example YAML file is invalid"
                ((errors++))
            fi
            deactivate
        fi
    else
        log "✗ Example YAML file not found"
        ((errors++))
    fi
    
    return $errors
}

generate_validation_report() {
    local total_errors=$1
    
    log "Generating validation report..."
    
    local report_file="$PROJECT_ROOT/validation-report.txt"
    
    cat > "$report_file" << EOF
CyRIS 部署验证报告
================
生成时间: $(date)
项目根目录: $PROJECT_ROOT

EOF
    
    if [[ $total_errors -eq 0 ]]; then
        cat >> "$report_file" << EOF
✅ 验证状态: 通过
所有验证检查都已成功通过。

EOF
    else
        cat >> "$report_file" << EOF
❌ 验证状态: 失败
发现 $total_errors 个问题需要解决。

EOF
    fi
    
    cat >> "$report_file" << EOF
验证项目:
- 主机环境检查
- Python环境检查
- 项目结构检查
- 配置文件检查
- 单元测试运行

详细信息请查看控制台输出。
EOF
    
    log "Validation report saved: $report_file"
}

main() {
    log "Starting CyRIS deployment validation..."
    log "Project root: $PROJECT_ROOT"
    
    local total_errors=0
    
    # 运行各项验证
    validate_host_environment || total_errors=$((total_errors + $?))
    validate_python_environment || total_errors=$((total_errors + $?))
    validate_project_structure || total_errors=$((total_errors + $?))
    validate_configuration || total_errors=$((total_errors + $?))
    run_unit_tests || total_errors=$((total_errors + 1))
    
    # 生成报告
    generate_validation_report $total_errors
    
    log ""
    log "==================== 验证摘要 ===================="
    
    if [[ $total_errors -eq 0 ]]; then
        log "🎉 所有验证检查通过！CyRIS部署验证成功"
        log ""
        log "系统已准备就绪，可以使用以下命令运行CyRIS:"
        log "  source .venv/bin/activate"
        log "  python main/cyris.py examples/basic.yml CONFIG"
        return 0
    else
        log "❌ 验证失败，发现 $total_errors 个问题"
        log "请解决上述问题后重新运行验证"
        return 1
    fi
}

# 只有在直接运行脚本时才执行main函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi