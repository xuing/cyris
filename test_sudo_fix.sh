#!/bin/bash

echo "=== 测试 Sudo 修复效果 ==="
echo "这个脚本需要在真正的交互终端中运行"
echo ""

# 激活虚拟环境
source .venv/bin/activate

echo "1. 🔐 清除并重新认证 sudo（会提示输入密码）："
sudo -k
sudo -v

if [ $? -eq 0 ]; then
    echo "✅ Sudo 认证成功"
    
    echo ""
    echo "2. 🧪 测试修复后的命令："
    
    echo "测试 virt-builder --help："
    timeout 10 sudo virt-builder --help >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ virt-builder --help 成功"
    else
        echo "❌ virt-builder --help 失败"
    fi
    
    echo ""
    echo "3. 🚀 运行修复后的 cyris 创建命令："
    echo "执行: ./cyris create test-kvm-auto-debian.yml"
    echo "注意观察是否不再出现 'sudo: a password is required' 错误"
    
    # 运行实际的 cyris 命令
    ./cyris create test-kvm-auto-debian.yml
    
else
    echo "❌ Sudo 认证失败，无法继续测试"
fi

echo ""
echo "=== 测试完成 ==="