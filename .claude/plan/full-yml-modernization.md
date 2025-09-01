# Full.yml Modernization - Pure Modern Implementation Plan

## Project Context
**Task**: Make examples/full.yml work with pure modern CyRIS architecture
**Approach**: Solution 2 - Complete modernization, legacy code only as reference
**Goal**: Reproducible pipeline from YAML → VM Creation → Task Execution → Verification

## Target Architecture
```
examples/full.yml → Modern CyRIS Architecture
├── CLI (Click + Rich) → Command Handlers
├── Services Layer → Orchestrator + Task Executor  
├── Infrastructure → KVM Provider + Network Manager
├── Domain Layer → Host/Guest Entities
└── Tools → SSH Manager + User Manager + IP Discovery
```

## Implementation Phases

### Phase 1: Core Infrastructure Foundation
**Files**: 4-5, **Functions**: 8-10

#### Step 1.1: Enhance KVM Provider
- **File**: `src/cyris/infrastructure/providers/kvm_provider.py`
- **Functions**: `create_vm()`, `clone_vm()`, `inject_ssh_keys()`, `get_vm_ip()`
- **Logic**: Complete KVM provider with libvirt integration, VM cloning, cloud-init SSH key injection
- **Expected Result**: Can create, clone, and manage VMs programmatically

#### Step 1.2: Implement Network Topology Manager  
- **File**: `src/cyris/infrastructure/network/topology_manager.py`
- **Functions**: `create_topology()`, `assign_ips()`, `discover_vm_ips()`, `sync_metadata()`
- **Logic**: Bridge creation, IP assignment, DHCP discovery with fallback methods
- **Expected Result**: Network topology creation and reliable IP discovery

#### Step 1.3: Build SSH Connection Manager
- **File**: `src/cyris/tools/ssh_manager.py` 
- **Functions**: `establish_connection()`, `execute_command()`, `verify_connectivity()`
- **Logic**: Robust SSH connections with retry, key-based auth, command execution
- **Expected Result**: Reliable SSH communication to all VMs

### Phase 2: Task Execution Engine
**Files**: 3-4, **Functions**: 12-15

#### Step 2.1: Modern Task Executor
- **File**: `src/cyris/services/task_executor.py`
- **Functions**: `execute_task()`, `verify_task_result()`, `execute_add_account()`, `execute_install_package()`
- **Logic**: Task-specific execution with verification, structured results
- **Expected Result**: All YAML task types execute and verify successfully

#### Step 2.2: Attack Emulation Service
- **File**: `src/cyris/services/attack_emulator.py`
- **Functions**: `emulate_ssh_attack()`, `emulate_malware()`, `generate_traffic_pcap()`
- **Logic**: Attack simulation, traffic generation, malware processes  
- **Expected Result**: Attack emulation tasks work as specified in full.yml

#### Step 2.3: Content & Program Execution Service
- **File**: `src/cyris/services/content_service.py`
- **Functions**: `copy_content()`, `execute_program()`, `setup_firewall_rules()`
- **Logic**: File copying, script execution, firewall configuration
- **Expected Result**: Content tasks and program execution work reliably

### Phase 3: Orchestration Integration
**Files**: 2-3, **Functions**: 6-8

#### Step 3.1: Range Orchestrator Enhancement
- **File**: `src/cyris/services/orchestrator.py`
- **Functions**: `create_range()`, `execute_all_tasks()`, `get_range_status()`  
- **Logic**: Full range lifecycle, task orchestration, status monitoring
- **Expected Result**: Complete range creation from YAML to running VMs

#### Step 3.2: Status Monitoring Service
- **File**: `src/cyris/services/monitoring_service.py`
- **Functions**: `monitor_vm_health()`, `verify_tasks_completed()`, `generate_status_report()`
- **Logic**: Health checking, task verification, comprehensive status reporting
- **Expected Result**: Detailed status display showing actual VM state

### Phase 4: CLI Command Implementation
**Files**: 2-3, **Functions**: 4-6

#### Step 4.1: Create Command Handler
- **File**: `src/cyris/cli/commands/create_command.py`
- **Functions**: `execute()`, `_validate_yaml()`, `_execute_creation()`
- **Logic**: YAML validation, range creation coordination, progress display
- **Expected Result**: `./cyris create examples/full.yml` works end-to-end

#### Step 4.2: Status Command Handler  
- **File**: `src/cyris/cli/commands/status_command.py`
- **Functions**: `execute()`, `_display_range_status()`, `_show_vm_details()`
- **Logic**: Rich-formatted status display, VM health, task completion status
- **Expected Result**: `./cyris status <range_id>` shows comprehensive state

### Phase 5: Verification & Testing
**Files**: 6-8, **Functions**: 15-20

#### Step 5.1: Integration Tests
- **Files**: `tests/integration/test_full_yml_execution.py`, `tests/integration/test_kvm_provider.py`
- **Functions**: End-to-end test suite for full.yml execution
- **Logic**: Complete workflow testing with real VMs
- **Expected Result**: Automated verification that full.yml works correctly

#### Step 5.2: Status Display Verification
- **File**: `tests/e2e/test_status_accuracy.py`
- **Functions**: Status reporting accuracy tests
- **Logic**: Verify displayed status matches actual VM/task state  
- **Expected Result**: Status command shows accurate, real-time information

## Key Technical Decisions

1. **SSH Key Injection**: Use cloud-init ISO generation for KVM (modern approach)
2. **IP Discovery**: Multi-method fallback: `libvirt DHCP → virsh domifaddr → ARP → bridge inspection`
3. **Task Verification**: Each task includes post-execution verification (user exists, package installed, etc.)
4. **Network Isolation**: Dedicated bridges per range: `cr-br-{range_id}-{network_name}`
5. **Error Handling**: Structured exceptions with actionable error messages

## Success Criteria

- ✅ `./cyris create examples/full.yml` completes successfully  
- ✅ All 3 VMs (desktop, webserver, firewall) are created and running
- ✅ All tasks execute and verify (account creation, package installation, attack emulation)
- ✅ `./cyris status <range_id>` shows accurate VM IPs, task results, network topology
- ✅ SSH access works to all VMs with injected keys
- ✅ Network connectivity matches topology (desktop→firewall→webserver)

## Implementation Timeline

- **Phase 1**: Core Infrastructure (Priority 1) 
- **Phase 2**: Task Execution Engine (Priority 1)
- **Phase 3**: Orchestration Integration (Priority 1)
- **Phase 4**: CLI Commands (Priority 2)
- **Phase 5**: Testing & Verification (Priority 2)

Total estimated effort: ~25-30 atomic operations across 18-20 files.