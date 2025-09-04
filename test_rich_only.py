#!/usr/bin/env python3
"""
Simple Rich Progress Test

Tests only the Rich progress display functionality without CyRIS dependencies.
"""

import sys
import time
from pathlib import Path

# Add the src directory to the Python path for testing
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from rich.console import Console
    from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
    from rich.status import Status
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
    
    print("✅ Rich library is working correctly")
    
except ImportError as e:
    print(f"❌ Rich library not available: {e}")
    print("Install with: pip install rich")
    sys.exit(1)


def test_rich_basic():
    """Test basic Rich functionality"""
    console = Console()
    
    console.print("[bold blue]Testing Basic Rich Features[/bold blue]")
    console.print("[green]✅ Green success message[/green]")
    console.print("[yellow]⚠️ Yellow warning message[/yellow]")  
    console.print("[red]❌ Red error message[/red]")
    console.print("[dim]CMD: echo 'test command'[/dim]")
    console.print()


def test_rich_progress():
    """Test Rich progress bars"""
    console = Console()
    console.print("[bold blue]Testing Rich Progress Bars[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}", justify="left"),
        BarColumn(bar_width=40),
        "[progress.percentage]{task.percentage:>3.1f}%",
        console=console
    ) as progress:
        
        # Test progress task
        task = progress.add_task("Processing...", total=100)
        
        for i in range(101):
            progress.update(task, completed=i)
            time.sleep(0.02)
        
        console.print("✅ Progress bar test completed")


def test_rich_status():
    """Test Rich status spinner"""
    console = Console()
    console.print("[bold blue]Testing Rich Status Spinner[/bold blue]")
    
    with console.status("[bold green]Working...") as status:
        time.sleep(1)
        console.log("Task 1 completed")
        time.sleep(1)  
        console.log("Task 2 completed")
        time.sleep(1)
        console.log("Task 3 completed")
    
    console.print("✅ Status spinner test completed")


def test_rich_live():
    """Test Rich live display"""
    console = Console()
    console.print("[bold blue]Testing Rich Live Display[/bold blue]")
    
    # Create a table that updates
    table = Table(title="Live Updates")
    table.add_column("Time")
    table.add_column("Status") 
    table.add_column("Message")
    
    with Live(table, console=console, refresh_per_second=4):
        for i in range(5):
            current_time = time.strftime("%H:%M:%S")
            status = "[green]✅[/green]" if i % 2 == 0 else "[yellow]⚠️[/yellow]"
            message = f"Update {i+1}"
            
            table.add_row(current_time, status, message)
            time.sleep(1)
    
    console.print("✅ Live display test completed")


def test_rich_panel():
    """Test Rich panels and layouts"""
    console = Console()
    console.print("[bold blue]Testing Rich Panels[/bold blue]")
    
    # Test panel
    console.print(Panel("This is a test panel", title="[bold yellow]Test Panel[/bold yellow]"))
    
    # Test layout
    layout = Layout()
    layout.split_column(
        Layout(Panel("Top section", border_style="blue"), size=3),
        Layout(Panel("Bottom section", border_style="red"), size=3)
    )
    
    console.print(layout)
    console.print("✅ Panel and layout test completed")


def main():
    console = Console()
    
    console.print("[bold green]🧪 Rich Library Test Suite[/bold green]")
    console.print("Testing Rich functionality for CyRIS progress system\n")
    
    tests = [
        ("Basic Features", test_rich_basic),
        ("Progress Bars", test_rich_progress),
        ("Status Spinner", test_rich_status),
        ("Live Display", test_rich_live),
        ("Panels & Layout", test_rich_panel)
    ]
    
    for test_name, test_func in tests:
        console.print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            test_func()
            console.print(f"[green]✅ {test_name} passed[/green]")
        except Exception as e:
            console.print(f"[red]❌ {test_name} failed: {e}[/red]")
    
    console.print("\n[bold green]🎉 Rich library tests completed![/bold green]")
    console.print("Rich is ready for CyRIS progress integration.")


if __name__ == "__main__":
    main()