"""
Streaming Command Executor

A universal command execution utility that provides real-time output streaming
with Rich progress integration and intelligent output formatting.
"""

import subprocess
import time
import os
import pty
import select
import errno
import fcntl
import signal
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

try:
    from ..core.unified_logger import get_logger
    from ..core.rich_progress import RichProgressManager
    from ..core.sudo_manager import SudoPermissionManager
except ImportError:
    # Fallback for testing
    import logging
    get_logger = lambda name, module: logging.getLogger(f"{name}.{module}")
    RichProgressManager = None
    SudoPermissionManager = None


@dataclass
class CommandResult:
    """Result of command execution"""
    returncode: int
    stdout: str
    stderr: str
    execution_time: float = 0.0
    command: Optional[List[str]] = None


class StreamingCommandExecutor:
    """
    Universal streaming command executor with real-time output display.
    
    Features:
    - Real-time output streaming with line-by-line display
    - Rich Progress Manager integration
    - Intelligent output formatting with contextual icons
    - Comprehensive timeout and error handling
    - Compatible with existing subprocess patterns
    """
    
    def __init__(self, progress_manager: Optional[RichProgressManager] = None, logger=None):
        """
        Initialize the streaming command executor.
        
        Args:
            progress_manager: RichProgressManager for UI integration
            logger: Logger instance for debugging
        """
        self.progress_manager = progress_manager
        self.logger = logger or get_logger(__name__, "streaming_executor")
        
        # Initialize sudo manager for unified sudo status checking
        if SudoPermissionManager:
            self.sudo_manager = SudoPermissionManager(progress_manager)
        else:
            self.sudo_manager = None
    
    def execute_with_realtime_output(
        self,
        cmd: List[str],
        description: str,
        timeout: int = 300,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        merge_streams: bool = True,
        use_pty: bool = True,
        allow_password_prompt: bool = False
    ) -> CommandResult:
        """
        Execute command with real-time output streaming.
        
        Args:
            cmd: Command and arguments as list
            description: Human-readable description of the operation
            timeout: Timeout in seconds (default: 5 minutes)
            env: Environment variables
            cwd: Working directory
            merge_streams: Whether to merge stderr into stdout
            use_pty: Use pseudo-terminal for TTY-aware commands (default: True)
            allow_password_prompt: Allow interactive password prompts (default: False)
            
        Returns:
            CommandResult with execution details
            
        Raises:
            subprocess.TimeoutExpired: If command times out
            subprocess.SubprocessError: If command fails to start
        """
        start_time = time.time()
        
        # Smart sudo handling: detect if command needs password and adjust execution strategy
        needs_password = self._detect_sudo_password_requirement(cmd, allow_password_prompt)
        
        if use_pty:
            # Use enhanced bidirectional PTY for all PTY-enabled commands
            # This handles both cached sudo (no password needed) and interactive sudo (password prompting)
            if self.logger:
                if needs_password:
                    self.logger.debug("🔐 Using bidirectional PTY with password support")
                else:
                    self.logger.debug("✅ Using bidirectional PTY with cached sudo")
            return self._execute_with_pty(cmd, description, timeout, env, cwd, start_time)
        else:
            return self._execute_with_pipe(cmd, description, timeout, env, cwd, merge_streams, start_time)
    
    def _execute_with_pty(
        self,
        cmd: List[str],
        description: str,
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str],
        start_time: float
    ) -> CommandResult:
        """Execute command using single PTY session with intelligent sudo handling."""
        
        # Initialize progress tracking
        step_id = f"cmd_{int(time.time())}"
        if self.progress_manager:
            self.progress_manager.start_step(step_id, description)
        
        if self.logger:
            self.logger.debug("🔧 Using single PTY session for optimal sudo and progress bar support")
        
        try:
            # Create PTY
            master, slave = pty.openpty()
            
            # Set up proper terminal environment
            if env is None:
                env = os.environ.copy()
            
            env.update({
                'TERM': env.get('TERM', 'xterm-256color'),
                'COLUMNS': '120',
                'LINES': '30',
                'PATH': env.get('PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'),
                'SHELL': env.get('SHELL', '/bin/bash')
            })
            
            # Execute command in bash session within PTY
            # Properly handle shell escaping for complex commands
            if len(cmd) == 1:
                bash_command = cmd[0]
            else:
                # Escape individual arguments and join them
                import shlex
                bash_command = ' '.join(shlex.quote(arg) for arg in cmd)
            
            process = subprocess.Popen(
                ['bash', '-c', bash_command],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                cwd=cwd,
                preexec_fn=os.setsid  # Create new session
            )
            
            os.close(slave)  # Close child end
            
            # Collect output for logging
            output_buffer = []
            
            # Real-time I/O loop
            while process.poll() is None:
                # Check timeout
                if time.time() - start_time > timeout:
                    process.terminate()
                    if self.progress_manager:
                        self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Check for data with timeout
                ready, _, _ = select.select([master], [], [], 1.0)
                
                if master in ready:
                    try:
                        data = os.read(master, 1024)
                        if data:
                            decoded = data.decode('utf-8', errors='replace')
                            
                            # Check for sudo password prompt
                            if self._detect_sudo_prompt(decoded):
                                print(f"\n🔐 Detected sudo password prompt")
                                # Check if we're in an interactive environment
                                import sys
                                if sys.stdin.isatty():
                                    try:
                                        import getpass
                                        password = getpass.getpass("Please enter sudo password: ")
                                        os.write(master, (password + '\n').encode())
                                        print("Password sent, continuing...")
                                    except (KeyboardInterrupt, EOFError):
                                        print("\nPassword input cancelled")
                                        break
                                else:
                                    # Non-interactive environment - log and continue
                                    if self.logger:
                                        self.logger.warning("Sudo password prompt detected, but running in non-interactive environment")
                                    # Still display the decoded output so user sees the prompt
                                    sys.stdout.write(decoded)
                                    sys.stdout.flush()
                                    output_buffer.append(decoded)
                            else:
                                # Normal output - directly display (PTY handles \r correctly)
                                import sys
                                sys.stdout.write(decoded)
                                sys.stdout.flush()
                                output_buffer.append(decoded)
                                
                    except OSError as e:
                        if e.errno == 5:  # Input/output error - PTY closed
                            break
                        else:
                            if self.logger:
                                self.logger.debug(f"PTY read error: {e}")
            
            # Read remaining output
            try:
                while True:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if not ready:
                        break
                    data = os.read(master, 1024)
                    if not data:
                        break
                    decoded = data.decode('utf-8', errors='replace')
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
                    output_buffer.append(decoded)
            except OSError:
                pass
            
            # Wait for process completion
            process.wait()
            os.close(master)
            
            execution_time = time.time() - start_time
            
            # Update progress based on result
            if self.progress_manager:
                if process.returncode == 0:
                    self.progress_manager.complete_step(step_id)
                else:
                    error_msg = f"Command failed with exit code {process.returncode}"
                    self.progress_manager.fail_step(step_id, error_msg)
            
            # Create result
            stdout_combined = ''.join(output_buffer)
            
            result = CommandResult(
                returncode=process.returncode,
                stdout=stdout_combined,
                stderr='',  # PTY merges stderr into stdout
                execution_time=execution_time,
                command=cmd.copy()
            )
            
            if self.logger:
                self.logger.info(f"Single PTY session completed in {execution_time:.1f}s with return code {process.returncode}")
            
            return result
            
        except subprocess.TimeoutExpired:
            # Ensure process cleanup on timeout
            if 'process' in locals() and process.poll() is None:
                process.kill()
                process.wait()
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Single PTY session execution failed: {e}")
            # Fallback to pipe method
            if self.logger:
                self.logger.info("Falling back to pipe execution method")
            return self._execute_with_pipe(cmd, description, timeout, env, cwd, True, start_time)
    
    def _detect_sudo_prompt(self, output: str) -> bool:
        """Detect sudo password prompt in output"""
        output_lower = output.lower()
        sudo_prompts = ['password', '[sudo]', 'sorry, try again']
        return any(prompt in output_lower for prompt in sudo_prompts)
    
    def _execute_with_pipe(
        self,
        cmd: List[str],
        description: str,
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str],
        merge_streams: bool,
        start_time: float
    ) -> CommandResult:
        """Execute command using traditional pipes (fallback method)."""
        
        # Start process with appropriate stream configuration
        stderr_config = subprocess.STDOUT if merge_streams else subprocess.PIPE
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=stderr_config,
                stdin=None,
                text=True,
                bufsize=1,  # Line buffering for immediate output
                universal_newlines=True,
                env=env,
                cwd=cwd
            )
        except Exception as e:
            error_msg = f"Failed to start command {cmd}: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise subprocess.SubprocessError(error_msg)
        
        # Initialize progress tracking
        step_id = f"cmd_pipe_{int(time.time())}"
        if self.progress_manager:
            self.progress_manager.start_step(step_id, description)
        
        # Stream output in real-time
        output_lines = []
        error_lines = []
        
        try:
            # Read stdout in real-time
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    process.terminate()
                    if self.progress_manager:
                        self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
                    raise subprocess.TimeoutExpired(cmd, timeout)
                
                # Read one line from stdout
                line = process.stdout.readline()
                if not line:  # EOF, process finished
                    break
                
                # Preserve the original line exactly as received from command
                line_for_display = line  # Keep original with all control characters
                line_for_storage = line.rstrip('\n\r')  # Clean version for storage
                
                if line:  # Any line (including empty ones)
                    output_lines.append(line_for_storage)
                    
                    # Direct raw output - exactly as the command intended
                    import sys
                    sys.stdout.write(line_for_display)
                    sys.stdout.flush()
                    
                    # Debug logging (use cleaned version)
                    if self.logger:
                        self.logger.debug(f"Command output: {line_for_storage}")
            
            # If not merging streams, read stderr separately
            if not merge_streams and process.stderr:
                stderr_output = process.stderr.read()
                if stderr_output:
                    error_lines = stderr_output.strip().split('\n')
            
            # Wait for process completion
            process.wait()
            
            execution_time = time.time() - start_time
            
            # Update progress based on result
            if self.progress_manager:
                if process.returncode == 0:
                    self.progress_manager.complete_step(step_id)
                else:
                    error_msg = f"Command failed with exit code {process.returncode}"
                    self.progress_manager.fail_step(step_id, error_msg)
            
            # Create result
            stdout_combined = '\n'.join(output_lines)
            stderr_combined = '\n'.join(error_lines) if error_lines else ''
            
            result = CommandResult(
                returncode=process.returncode,
                stdout=stdout_combined,
                stderr=stderr_combined,
                execution_time=execution_time,
                command=cmd.copy()
            )
            
            if self.logger:
                self.logger.info(f"Command completed in {execution_time:.1f}s with return code {process.returncode}")
            
            return result
            
        except subprocess.TimeoutExpired:
            # Ensure process cleanup on timeout
            if process.poll() is None:
                process.kill()
                process.wait()
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
            raise
        except Exception as e:
            # Ensure process cleanup on any other exception
            if process.poll() is None:
                process.terminate()
                process.wait()
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command failed: {str(e)}")
            raise
    
    def set_progress_manager(self, progress_manager: RichProgressManager) -> None:
        """Set or update the progress manager"""
        self.progress_manager = progress_manager
    
    def set_logger(self, logger) -> None:
        """Set or update the logger"""
        self.logger = logger
    
    def _detect_sudo_password_requirement(self, cmd: List[str], allow_password_prompt: bool) -> bool:
        """
        Detect if command contains sudo that requires password prompt.
        
        Args:
            cmd: Command list to analyze
            allow_password_prompt: Whether password prompts are allowed
            
        Returns:
            True if command needs password input, False otherwise
        """
        if not cmd or len(cmd) == 0:
            return False
            
        # Check if command starts with sudo
        if cmd[0] == 'sudo':
            # Check for -n flag (non-interactive)
            if '-n' in cmd:
                # -n flag means fail if password required, so no password prompt expected
                return False
            elif allow_password_prompt:
                # Use unified sudo manager for status checking
                if self.sudo_manager:
                    has_cached_access = self.sudo_manager.check_sudo_status()
                    
                    if has_cached_access:
                        if self.logger:
                            self.logger.debug("✅ Sudo access available (cached) - using PTY mode")
                        return False
                    else:
                        if self.logger:
                            self.logger.debug("🔐 Sudo requires password - using interactive mode")
                        return True
                else:
                    # Fallback to inline check if sudo_manager unavailable
                    try:
                        import subprocess
                        result = subprocess.run(['sudo', '-n', 'true'], 
                                              capture_output=True, timeout=3)
                        has_cached_access = result.returncode == 0
                        
                        if has_cached_access:
                            if self.logger:
                                self.logger.debug("✅ Sudo access available (cached) - using PTY mode")
                            return False
                        else:
                            if self.logger:
                                self.logger.debug("🔐 Sudo requires password - using interactive mode")
                            return True
                    except:
                        if self.logger:
                            self.logger.debug("⚠️  Sudo check failed - assuming password needed")
                        return True
            else:
                # Password prompts not allowed, so we should modify command to use -n
                return False
        
        return False
    
    def _execute_with_pty_password(
        self,
        cmd: List[str],
        description: str,
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str],
        start_time: float,
        allow_password_prompt: bool
    ) -> CommandResult:
        """
        Execute sudo command with PTY that preserves password prompt capability.
        
        This method handles the tricky case where we want PTY for progress bars
        but also need to allow password input for sudo commands.
        """
        if self.logger:
            self.logger.info(f"🔐 Executing sudo command with password prompt capability")
        
        # For commands that need password input, fall back to simple subprocess execution
        # This ensures password prompts work correctly, but progress bars may flood the screen
        if self.logger:
            self.logger.info("🔐 Using simple subprocess execution for password compatibility")
            self.logger.warning("⚠️  Progress bars may flood screen for password-required commands")
        
        # Remove -n flag if present and ensure interactive mode
        modified_cmd = []
        i = 0
        while i < len(cmd):
            if cmd[i] == '-n' and i > 0 and cmd[i-1] == 'sudo':
                # Skip -n flag to allow password prompt
                pass
            else:
                modified_cmd.append(cmd[i])
            i += 1
        
        # Use simple subprocess.run with direct terminal access for password input
        return self._execute_with_direct_terminal(modified_cmd, description, timeout, env, cwd, start_time)
    
    def _execute_with_direct_terminal(
        self,
        cmd: List[str],
        description: str,
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str],
        start_time: float
    ) -> CommandResult:
        """
        Execute command with direct terminal access for password input.
        This method gives up real-time output streaming to ensure password prompts work.
        """
        
        # Initialize progress tracking
        step_id = f"cmd_direct_{int(time.time())}"
        if self.progress_manager:
            self.progress_manager.start_step(step_id, description)
        
        try:
            if self.logger:
                self.logger.info(f"🖥️  Executing with direct terminal: {' '.join(cmd)}")
            
            # Use subprocess.run with direct terminal access
            # This will allow password prompts to work properly
            import sys
            process = subprocess.run(
                cmd,
                env=env,
                cwd=cwd,
                timeout=timeout,
                stdin=sys.stdin,   # Explicitly connect to terminal stdin
                stdout=sys.stdout, # Explicitly connect to terminal stdout
                stderr=sys.stderr, # Explicitly connect to terminal stderr
                text=True
            )
            
            execution_time = time.time() - start_time
            
            # Update progress
            if self.progress_manager:
                if process.returncode == 0:
                    self.progress_manager.complete_step(step_id)
                else:
                    error_msg = f"Command failed with exit code {process.returncode}"
                    self.progress_manager.fail_step(step_id, error_msg)
            
            # Create result (no output capture for direct terminal execution)
            result = CommandResult(
                returncode=process.returncode,
                stdout="",  # No output captured in direct mode
                stderr="",  # No error output captured
                execution_time=execution_time,
                command=cmd.copy()
            )
            
            if self.logger:
                self.logger.info(f"Direct terminal command completed in {execution_time:.1f}s with return code {process.returncode}")
            
            return result
            
        except subprocess.TimeoutExpired:
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Direct terminal execution failed: {e}")
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command failed: {str(e)}")
            raise
    
    def _execute_with_interactive_pty(
        self,
        cmd: List[str],
        description: str,
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str],
        start_time: float
    ) -> CommandResult:
        """
        Execute command with full TTY support for interactive input like passwords.
        This method gives the process full control of the terminal for password input.
        """
        
        # Initialize progress tracking
        step_id = f"cmd_interactive_{int(time.time())}"
        if self.progress_manager:
            self.progress_manager.start_step(step_id, description)
        
        try:
            # Use pty.spawn for full TTY control, but capture output
            import tempfile
            output_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
            error_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
            
            try:
                # For interactive commands, we need to let the user interact directly
                # but we can still capture some output using a hybrid approach
                if self.logger:
                    self.logger.info(f"🔐 Executing interactive command: {' '.join(cmd)}")
                
                # Execute with full terminal access
                # Use script command to capture output while preserving TTY
                script_cmd = ['script', '-qec', ' '.join(cmd), '/dev/null']
                
                process = subprocess.Popen(
                    script_cmd,
                    stdin=None,  # Use real terminal stdin
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=cwd,
                    text=True
                )
                
                # Read output in real-time
                output_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())  # Show output in real-time
                        output_lines.append(output.strip())
                
                # Wait for completion
                stdout, stderr = process.communicate()
                
                execution_time = time.time() - start_time
                
                # Update progress
                if self.progress_manager:
                    if process.returncode == 0:
                        self.progress_manager.complete_step(step_id)
                    else:
                        error_msg = f"Interactive command failed with exit code {process.returncode}"
                        self.progress_manager.fail_step(step_id, error_msg)
                
                # Create result
                all_output = '\n'.join(output_lines) + '\n' + (stdout or '')
                
                result = CommandResult(
                    returncode=process.returncode,
                    stdout=all_output,
                    stderr=stderr or '',
                    execution_time=execution_time,
                    command=cmd.copy()
                )
                
                if self.logger:
                    self.logger.info(f"Interactive command completed in {execution_time:.1f}s with return code {process.returncode}")
                
                return result
                
            finally:
                # Cleanup temp files
                try:
                    import os
                    os.unlink(output_file.name)
                    os.unlink(error_file.name)
                except:
                    pass
        except subprocess.TimeoutExpired:
            # Ensure process cleanup on timeout
            if process.poll() is None:
                process.kill()
                process.wait()
            if self.progress_manager:
                self.progress_manager.fail_step(step_id, f"Command timed out after {timeout}s")
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"Interactive PTY execution failed: {e}")
            # Final fallback to pipe method
            if self.logger:
                self.logger.info("Falling back to pipe method")
            return self._execute_with_pipe(cmd, description, timeout, env, cwd, True, start_time)


# Convenience functions for backward compatibility
def create_streaming_executor(progress_manager=None, logger=None) -> StreamingCommandExecutor:
    """Create a new StreamingCommandExecutor instance"""
    return StreamingCommandExecutor(progress_manager=progress_manager, logger=logger)


def execute_command_with_streaming(
    cmd: List[str],
    description: str,
    timeout: int = 300,
    progress_manager=None,
    logger=None,
    **kwargs
) -> CommandResult:
    """
    Convenience function to execute a single command with streaming output.
    
    Args:
        cmd: Command and arguments
        description: Operation description
        timeout: Timeout in seconds
        progress_manager: RichProgressManager instance
        logger: Logger instance
        **kwargs: Additional arguments passed to execute_with_realtime_output
        
    Returns:
        CommandResult
    """
    executor = StreamingCommandExecutor(progress_manager=progress_manager, logger=logger)
    return executor.execute_with_realtime_output(
        cmd=cmd,
        description=description,
        timeout=timeout,
        **kwargs
    )