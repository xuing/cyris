"""
Rich-based Progress Management System

Provides comprehensive progress tracking with Rich UI components including:
- Nested progress bars for complex operations
- Status spinners for indeterminate tasks  
- Live logging above progress displays
- Color-coded feedback and professional terminal UI
- Integration with existing progress tracking system

Designed to replace basic print statements with rich, interactive progress displays
while maintaining compatibility with non-interactive environments.
"""

import time
import threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
from rich.status import Status
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.align import Align


class ProgressLevel(Enum):
    """Progress operation levels"""
    MAIN = "main"           # Top-level operation (e.g., "Creating cyber range")
    PHASE = "phase"         # Major phases (e.g., "Building images", "Creating VMs")
    STEP = "step"           # Individual steps (e.g., "Downloading ubuntu-20.04")
    DETAIL = "detail"       # Fine-grained details (e.g., "Customizing image")


@dataclass
class ProgressStep:
    """Individual progress step with Rich UI integration"""
    step_id: str
    description: str
    level: ProgressLevel
    total: Optional[int] = None
    completed: int = 0
    task_id: Optional[TaskID] = None
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def start(self) -> None:
        """Mark step as started"""
        self.status = "running"
        self.start_time = time.time()
    
    def complete(self) -> None:
        """Mark step as completed"""
        self.status = "completed"
        self.end_time = time.time()
        if self.total:
            self.completed = self.total
    
    def fail(self, error: str) -> None:
        """Mark step as failed"""
        self.status = "failed"
        self.end_time = time.time()
        self.error_message = error
    
    def update_progress(self, completed: int, total: Optional[int] = None) -> None:
        """Update progress values"""
        self.completed = completed
        if total is not None:
            self.total = total
    
    @property
    def duration(self) -> Optional[float]:
        """Get step duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class RichProgressManager:
    """
    Rich-based progress manager with advanced UI capabilities
    
    Features:
    - Nested progress bars for complex operations
    - Live status updates with spinners
    - Concurrent logging above progress displays
    - Color-coded status indication
    - Professional terminal UI with timing information
    """
    
    def __init__(self, operation_name: str, console: Optional[Console] = None):
        self.operation_name = operation_name
        self.console = console or Console()
        self.steps: Dict[str, ProgressStep] = {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.overall_success = True
        
        # Progress tracking components
        self.progress: Optional[Progress] = None
        self.live: Optional[Live] = None
        self.status: Optional[Status] = None
        self._lock = threading.Lock()
        
        # Log message buffer for display above progress
        self.log_messages: List[str] = []
        self.max_log_lines = 20
    
    def create_progress_display(self) -> Progress:
        """Create Rich progress display with custom columns"""
        return Progress(
            SpinnerColumn(style="bold green"),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            TimeElapsedColumn(),
            "•",
            TimeRemainingColumn(),
            console=self.console,
            expand=True
        )
    
    @contextmanager
    def progress_context(self):
        """Context manager for Rich progress display"""
        self.progress = self.create_progress_display()
        
        try:
            with self.progress:
                yield self.progress
        finally:
            self.progress = None
    
    @contextmanager 
    def live_context(self):
        """Context manager for live display with logging"""
        layout = Layout()
        
        # Create log panel
        log_panel = self._create_log_panel()
        
        # Create progress panel
        progress_panel = Panel(
            self.progress.make_tasks_table(self.progress.tasks) if self.progress else Text("Initializing..."),
            title=f"[bold blue]{self.operation_name}[/bold blue]",
            border_style="blue"
        )
        
        layout.split_column(
            Layout(log_panel, name="logs", size=10),
            Layout(progress_panel, name="progress")
        )
        
        self.live = Live(layout, console=self.console, refresh_per_second=4)
        
        try:
            with self.live:
                yield self.live
        finally:
            self.live = None
    
    @contextmanager
    def status_context(self, message: str, spinner: str = "dots"):
        """Context manager for status spinner"""
        self.status = Status(message, console=self.console, spinner=spinner)
        
        try:
            with self.status:
                yield self.status
        finally:
            self.status = None
    
    def add_step(self, step_id: str, description: str, level: ProgressLevel = ProgressLevel.STEP, 
                 total: Optional[int] = None) -> ProgressStep:
        """Add a new progress step"""
        step = ProgressStep(step_id, description, level, total)
        self.steps[step_id] = step
        return step
    
    def start_step(self, step_id: str, description: Optional[str] = None) -> Optional[TaskID]:
        """Start a progress step and create Rich task"""
        with self._lock:
            step = self.steps.get(step_id)
            if not step:
                if description:
                    step = self.add_step(step_id, description)
                else:
                    self.log_error(f"Step {step_id} not found and no description provided")
                    return None
            
            step.start()
            
            # Create Rich progress task if progress display is active
            if self.progress:
                task_id = self.progress.add_task(
                    description=step.description,
                    total=step.total or 100,
                    completed=step.completed
                )
                step.task_id = task_id
                return task_id
            else:
                # Fallback to console logging
                self.log_info(f"Starting: {step.description}")
                return None
    
    def update_step(self, step_id: str, completed: int, total: Optional[int] = None, 
                   description: Optional[str] = None) -> None:
        """Update progress step"""
        with self._lock:
            step = self.steps.get(step_id)
            if not step:
                return
            
            step.update_progress(completed, total)
            
            if self.progress and step.task_id:
                self.progress.update(
                    step.task_id,
                    completed=completed,
                    total=total or step.total or 100,
                    description=description or step.description
                )
    
    def complete_step(self, step_id: str, message: Optional[str] = None) -> None:
        """Complete a progress step"""
        with self._lock:
            step = self.steps.get(step_id)
            if not step:
                return
            
            step.complete()
            
            if self.progress and step.task_id:
                self.progress.update(
                    step.task_id,
                    completed=step.total or 100,
                    description=f"✅ {step.description}"
                )
            
            success_msg = message or f"Completed: {step.description}"
            self.log_success(success_msg)
    
    def fail_step(self, step_id: str, error: str) -> None:
        """Fail a progress step"""
        with self._lock:
            step = self.steps.get(step_id)
            if not step:
                # Create step if it doesn't exist for error reporting
                step = self.add_step(step_id, f"Failed operation: {step_id}")
            
            step.fail(error)
            self.overall_success = False
            
            if self.progress and step.task_id:
                self.progress.update(
                    step.task_id,
                    description=f"❌ {step.description}"
                )
            
            self.log_error(f"Failed: {step.description} - {error}")
    
    def log_info(self, message: str) -> None:
        """Log info message"""
        self._add_log_message(f"[bold blue]INFO[/bold blue]: {message}")
    
    def log_success(self, message: str) -> None:
        """Log success message"""
        self._add_log_message(f"[bold green]SUCCESS[/bold green]: {message}")
    
    def log_warning(self, message: str) -> None:
        """Log warning message"""
        self._add_log_message(f"[bold yellow]WARNING[/bold yellow]: {message}")
    
    def log_error(self, message: str) -> None:
        """Log error message"""
        self._add_log_message(f"[bold red]ERROR[/bold red]: {message}")
    
    def log_command(self, command: str) -> None:
        """Log command being executed"""
        self._add_log_message(f"[dim]CMD[/dim]: {command}")
    
    def _add_log_message(self, message: str) -> None:
        """Add message to log buffer"""
        with self._lock:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[dim]{timestamp}[/dim] {message}"
            
            self.log_messages.append(formatted_message)
            
            # Keep only recent messages
            if len(self.log_messages) > self.max_log_lines:
                self.log_messages = self.log_messages[-self.max_log_lines:]
            
            # Print to console if no live display
            if not self.live:
                self.console.print(formatted_message)
            
            # Update live display if available
            if self.live:
                self._update_live_display()
    
    def _create_log_panel(self) -> Panel:
        """Create log display panel"""
        if not self.log_messages:
            log_content = Text("Ready to start...", style="dim")
        else:
            log_content = Text("\n".join(self.log_messages[-10:]))  # Show last 10 messages
        
        return Panel(
            log_content,
            title="[bold yellow]Progress Log[/bold yellow]",
            border_style="yellow",
            height=8
        )
    
    def _update_live_display(self) -> None:
        """Update live display with current state"""
        if not self.live:
            return
        
        try:
            layout = Layout()
            
            # Update log panel
            log_panel = self._create_log_panel()
            
            # Update progress panel
            if self.progress:
                progress_content = self.progress.make_tasks_table(self.progress.tasks)
            else:
                progress_content = Text("No active progress tasks", style="dim")
            
            progress_panel = Panel(
                progress_content,
                title=f"[bold blue]{self.operation_name}[/bold blue]",
                border_style="blue"
            )
            
            layout.split_column(
                Layout(log_panel, name="logs", size=10),
                Layout(progress_panel, name="progress")
            )
            
            self.live.update(layout)
        except Exception:
            # Ignore display update errors to prevent breaking main functionality
            pass
    
    def complete(self) -> None:
        """Complete the overall operation"""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        
        if self.overall_success:
            self.log_success(f"Operation completed successfully in {duration:.1f}s")
        else:
            failed_count = len([s for s in self.steps.values() if s.status == "failed"])
            self.log_error(f"Operation failed with {failed_count} error(s) after {duration:.1f}s")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get operation summary"""
        return {
            'operation': self.operation_name,
            'success': self.overall_success,
            'duration': self.duration,
            'steps_completed': len([s for s in self.steps.values() if s.status == "completed"]),
            'steps_failed': len([s for s in self.steps.values() if s.status == "failed"]),
            'steps_total': len(self.steps)
        }
    
    @property
    def duration(self) -> Optional[float]:
        """Get total operation duration"""
        if self.end_time:
            return self.end_time - self.start_time
        return None


