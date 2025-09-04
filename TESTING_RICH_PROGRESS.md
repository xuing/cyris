# Testing Rich Progress System

This document describes how to test the enhanced Rich progress system for CyRIS KVM auto workflow.

## Test Scripts

### 1. Rich Progress Test Script (`test_rich_progress.py`)

Tests the Rich progress manager functionality in isolation.

**Usage:**
```bash
# Test all components
./test_rich_progress.py

# Test specific components
./test_rich_progress.py --test basic      # Basic progress manager
./test_rich_progress.py --test image      # Image builder progress
./test_rich_progress.py --test kvm        # KVM provider progress  
./test_rich_progress.py --test e2e        # End-to-end simulation
./test_rich_progress.py --test errors     # Error scenarios

# Interactive mode (waits for user input between tests)
./test_rich_progress.py --interactive
```

### 2. KVM Auto Workflow Test Script (`test_kvm_auto_workflow.py`)

Tests the complete KVM auto workflow with real system integration.

**Usage:**
```bash
# Test all components
./test_kvm_auto_workflow.py

# Test specific components
./test_kvm_auto_workflow.py --test prereq      # Check prerequisites
./test_kvm_auto_workflow.py --test yaml        # Validate YAML config
./test_kvm_auto_workflow.py --test dry-run     # Test dry run mode
./test_kvm_auto_workflow.py --test pre-checks  # Test pre-creation checks
./test_kvm_auto_workflow.py --test images      # Check available images
./test_kvm_auto_workflow.py --test rich        # Test Rich output
./test_kvm_auto_workflow.py --test simulate    # Simulate workflow

# Continue even if tests fail
./test_kvm_auto_workflow.py --continue-on-failure
```

## Manual Testing

### Quick Test
```bash
# 1. Test Rich progress display
./test_rich_progress.py --test e2e

# 2. Test with real configuration (dry run)
./cyris create test-kvm-auto-ubuntu.yml --dry-run

# 3. Check prerequisites
./test_kvm_auto_workflow.py --test prereq
```

### Full Workflow Test
```bash
# 1. Validate configuration
./cyris validate test-kvm-auto-ubuntu.yml

# 2. Run pre-checks (will show Rich progress)
./cyris create test-kvm-auto-ubuntu.yml
# (Cancel after seeing pre-checks complete)

# 3. Test dry run with Rich progress
./cyris create test-kvm-auto-ubuntu.yml --dry-run
```

### Real VM Creation (if environment supports it)
```bash
# Only run if you have:
# - libvirt configured
# - virt-builder, virt-install, virt-customize installed
# - Sufficient disk space

./cyris create test-kvm-auto-ubuntu.yml
```

## Expected Rich Progress Features

The enhanced system should display:

### ✅ Pre-Creation Checks
- Configuration parsing with details
- Dependency checking (virt-builder, etc.)
- Base image validation
- Network connectivity tests
- Live progress bars and status updates

### ✅ Image Building Phase
- Real-time virt-builder progress
- Command logging
- Progress bars for long operations
- Success/failure feedback with colors

### ✅ VM Creation Phase
- Step-by-step VM creation progress
- Resource allocation feedback
- Network configuration status
- Post-creation validation

### ✅ Error Handling
- Clear error messages with colors
- Helpful suggestions for fixes
- Graceful failure handling
- Recovery recommendations

## Progress Display Features

### Visual Elements
- **Progress Bars**: Show completion percentage
- **Status Spinners**: Indicate ongoing work
- **Live Logs**: Command output above progress
- **Color Coding**: Green (success), Yellow (warning), Red (error)
- **Nested Progress**: Overall → Phase → Step hierarchy

### Information Display
- **Time Estimates**: Remaining time for operations
- **Resource Usage**: Memory, disk space, etc.
- **Command Logging**: Actual commands being executed
- **Status Updates**: Current operation and progress

## Troubleshooting

### If tests fail:

1. **Permission Issues**
   ```bash
   # Check libvirt group membership
   groups
   # Should include 'libvirt' group
   ```

2. **Missing Dependencies**
   ```bash
   # Install required tools
   sudo apt update
   sudo apt install libguestfs-tools virtinst qemu-kvm
   ```

3. **Rich Display Issues**
   ```bash
   # Test terminal compatibility
   python3 -c "from rich.console import Console; Console().print('[bold green]Rich works![/bold green]')"
   ```

4. **Configuration Issues**
   ```bash
   # Validate YAML syntax
   python3 -c "import yaml; yaml.safe_load(open('test-kvm-auto-ubuntu.yml'))"
   ```

## Success Criteria

A successful test should show:
- ✅ All progress bars render correctly
- ✅ Colors and formatting work properly
- ✅ Real-time updates during operations
- ✅ Clear error messages with suggestions
- ✅ Professional terminal UI experience
- ✅ No crashes or exceptions during display

The Rich progress system significantly improves the user experience by providing:
- Clear visibility into current operations
- Professional terminal interface
- Real-time feedback during long operations
- Better error handling and user guidance