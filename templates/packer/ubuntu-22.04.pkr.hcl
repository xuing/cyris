# Ubuntu 22.04 LTS Server Packer Template
# Automated image building with cloud-init and SSH key injection

packer {
  required_plugins {
    qemu = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "ssh_keys" {
  type        = list(string)
  description = "SSH public keys to inject"
  default     = []
}

variable "output_formats" {
  type        = list(string)
  description = "Output image formats"
  default     = ["qcow2"]
}

variable "vm_name" {
  type        = string
  description = "VM name for output"
  default     = "ubuntu-22.04"
}

source "qemu" "ubuntu" {
  # ISO Configuration
  iso_url      = "https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
  iso_checksum = "sha256:a4acfda10b18da50e2ec50ccaf860d7f20b389df8765611142305c0e911d16fd"
  
  # Output Configuration
  output_directory = "output-ubuntu-22.04"
  vm_name          = "${var.vm_name}.qcow2"
  format           = "qcow2"
  
  # Hardware Configuration
  accelerator = "kvm"
  memory      = 2048
  cpus        = 2
  disk_size   = "20G"
  
  # Network Configuration
  net_device = "virtio-net"
  
  # SSH Configuration
  ssh_username = "ubuntu"
  ssh_password = "ubuntu"
  ssh_timeout = "20m"
  
  # Boot Configuration - Ubuntu 22.04 autoinstall
  boot_command = [
    "<spacebar><wait><spacebar><wait><spacebar><wait><spacebar><wait><spacebar><wait>",
    "e<wait>",
    "<down><down><down><end>",
    " autoinstall ds=nocloud-net\\;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/",
    "<f10><wait>"
  ]
  
  # HTTP server for autoinstall
  http_directory    = "templates/packer/http"
  http_bind_address = "0.0.0.0"
  http_port_min     = 8000
  http_port_max     = 8100
  
  # VM Configuration
  headless         = true
  use_default_display = true
  vnc_bind_address = "127.0.0.1"
  
  # Shutdown
  shutdown_command = "echo 'ubuntu' | sudo -S shutdown -P now"
}

build {
  sources = ["source.qemu.ubuntu"]
  
  # Wait for system to be ready
  provisioner "shell" {
    inline = [
      "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for cloud-init...'; sleep 1; done"
    ]
  }
  
  # Basic system setup
  provisioner "shell" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y qemu-guest-agent cloud-init",
      "sudo systemctl enable qemu-guest-agent",
      "sudo systemctl enable cloud-init"
    ]
  }
  
  # SSH key injection
  provisioner "shell" {
    inline = [
      "mkdir -p /home/ubuntu/.ssh",
      "chmod 700 /home/ubuntu/.ssh",
      "touch /home/ubuntu/.ssh/authorized_keys",
      "chmod 600 /home/ubuntu/.ssh/authorized_keys",
      "chown -R ubuntu:ubuntu /home/ubuntu/.ssh"
    ]
    only = ["qemu.ubuntu"]
  }
  
  # Inject SSH keys if provided
  provisioner "shell" {
    inline = [
      "echo '${join("\\n", var.ssh_keys)}' >> /home/ubuntu/.ssh/authorized_keys"
    ]
    only = ["qemu.ubuntu"]
    execute_command = "sudo sh -c '{{ .Vars }} {{ .Path }}'"
  }
  
  # Clean up
  provisioner "shell" {
    inline = [
      "sudo apt-get autoremove -y",
      "sudo apt-get autoclean",
      "sudo cloud-init clean",
      "sudo rm -rf /var/lib/cloud/instances/*",
      "sudo rm -rf /tmp/*",
      "sudo rm -rf /var/tmp/*",
      "history -c"
    ]
  }
  
  # Convert to additional formats if requested
  post-processor "shell-local" {
    inline = [
      "for fmt in ${join(" ", var.output_formats)}; do",
      "  if [ \"$fmt\" != \"qcow2\" ]; then",
      "    echo \"Converting to $fmt format...\"",
      "    qemu-img convert -f qcow2 -O $fmt output-ubuntu-22.04/${var.vm_name}.qcow2 output-ubuntu-22.04/${var.vm_name}.$fmt",
      "  fi",
      "done"
    ]
  }
}