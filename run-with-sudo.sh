#!/bin/bash
# Simple wrapper to authenticate sudo and then run cyris commands
# Usage: ./run-with-sudo.sh create test-kvm-auto.yml

set -e

echo "🔐 CyRIS Sudo Authentication Helper"
echo "=================================="
echo "This script will authenticate sudo for virt-builder commands."
echo "You will be prompted for your password once."
echo ""

# Authenticate sudo and keep it cached
echo "🔑 Authenticating sudo..."
sudo -v

if [ $? -eq 0 ]; then
    echo "✅ Sudo authentication successful!"
    echo ""
    echo "🚀 Running cyris command..."
    source .venv/bin/activate
    ./cyris "$@"
else
    echo "❌ Sudo authentication failed!"
    echo "Please check your password and try again."
    exit 1
fi