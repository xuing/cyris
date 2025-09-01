# LibVirt-Python Migration Plan

## Project Context
Complete migration from virsh subprocess commands to native libvirt-python API across CyRIS codebase (excluding legacy/ folder).

## Implementation Strategy: Solution 2 - Direct API Replacement
- **Timeline**: 15 days
- **Approach**: TDD-first with comprehensive testing
- **Scope**: Modern CyRIS modules only (no legacy/ changes)

## Execution Plan

### Phase 1: Foundation & Testing Framework (Days 1-3)
- [x] LibvirtConnectionManager - Centralized connection pooling
- [ ] LibvirtDomainWrapper - Enhanced domain operations  
- [ ] Comprehensive test suite setup

### Phase 2: Core Module Migration (Days 4-8)
- [ ] vm_ip_manager.py complete rewrite
- [ ] vm_diagnostics.py enhancement
- [ ] virsh_client.py → libvirt_provider.py

### Phase 3: Infrastructure Integration (Days 9-12)
- [ ] Network topology manager migration
- [ ] Services layer integration (orchestrator.py, range_discovery.py)
- [ ] CLI commands integration

### Phase 4: Advanced Features & Optimization (Days 13-15)
- [ ] Performance enhancements
- [ ] Advanced libvirt features
- [ ] Comprehensive testing & validation

## Expected Results
- 60-80% faster VM operations
- 90%+ reduction in IP discovery time
- Enhanced error handling and diagnostics
- Advanced virtualization capabilities

## Key Files Modified
- src/cyris/infrastructure/providers/libvirt_connection_manager.py (NEW)
- src/cyris/infrastructure/providers/libvirt_domain_wrapper.py (NEW)
- src/cyris/infrastructure/providers/libvirt_provider.py (REPLACES virsh_client.py)
- src/cyris/tools/vm_ip_manager.py (MAJOR REWRITE)
- src/cyris/tools/vm_diagnostics.py (MAJOR REWRITE)
- Multiple infrastructure and services files (UPDATED)