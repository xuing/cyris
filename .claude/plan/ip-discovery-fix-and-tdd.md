# IP Discovery Fix and TDD Implementation Plan

## Context
Fix VM IP assignment issues and implement comprehensive TDD coverage.

## Root Cause Analysis
- VMs created with empty 196KB base images (no bootable OS)
- No DHCP requests due to no operating system
- Need bootable base images for real IP assignment

## Implementation Plan

### Step 1: Automated Base Image Setup
- Add Ubuntu cloud image download automation
- Simple cloud-init configuration for networking
- User-friendly setup with error handling

### Step 2: Simplified IP Discovery
- Single reliable method: libvirt DHCP leases → virsh domifaddr fallback
- Simple error exposure (raw details, no over-engineering)
- Clean, maintainable functions

### Step 3: Comprehensive TDD
- Unit tests: base image setup, IP discovery logic
- Integration tests: real VM IP assignment
- E2E tests: complete workflow validation
- 90%+ test coverage target

### Step 4: CLI Enhancement
- Accurate IP display
- Simple error messages with underlying details
- Clear troubleshooting information

## Expected Results
- VMs get real IP addresses immediately after creation
- Reliable IP discovery with simple error reporting
- Comprehensive test coverage with real VM scenarios
- Clean, maintainable code architecture