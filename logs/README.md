# CyRIS Logs Directory

This directory contains all CyRIS application logs organized by category.

## Directory Structure

```
logs/
├── main/           # Main application and CLI logs
│   ├── debug_main.log     # Main entry script debug logs
│   └── debug_parser.log   # Configuration parser debug logs
├── infrastructure/ # Infrastructure and virtualization logs  
│   └── debug_virt_install.log # VM installation debug logs
├── operations/     # Range creation and operation logs
│   ├── create*.log        # Range creation logs
│   └── *.log             # Other operational logs
└── debug/         # Generic debug and temporary logs
```

## Log Management

- All logs are automatically excluded from git via `.gitignore`
- Log rotation and cleanup should be managed by system tools
- For production deployments, consider using logrotate

## Configuration

Log paths are managed by the unified logging system in:
- `src/cyris/core/unified_logger.py`

## Legacy Note

Previously, log files were scattered in the project root directory. This structure provides centralized, organized log management.