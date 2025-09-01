# CLI Module

[Root Directory](../../../CLAUDE.md) > [src](../../) > [cyris](../) > **cli**

## Module Responsibilities

The CLI module provides the modern command-line interface for CyRIS using Click framework with Rich UI enhancements. It serves as the primary user interaction layer, handling command parsing, validation, and delegation to appropriate service handlers.

## Entry and Startup

- **Primary Entry**: `main.py` - Main CLI application with Click groups and commands
- **Unified Entry**: `/home/ubuntu/cyris/cyris` - Unified entry script that delegates to modern CLI
- **Direct Entry**: `/home/ubuntu/cyris/cyris-cli` - Direct modern CLI entry point

### Command Structure
```
cyris
├── create <yaml_file>     # Create cyber range
├── list [--all] [-v]      # List ranges  
├── status <range_id> [-v] # Show range status
├── destroy <range_id>     # Destroy range
├── rm <range_id>          # Remove range records
├── validate               # Validate environment
├── config-show            # Show configuration
├── config-init            # Initialize config
├── ssh-info <range_id>    # SSH connection info
├── setup-permissions      # Setup libvirt permissions
└── legacy <args...>       # Legacy compatibility
```

## External Interfaces

### Command Handlers
Located in `commands/` directory:
- `CreateCommandHandler` - Range creation logic
- `ListCommandHandler` - Range listing and discovery
- `StatusCommandHandler` - Range status and health checking
- `DestroyCommandHandler` - Range destruction and cleanup
- `ConfigCommandHandler` - Configuration management
- `SSHInfoCommandHandler` - SSH connection information
- `PermissionsCommandHandler` - System permissions setup
- `LegacyCommandHandler` - Legacy command compatibility

### Rich UI Components
Located in `presentation/` directory:
- Status displays with colored output
- Progress indicators for long operations
- Formatted tables for range listings
- Error message formatting

## Key Dependencies and Configuration

### External Dependencies
```python
click>=8.0          # Command-line interface framework
rich>=14.0          # Rich text and beautiful formatting
pydantic>=2.0       # Configuration validation
structlog>=23.0     # Structured logging
```

### Internal Dependencies
- `config.settings.CyRISSettings` - Configuration management
- `config.parser.parse_modern_config` - YAML configuration parsing
- `services.orchestrator` - Range orchestration services

### Configuration Options
- `--config/-c` - Custom configuration file path
- `--verbose/-v` - Verbose output mode
- `--version` - Show version information

## Data Models

### Command Context
```python
class CommandContext:
    config: CyRISSettings
    verbose: bool
    
    # Available in ctx.obj for all commands
```

### Range Identification
- Range IDs are strings (e.g., "basic", "advanced-001")
- Support both numeric and string identifiers
- Validation through configuration parser

## Testing and Quality

### Unit Tests
- `/home/ubuntu/cyris/tests/unit/test_cli_commands.py` - Command handler testing
- Mock external dependencies (orchestrator, file system)
- Test command argument validation and error handling

### Integration Tests
- `/home/ubuntu/cyris/tests/e2e/test_cli_interface.py` - Full CLI workflow testing
- Test actual command execution with real configurations
- Validate output formatting and error messages

### E2E Tests
- `/home/ubuntu/cyris/tests/e2e/test_full_deployment.py` - Complete deployment workflows
- Test CLI interactions with real VM creation/destruction
- Verify status reporting accuracy

### Quality Checks
```bash
# Type checking
mypy src/cyris/cli/

# Style checking
black src/cyris/cli/
flake8 src/cyris/cli/

# Test execution
pytest tests/unit/test_cli_commands.py -v
pytest tests/e2e/test_cli_interface.py -v
```

## Frequently Asked Questions (FAQ)

### Q: How does CLI interact with legacy commands?
A: The `legacy` subcommand delegates to the original `main/cyris.py` script while maintaining modern CLI interface consistency.

### Q: What's the difference between `destroy` and `rm`?
A: `destroy` stops VMs and cleans up resources but keeps metadata. `rm` additionally removes all records (like `docker run --rm`).

### Q: How are errors handled and displayed?
A: Errors use Rich formatting with color coding and structured error messages that provide actionable next steps.

### Q: Can I use the CLI programmatically?
A: Yes, import `cyris.cli.main.cli` and call it with argument lists, or use command handlers directly.

## Related File List

### Core Files
- `/home/ubuntu/cyris/src/cyris/cli/main.py` - Main CLI application
- `/home/ubuntu/cyris/src/cyris/cli/__init__.py` - Module initialization

### Command Handlers
- `/home/ubuntu/cyris/src/cyris/cli/commands/__init__.py` - Command handler exports
- `/home/ubuntu/cyris/src/cyris/cli/commands/create_command.py` - Range creation handler
- `/home/ubuntu/cyris/src/cyris/cli/commands/list_command.py` - Range listing handler
- `/home/ubuntu/cyris/src/cyris/cli/commands/status_command.py` - Status reporting handler
- `/home/ubuntu/cyris/src/cyris/cli/commands/destroy_command.py` - Range destruction handler
- `/home/ubuntu/cyris/src/cyris/cli/commands/config_command.py` - Configuration management
- `/home/ubuntu/cyris/src/cyris/cli/commands/ssh_command.py` - SSH info handler
- `/home/ubuntu/cyris/src/cyris/cli/commands/permissions_command.py` - Permissions setup
- `/home/ubuntu/cyris/src/cyris/cli/commands/legacy_command.py` - Legacy compatibility

### Presentation Layer
- `/home/ubuntu/cyris/src/cyris/cli/presentation/__init__.py` - UI component exports
- `/home/ubuntu/cyris/src/cyris/cli/presentation/` - Rich UI components (to be implemented)

### Entry Points
- `/home/ubuntu/cyris/cyris` - Unified entry script
- `/home/ubuntu/cyris/cyris-cli` - Direct CLI entry script

## Change Log (Changelog)

### 2025-09-01
- **[INITIALIZATION]** Created CLI module documentation with comprehensive interface mapping
- **[STRUCTURE]** Documented command handler architecture and Rich UI integration
- **[TESTING]** Outlined testing strategy for unit, integration, and e2e scenarios