class GlobalRichProgressManager:
    """
    Global progress manager for system-wide Rich UI coordination
    
    Ensures consistent Rich UI across all operations and prevents
    conflicting progress displays from interfering with each other.
    """
    
    def __init__(self):
        self.operations: Dict[str, RichProgressManager] = {}
        self.active_operation: Optional[str] = None
        self._lock = threading.Lock()
        self.console = Console()
    
    def create_operation(self, operation_id: str, operation_name: str) -> RichProgressManager:
        """Create a new Rich progress manager"""
        with self._lock:
            manager = RichProgressManager(operation_name, self.console)
            self.operations[operation_id] = manager
            
            # Set as active if no other active operation
            if not self.active_operation:
                self.active_operation = operation_id
                
            return manager
    
    def get_operation(self, operation_id: str) -> Optional[RichProgressManager]:
        """Get existing progress manager"""
        return self.operations.get(operation_id)
    
    def set_active(self, operation_id: str) -> None:
        """Set active operation for UI focus"""
        with self._lock:
            if operation_id in self.operations:
                self.active_operation = operation_id
    
    def complete_operation(self, operation_id: str) -> None:
        """Mark operation as completed and clean up"""
        with self._lock:
            if operation_id in self.operations:
                manager = self.operations[operation_id]
                manager.complete()
                
                # Clear active if this was the active operation
                if self.active_operation == operation_id:
                    self.active_operation = None
                
                # Keep operation for a short time for debugging, then remove
                # In production, you might want to archive completed operations
    
    def cleanup(self) -> None:
        """Clean up all operations"""
        with self._lock:
            self.operations.clear()
            self.active_operation = None


# Global instance for system-wide Rich UI coordination
GLOBAL_RICH_PROGRESS = GlobalRichProgressManager()


def create_rich_progress_manager(operation_id: str, operation_name: str) -> RichProgressManager:
    """Convenience function to create a Rich progress manager"""
    return GLOBAL_RICH_PROGRESS.create_operation(operation_id, operation_name)


def get_rich_progress_manager(operation_id: str) -> Optional[RichProgressManager]:
    """Convenience function to get a Rich progress manager"""
    return GLOBAL_RICH_PROGRESS.get_operation(operation_id)


# Legacy compatibility functions
def create_progress_tracker(operation_id: str, operation_name: str):
    """Legacy compatibility: create Rich progress manager"""
    return create_rich_progress_manager(operation_id, operation_name)


def get_progress_tracker(operation_id: str):
    """Legacy compatibility: get Rich progress manager"""
    return get_rich_progress_manager(operation_id)