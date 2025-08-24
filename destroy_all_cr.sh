#!/bin/bash

# Modern CyRIS Mass Range Destruction Script
# Uses the new Docker-style range lifecycle management system
# Compatible with both legacy and modern CyRIS installations

set -euo pipefail  # Exit on error, undefined variables, pipe failures

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script metadata
readonly SCRIPT_NAME="destroy_all_cr.sh"
readonly VERSION="2.0.0"

# Global variables
CYRIS_PATH=""
CONFIG_FILE=""
FORCE_MODE=false
REMOVE_MODE=false
DRY_RUN=false
MODERN_CLI=true
VERBOSE=false

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  INFO: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ SUCCESS: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
}

print_usage() {
    cat << EOF
${SCRIPT_NAME} v${VERSION} - Modern CyRIS Mass Range Destruction

DESCRIPTION:
    Destroys all cyber ranges using the new Docker-style lifecycle management.
    Supports both modern CLI and legacy methods with comprehensive cleanup.

USAGE:
    $0 [OPTIONS] CYRIS_PATH [CONFIG_FILE]

ARGUMENTS:
    CYRIS_PATH      Path to CyRIS installation directory
    CONFIG_FILE     Configuration file (optional, auto-detected if not provided)

OPTIONS:
    -f, --force     Force destruction without confirmation prompts
    -r, --rm        Remove all records after destroying (like docker run --rm)
    -n, --dry-run   Show what would be destroyed without actually doing it
    -l, --legacy    Use legacy destruction methods instead of modern CLI
    -v, --verbose   Enable verbose output
    -h, --help      Show this help message

EXAMPLES:
    # Interactive destruction (recommended)
    $0 /home/cyuser/cyris/

    # Force destroy all ranges and remove all traces
    $0 --force --rm /home/cyuser/cyris/

    # Dry run to see what would be destroyed
    $0 --dry-run /home/cyuser/cyris/

    # Use legacy method for older installations
    $0 --legacy /home/cyuser/cyris/ CONFIG

DOCKER-STYLE COMMANDS USED:
    cyris destroy --force --rm <range_id>    # Modern approach
    cyris rm --force <range_id>               # For destroyed ranges

EOF
}

