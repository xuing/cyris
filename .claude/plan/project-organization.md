# Project Organization Task - Execution Plan

## Context
Reorganize CyRIS project structure by moving MD files to docs/ and test Python files to tests/.

## Requirements Analysis
- **Goal**: Clean project structure following Python conventions
- **Scope**: Root directory MD files (10) and test*.py files (8) 
- **Expected Results**: Organized docs/ subdirectories and consolidated tests/

## Approved Solution: Organized Migration with Import Analysis
- Analyze dependencies before moving
- Create logical subdirectories in docs/
- Update import references as needed
- Verify functionality post-migration

## Execution Steps
### Phase A: Pre-Migration Analysis
1. Analyze import dependencies in test files
2. Check for hardcoded file paths in scripts
3. Create logical subdirectories in docs/

### Phase B: Documentation Migration  
4. Create docs subdirectories (design/, analysis/, guides/)
5. Move MD files to appropriate subdirectories
6. Keep CLAUDE.md and README.md in root

### Phase C: Test Files Migration
7. Move root test files to tests/
8. Update import paths if needed  
9. Update script references to moved files

### Phase D: Verification & Cleanup
10. Verify project structure
11. Test critical functionality
12. Update documentation references

## Files to Process
**MD Files (10)**: MODERNIZATION_DESIGN.md, destroy_all_cr_README.md, README-cloud-init.md, COMPREHENSIVE_ANALYSIS.md, VM_IP_DISCOVERY_SUMMARY.md, MODERNIZATION_SUMMARY.md, DEPLOYMENT_ANALYSIS.md, BUGFIX_RECORD.md

**Test Files (8)**: test_add_account.py, simple_test.py, test_script_upload.py, test_legacy_core.py, test_modern_services.py, test_comprehensive_verification.py, test_service_integration.py, test_kvm_session.py, test_complete_functionality.py, test_emoji_detection.py