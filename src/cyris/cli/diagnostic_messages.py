"""
Diagnostic Messages System

Provides user-friendly diagnostic messages and formatting for VM health issues.
"""

from rich.text import Text
from rich.panel import Panel
from rich.console import Group
from typing import List, Dict
from ..tools.vm_diagnostics import DiagnosticResult, DiagnosticLevel


class DiagnosticMessageFormatter:
    """Formats diagnostic results for user-friendly display"""
    
    # Emoji and style mapping for different diagnostic levels
    LEVEL_STYLES = {
        DiagnosticLevel.INFO: ("ℹ️", "blue", "dim"),
        DiagnosticLevel.WARNING: ("⚠️", "yellow", "bold"),
        DiagnosticLevel.ERROR: ("❌", "red", "bold"),
        DiagnosticLevel.CRITICAL: ("🚨", "red", "bold red")
    }
    
    def __init__(self, console=None):
        self.console = console
    
    def format_diagnostic_summary(self, vm_name: str, results: List[DiagnosticResult]) -> Text:
        """Create a summary line for diagnostic results"""
        if not results:
            return Text()
        
        # Count issues by severity
        counts = {level: 0 for level in DiagnosticLevel}
        for result in results:
            counts[result.level] += 1
        
        # Build summary text
        summary_parts = []
        
        if counts[DiagnosticLevel.CRITICAL] > 0:
            summary_parts.append(f"🚨 {counts[DiagnosticLevel.CRITICAL]} critical")
        if counts[DiagnosticLevel.ERROR] > 0:
            summary_parts.append(f"❌ {counts[DiagnosticLevel.ERROR]} errors")
        if counts[DiagnosticLevel.WARNING] > 0:
            summary_parts.append(f"⚠️ {counts[DiagnosticLevel.WARNING]} warnings")
        
        if not summary_parts:
            return Text("✅ Healthy", style="green")
        
        return Text(" | ".join(summary_parts), style="yellow")
    
    def format_diagnostic_details(self, vm_name: str, results: List[DiagnosticResult]) -> List[Text]:
        """Format detailed diagnostic information"""
        if not results:
            return []
        
        # Filter out INFO level for brief display unless specifically requested
        significant_results = [r for r in results if r.level != DiagnosticLevel.INFO]
        
        if not significant_results:
            return []
        
        formatted_lines = []
        formatted_lines.append(Text(f"\n📋 Diagnostics for {vm_name}:", style="bold cyan"))
        
        for result in significant_results:
            emoji, color, style = self.LEVEL_STYLES[result.level]
            
            # Main message
            message_text = Text.assemble(
                (emoji + " ", color),
                (result.message, style)
            )
            formatted_lines.append(message_text)
            
            # Suggestion if available
            if result.suggestion:
                suggestion_text = Text.assemble(
                    ("   💡 ", "blue"),
                    ("Suggestion: ", "blue bold"),
                    (result.suggestion, "blue")
                )
                formatted_lines.append(suggestion_text)
        
        return formatted_lines
    
    def format_quick_fix_suggestions(self, results: List[DiagnosticResult]) -> List[Text]:
        """Format quick fix suggestions for common issues"""
        quick_fixes = []
        
        # Extract actionable suggestions
        for result in results:
            if result.suggestion and any(keyword in result.suggestion.lower() 
                                       for keyword in ['virsh', 'attach', 'restart', 'create']):
                quick_fixes.append(Text.assemble(
                    ("🔧 ", "green"),
                    ("Quick fix: ", "green bold"),
                    (result.suggestion, "green")
                ))
        
        return quick_fixes
    
    def get_health_indicator(self, results: List[DiagnosticResult]) -> Text:
        """Get a single health indicator emoji/text"""
        if not results:
            return Text("❓", style="dim")
        
        # Determine worst case
        max_severity = DiagnosticLevel.INFO
        for result in results:
            if result.level == DiagnosticLevel.CRITICAL:
                max_severity = DiagnosticLevel.CRITICAL
                break
            elif result.level == DiagnosticLevel.ERROR and max_severity != DiagnosticLevel.CRITICAL:
                max_severity = DiagnosticLevel.ERROR
            elif result.level == DiagnosticLevel.WARNING and max_severity == DiagnosticLevel.INFO:
                max_severity = DiagnosticLevel.WARNING
        
        emoji, color, _ = self.LEVEL_STYLES[max_severity]
        
        # Special case for healthy VMs
        if max_severity == DiagnosticLevel.INFO:
            return Text("✅", style="green")
        
        return Text(emoji, style=color)


# Predefined diagnostic patterns and solutions
DIAGNOSTIC_PATTERNS = {
    "missing_cloud_init": {
        "description": "VM missing cloud-init configuration",
        "quick_fix": "virsh attach-disk {vm_name} /home/ubuntu/cyris/docs/images/cloud-init.iso hdc --type cdrom --config",
        "explanation": "cloud-init.iso is required for VM initialization including network setup and user configuration"
    },
    
    "small_image": {
        "description": "VM image suspiciously small",
        "quick_fix": "Check base image: qemu-img info /path/to/base.qcow2",
        "explanation": "Images smaller than 500MB likely indicate corruption or incomplete creation"
    },
    
    "no_network_activity": {
        "description": "VM shows no network activity",
        "quick_fix": "1. Check cloud-init: virsh console {vm_name}\n2. Restart VM: virsh reboot {vm_name}",
        "explanation": "VMs without network activity may have failed initialization or network configuration issues"
    },
    
    "no_dhcp_lease": {
        "description": "VM has not obtained DHCP lease",
        "quick_fix": "virsh net-dhcp-leases default | grep {mac_address}",
        "explanation": "Check if VM is requesting DHCP and network configuration is correct"
    },
    
    "vm_startup_failed": {
        "description": "VM appears to have startup issues",
        "quick_fix": "Check console: virsh console {vm_name} --safe",
        "explanation": "VM may have failed to complete boot process or encountered errors"
    }
}


def get_diagnostic_pattern_help(pattern_name: str, **kwargs) -> Dict[str, str]:
    """Get help information for a specific diagnostic pattern"""
    pattern = DIAGNOSTIC_PATTERNS.get(pattern_name, {})
    
    result = {
        "description": pattern.get("description", "Unknown issue"),
        "explanation": pattern.get("explanation", "No additional information available"),
        "quick_fix": pattern.get("quick_fix", "No automated fix available")
    }
    
    # Format quick fix with provided parameters
    try:
        result["quick_fix"] = result["quick_fix"].format(**kwargs)
    except:
        pass  # Keep original if formatting fails
    
    return result


def format_diagnostic_help_panel(title: str, help_info: Dict[str, str]) -> Panel:
    """Create a Rich panel with diagnostic help information"""
    content_lines = [
        Text("📄 " + help_info["description"], style="bold"),
        Text(),
        Text("💡 Explanation:", style="blue bold"),
        Text(help_info["explanation"], style="blue"),
        Text(),
        Text("🔧 Quick Fix:", style="green bold"),
        Text(help_info["quick_fix"], style="green")
    ]
    
    return Panel(
        Group(*content_lines),
        title=f"[bold cyan]{title}[/bold cyan]",
        title_align="left",
        border_style="blue"
    )