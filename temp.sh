#!/usr/bin/env bash
# Ubuntu 24.04.3 install via JAIST ISO using --location
set -Eeuo pipefail

NAME="u24-jaist"
RAM=4096
VCPUS=2
DISK="$HOME/cyris/images/${NAME}.qcow2"
ISO_URL="http://ftp.jaist.ac.jp/pub/Linux/ubuntu-releases/noble/ubuntu-24.04.3-live-server-amd64.iso"
ISO="$HOME/cyris/images/$(basename "$ISO_URL")"

mkdir -p "$(dirname "$DISK")"
qemu-img create -f qcow2 "$DISK" 20G

# Download ISO if missing
[[ -f "$ISO" ]] || curl -fL --retry 5 --retry-delay 2 --continue-at - -o "$ISO" "$ISO_URL"

# Try install via --location
virt-install \
  --name "$NAME" \
  --memory "$RAM" \
  --vcpus "$VCPUS" \
  --disk "path=$DISK,format=qcow2,bus=virtio" \
  --os-variant detect=on \
  --network network=default,model=virtio \
  --graphics vnc,listen=127.0.0.1 \
  --location "$ISO" \
  --extra-args "console=ttyS0,115200 ---"