# Parse command line arguments
parse_arguments() {
    local args=()
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                FORCE_MODE=true
                shift
                ;;
            -r|--rm)
                REMOVE_MODE=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -l|--legacy)
                MODERN_CLI=false
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            -*)
                print_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done

    # Validate required arguments
    if [[ ${#args[@]} -eq 0 ]]; then
        print_error "Missing required argument: CYRIS_PATH"
        print_usage
        exit 1
    fi

    CYRIS_PATH="${args[0]}"
    
    # Auto-detect config file if not provided
    if [[ ${#args[@]} -ge 2 ]]; then
        CONFIG_FILE="${args[1]}"
    else
        # Try to auto-detect config file
        local potential_configs=("$CYRIS_PATH/CONFIG" "$CYRIS_PATH/config.yml" "$CYRIS_PATH/config.yaml")
        for config in "${potential_configs[@]}"; do
            if [[ -f "$config" ]]; then
                CONFIG_FILE="$config"
                break
            fi
        done
        
        if [[ -z "$CONFIG_FILE" ]] && [[ "$MODERN_CLI" == false ]]; then
            print_error "No configuration file found and legacy mode requires CONFIG file"
            exit 1
        fi
    fi
}

# Validate environment
validate_environment() {
    print_info "Validating CyRIS environment..."
    
    # Check CyRIS path
    if [[ ! -d "$CYRIS_PATH" ]]; then
        print_error "CyRIS path does not exist: $CYRIS_PATH"
        exit 1
    fi
    
    # Check for modern CLI
    local cyris_cli="$CYRIS_PATH/cyris"
    if [[ "$MODERN_CLI" == true ]]; then
        if [[ ! -f "$cyris_cli" ]] || [[ ! -x "$cyris_cli" ]]; then
            print_warning "Modern CLI not found or not executable: $cyris_cli"
            print_info "Falling back to legacy mode..."
            MODERN_CLI=false
        fi
    fi
    
    # Check for legacy components if needed
    if [[ "$MODERN_CLI" == false ]]; then
        local legacy_script="$CYRIS_PATH/main/cyris.py"
        if [[ ! -f "$legacy_script" ]]; then
            print_error "Legacy CyRIS script not found: $legacy_script"
            exit 1
        fi
        
        if [[ ! -f "$CONFIG_FILE" ]]; then
            print_error "Configuration file not found: $CONFIG_FILE"
            exit 1
        fi
    fi
    
    print_success "Environment validation passed"
}

# Get list of ranges using modern CLI
get_ranges_modern() {
    local cyris_cli="$CYRIS_PATH/cyris"
    
    # Try to get structured list of ranges
    if command -v jq &> /dev/null && $cyris_cli list --all --format json &> /dev/null; then
        # If JSON output is supported (future enhancement)
        $cyris_cli list --all --format json 2>/dev/null | jq -r '.[].range_id' 2>/dev/null || true
    else
        # Parse text output
        $cyris_cli list --all 2>/dev/null | grep -E '^\s*[🟢🟡🔴]' | awk '{print $2}' | cut -d: -f1 || true
    fi
}

# Get list of ranges using filesystem scan
get_ranges_filesystem() {
    local cyber_range_dir
    
    if [[ "$MODERN_CLI" == true ]]; then
        # Try to get cyber_range_dir from modern config
        cyber_range_dir=$($CYRIS_PATH/cyris config-show 2>/dev/null | grep "Cyber range directory:" | cut -d: -f2- | xargs || echo "")
    fi
    
    # Fallback to legacy config parsing or default
    if [[ -z "$cyber_range_dir" ]] && [[ -f "$CONFIG_FILE" ]]; then
        cyber_range_dir=$(grep "^RANGE_DIRECTORY=" "$CONFIG_FILE" 2>/dev/null | cut -d= -f2 || echo "")
    fi
    
    # Final fallback
    if [[ -z "$cyber_range_dir" ]]; then
        cyber_range_dir="$CYRIS_PATH/cyber_range"
    fi
    
    if [[ -d "$cyber_range_dir" ]]; then
        find "$cyber_range_dir" -maxdepth 1 -type d -not -path "$cyber_range_dir" -exec basename {} \; 2>/dev/null || true
    fi
}

# Destroy a single range using modern CLI
destroy_range_modern() {
    local range_id="$1"
    local cyris_cli="$CYRIS_PATH/cyris"
    
    local cmd_args=()
    
    if [[ "$FORCE_MODE" == true ]]; then
        cmd_args+=(--force)
    fi
    
    if [[ "$REMOVE_MODE" == true ]]; then
        cmd_args+=(--rm)
    fi
    
    if [[ "$VERBOSE" == true ]]; then
        cmd_args+=(--verbose)
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "Would execute: $cyris_cli destroy ${cmd_args[*]} $range_id"
        return 0
    fi
    
    print_info "Destroying range $range_id using modern CLI..."
    
    if [[ "$FORCE_MODE" == true ]]; then
        # Force mode - no interaction needed
        $cyris_cli destroy "${cmd_args[@]}" "$range_id"
    else
        # Interactive mode - pass 'y' to confirm
        echo "y" | $cyris_cli destroy "${cmd_args[@]}" "$range_id"
    fi
}

# Destroy a single range using legacy method
destroy_range_legacy() {
    local range_id="$1"
    local cyber_range_dir=$(grep "^RANGE_DIRECTORY=" "$CONFIG_FILE" | cut -d= -f2)
    local range_path="$cyber_range_dir/$range_id"
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "Would destroy legacy range: $range_path"
        return 0
    fi
    
    print_info "Destroying range $range_id using legacy method..."
    
    if [[ -d "$range_path" ]]; then
        # Execute any cleanup scripts
        for script in "$range_path"/*.sh; do
            if [[ -f "$script" && "$script" == *whole-controlled* ]]; then
                print_info "Executing cleanup script: $(basename "$script")"
                "$script" 2>/dev/null || print_warning "Cleanup script failed: $script"
            fi
        done
        
        # Remove the range directory
        rm -rf "$range_path"
        print_success "Removed range directory: $range_path"
    else
        print_warning "Range directory not found: $range_path"
    fi
}

# Clean up temporary files and orphaned resources
cleanup_system() {
    print_info "Cleaning up system resources..."
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "Would clean up temporary files and orphaned resources"
        return 0
    fi
    
    # Clean up settings files
    local settings_dir="$CYRIS_PATH/settings"
    if [[ -d "$settings_dir" ]]; then
        find "$settings_dir" -name "*.txt" -type f -delete 2>/dev/null || true
        print_info "Cleaned up temporary setting files in $settings_dir"
    fi
    
    # Clean up logs if they're very old (>30 days)
    local logs_dir="$CYRIS_PATH/logs"
    if [[ -d "$logs_dir" ]]; then
        find "$logs_dir" -name "*.log" -type f -mtime +30 -delete 2>/dev/null || true
        print_info "Cleaned up old log files in $logs_dir"
    fi
    
    # Check for orphaned KVM VMs
    if command -v virsh &> /dev/null; then
        local orphaned_vms
        orphaned_vms=$(virsh --connect qemu:///session list --name 2>/dev/null | grep "^cyris-" || true)
        
        if [[ -n "$orphaned_vms" ]]; then
            print_warning "Found potentially orphaned CyRIS VMs:"
            echo "$orphaned_vms" | while read -r vm_name; do
                [[ -n "$vm_name" ]] && echo "  - $vm_name"
            done
            print_info "Use 'virsh --connect qemu:///session destroy <vm-name>' to clean them up manually"
        fi
    fi
}

# Main destruction logic
destroy_all_ranges() {
    print_info "Scanning for cyber ranges..."
    
    local ranges=()
    
    if [[ "$MODERN_CLI" == true ]]; then
        # Try modern CLI first
        mapfile -t ranges < <(get_ranges_modern)
        
        # If no ranges found via CLI, try filesystem scan
        if [[ ${#ranges[@]} -eq 0 ]]; then
            print_info "No ranges found via modern CLI, scanning filesystem..."
            mapfile -t ranges < <(get_ranges_filesystem)
        fi
    else
        # Use filesystem scan for legacy mode
        mapfile -t ranges < <(get_ranges_filesystem)
    fi
    
    # Filter out empty entries
    local valid_ranges=()
    for range in "${ranges[@]}"; do
        [[ -n "$range" ]] && valid_ranges+=("$range")
    done
    
    if [[ ${#valid_ranges[@]} -eq 0 ]]; then
        print_info "No cyber ranges found to destroy"
        return 0
    fi
    
    print_warning "Found ${#valid_ranges[@]} cyber ranges to destroy:"
    for range in "${valid_ranges[@]}"; do
        echo "  - $range"
    done
    
    # Confirmation prompt (unless in force mode or dry run)
    if [[ "$FORCE_MODE" == false && "$DRY_RUN" == false ]]; then
        echo
        read -p "Are you sure you want to destroy ALL these ranges? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Operation cancelled by user"
            return 0
        fi
    fi
    
    # Destroy each range
    local success_count=0
    local total_count=${#valid_ranges[@]}
    
    for range_id in "${valid_ranges[@]}"; do
        print_info "Processing range $((success_count + 1))/$total_count: $range_id"
        
        if [[ "$MODERN_CLI" == true ]]; then
            if destroy_range_modern "$range_id"; then
                ((success_count++))
                print_success "Range $range_id processed successfully"
            else
                print_error "Failed to process range $range_id"
            fi
        else
            if destroy_range_legacy "$range_id"; then
                ((success_count++))
                print_success "Range $range_id processed successfully"
            else
                print_error "Failed to process range $range_id"
            fi
        fi
    done
    
    print_info "Processing complete: $success_count/$total_count ranges processed successfully"
    
    # System cleanup
    cleanup_system
}

# Signal handlers for graceful shutdown
trap_exit() {
    print_warning "Script interrupted by user"
    exit 130
}

trap trap_exit INT TERM

# Main execution
main() {
    print_info "Starting $SCRIPT_NAME v$VERSION"
    
    parse_arguments "$@"
    validate_environment
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "DRY RUN MODE - No actual changes will be made"
    fi
    
    if [[ "$MODERN_CLI" == true ]]; then
        print_info "Using modern CyRIS CLI interface"
    else
        print_info "Using legacy CyRIS interface"
    fi
    
    destroy_all_ranges
    
    if [[ "$DRY_RUN" == false ]]; then
        print_success "All operations completed successfully!"
    else
        print_info "Dry run completed - no actual changes were made"
    fi
}

# Execute main function with all arguments
main "$@"