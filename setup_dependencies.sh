#!/bin/bash
# CyRIS 依赖安装脚本
# 解决虚拟环境中的依赖问题

set -e

echo "🔧 CyRIS 依赖安装脚本"
echo "==================="

# 检查是否在虚拟环境中
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ 请先激活虚拟环境："
    echo "   source .venv/bin/activate"
    exit 1
fi

echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"

# 升级 pip
echo "📦 升级 pip..."
pip install --upgrade pip

# 安装核心依赖
echo "📦 安装核心依赖..."
pip install paramiko>=4.0.0
pip install psutil>=7.0.0
pip install pydantic>=2.11.0
pip install pydantic-settings>=2.10.0
pip install click>=8.2.0
pip install rich>=14.1.0
pip install PyYAML>=6.0.0
pip install structlog>=25.0.0

# 安装可选依赖
echo "📦 安装可选依赖..."
pip install cryptography>=45.0.0
pip install boto3>=1.40.0 || echo "⚠️  boto3 安装失败 (AWS 功能可能不可用)"

# 安装开发依赖
echo "📦 安装开发依赖..."
pip install pytest>=8.4.0 || echo "⚠️  pytest 安装失败 (测试功能可能不可用)"
pip install black>=25.0.0 || echo "⚠️  black 安装失败 (代码格式化功能可能不可用)"

# 验证安装
echo "🧪 验证关键依赖..."

python3 -c "import paramiko; print('✅ paramiko:', paramiko.__version__)" || echo "❌ paramiko 导入失败"
python3 -c "import psutil; print('✅ psutil:', psutil.__version__)" || echo "❌ psutil 导入失败"
python3 -c "import pydantic; print('✅ pydantic:', pydantic.__version__)" || echo "❌ pydantic 导入失败"
python3 -c "import click; print('✅ click:', click.__version__)" || echo "❌ click 导入失败"
python3 -c "import rich; print('✅ rich:', rich.__version__)" || echo "❌ rich 导入失败"

# 测试 CyRIS 导入
echo "🧪 测试 CyRIS 模块导入..."
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from cyris.config.parser import ConfigurationError
    print('✅ ConfigurationError 导入成功')
except Exception as e:
    print(f'❌ ConfigurationError 导入失败: {e}')

try:
    from cyris.cli.main import main
    print('✅ CLI main 导入成功')
except Exception as e:
    print(f'❌ CLI main 导入失败: {e}')
"

echo ""
echo "🎉 依赖安装完成！"
echo "📋 现在可以运行："
echo "   ./cyris list"
echo "   ./cyris validate" 
echo "   ./cyris create test-kvm-auto.yml --dry-run"