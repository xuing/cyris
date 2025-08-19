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
