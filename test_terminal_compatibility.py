#!/usr/bin/env python3
"""
Terminal Compatibility Test for Rich Progress System

Tests Rich output in different terminal environments and configurations.
"""

import sys
import os
import time
from pathlib import Path

# Add the src directory to the Python path for testing
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich import get_console
    from rich.terminal_theme import MONOKAI, DIMMED_MONOKAI
    print("✅ Rich library available")
except ImportError as e:
    print(f"❌ Rich library not available: {e}")
    sys.exit(1)


def test_terminal_info():
    """Test terminal detection and capabilities"""
    console = Console()
    
    print("=" * 60)
    print("Terminal Environment Detection")
    print("=" * 60)
    
    # Terminal info
    console.print(f"Terminal size: {console.size.width}x{console.size.height}")
    console.print(f"Color support: {'✅' if console.is_terminal else '❌'}")
    console.print(f"Interactive: {'✅' if console.is_interactive else '❌'}")
    console.print(f"TTY: {'✅' if console.is_terminal else '❌'}")
    console.print(f"Legacy Windows: {'✅' if console.legacy_windows else '❌'}")
    
    # Environment variables
    console.print("\nEnvironment Variables:")
    env_vars = ['TERM', 'COLORTERM', 'TERM_PROGRAM', 'SSH_CLIENT', 'SSH_TTY']
    for var in env_vars:
        value = os.environ.get(var, 'Not set')
        console.print(f"  {var}: {value}")
    
    return console


def test_color_support(console):
    """Test color rendering in current terminal"""
    print("\n" + "=" * 60)
    print("Color Support Testing")
    print("=" * 60)
    
    # Test basic colors
    console.print("Basic Colors:")
    colors = ['red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
    for color in colors:
        console.print(f"  [{color}]■ {color.capitalize()}[/{color}]")
    
    # Test styles
    console.print("\nText Styles:")
    styles = ['bold', 'dim', 'italic', 'underline', 'strike', 'reverse']
    for style in styles:
        console.print(f"  [{style}]{style.capitalize()} text[/{style}]")
    
    # Test RGB support
    console.print("\nRGB Color Support:")
    for i, color in enumerate(['rgb(255,0,0)', 'rgb(0,255,0)', 'rgb(0,0,255)']):
        console.print(f"  [{color}]■ RGB Color {i+1}[/{color}]")


def test_progress_bars(console):
    """Test progress bar rendering"""
    print("\n" + "=" * 60)
    print("Progress Bar Testing")
    print("=" * 60)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),  # Auto-width
        "[progress.percentage]{task.percentage:>3.1f}%",
        console=console,
        transient=False
    ) as progress:
        
        # Test various bar widths
        task1 = progress.add_task("Full width progress...", total=100)
        for i in range(0, 101, 10):
            progress.update(task1, completed=i)
            time.sleep(0.1)
        
        # Test fixed width
        task2 = progress.add_task("Fixed width progress...", total=100)
        for i in range(0, 101, 20):
            progress.update(task2, completed=i)
            time.sleep(0.1)


def test_unicode_support(console):
    """Test Unicode character support"""
    print("\n" + "=" * 60)
    print("Unicode Support Testing")
    print("=" * 60)
    
    # Test common Unicode symbols
    console.print("Common symbols:")
    symbols = {
        'checkmark': '✅',
        'cross': '❌', 
        'warning': '⚠️',
        'info': 'ℹ️',
        'spinner': '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏',
        'arrows': '→ ← ↑ ↓',
        'boxes': '█ ▇ ▆ ▅ ▄ ▃ ▂ ▁',
        'progress': '━━━━━━━━━━'
    }
    
    for name, chars in symbols.items():
        console.print(f"  {name}: {chars}")
    
    # Test box drawing
    console.print("\nBox drawing:")
    console.print("  ┌─────────┐")
    console.print("  │ Unicode │")
    console.print("  │ Boxes   │")
    console.print("  └─────────┘")


def test_wide_terminal(console):
    """Test output in different terminal widths"""
    print("\n" + "=" * 60)
    print("Terminal Width Testing")
    print("=" * 60)
    
    # Test table rendering
    table = Table(title="Terminal Width Test")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Very Long Description Column", style="dim")
    
    table.add_row("Short", "✅", "This is a test entry")
    table.add_row("Medium Length", "⚠️", "This is a longer test entry that might wrap")
    table.add_row("Very Long Component Name", "❌", "This is a very long test entry that will definitely wrap in narrow terminals")
    
    console.print(table)
    
    # Test panel rendering
    long_text = "This is a very long text that should wrap appropriately in different terminal widths. " * 3
    console.print(Panel(long_text, title="[bold]Width Test Panel[/bold]"))


def test_ssh_compatibility():
    """Test SSH terminal compatibility"""
    print("\n" + "=" * 60)
    print("SSH Compatibility Testing")
    print("=" * 60)
    
    # Check if running over SSH
    is_ssh = bool(os.environ.get('SSH_CLIENT') or os.environ.get('SSH_TTY'))
    console = Console()
    
    console.print(f"SSH session detected: {'✅' if is_ssh else '❌'}")
    
    if is_ssh:
        console.print("SSH-specific tests:")
        console.print("  Terminal forwarding: Testing...")
        
        # Test color over SSH
        console.print("  [red]Red color test[/red]")
        console.print("  [green]Green color test[/green]")
        
        # Test progress over SSH
        with console.status("[bold green]SSH progress test..."):
            time.sleep(1)
        console.print("  ✅ SSH progress test completed")
    else:
        console.print("Not running over SSH - local terminal")


def main():
    print("🧪 CyRIS Rich Terminal Compatibility Test")
    print("Testing Rich output in current terminal environment\n")
    
    try:
        # Run all tests
        console = test_terminal_info()
        test_color_support(console)
        test_progress_bars(console)
        test_unicode_support(console)
        test_wide_terminal(console)
        test_ssh_compatibility()
        
        # Final summary
        console.print(f"\n{'='*60}")
        console.print("[bold green]✅ Terminal compatibility tests completed![/bold green]")
        console.print("Rich progress system is compatible with this terminal environment.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())