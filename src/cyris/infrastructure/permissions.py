"""
Permission Management for CyRIS

This module handles automatic permission management for libvirt access,
ensuring that virtual machines can access disk files and directories
without manual ACL configuration.
"""
# import logging  # Replaced with unified logger
from cyris.core.unified_logger import get_logger
import os
import pwd
import grp
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any


logger = get_logger(__name__, "permissions")


class PermissionManager:
    """
    Manages file and directory permissions for libvirt access.
    
    This class automatically handles the common permission issues that occur
    when using libvirt system mode (qemu:///system) with user-created files.
    """
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize permission manager.
        
        Args:
            dry_run: If True, only log what would be done without executing
        """
        self.dry_run = dry_run
        self.libvirt_user = self._get_libvirt_user()
        self.logger = logger
        
    def _get_libvirt_user(self) -> Optional[str]:
        """Get the libvirt-qemu user name if it exists."""
        try:
            pwd.getpwnam('libvirt-qemu')
            return 'libvirt-qemu'
        except KeyError:
            # Check for alternative names
            for user_name in ['libvirt', 'qemu']:
                try:
                    pwd.getpwnam(user_name)
                    return user_name
                except KeyError:
                    continue
            return None
    
    def _run_command(self, cmd: List[str], description: str) -> bool:
        """
        Run a command with logging.
        
        Args:
            cmd: Command to run
            description: Description for logging
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.debug(f"{description}: {' '.join(cmd)}")
        
        if self.dry_run:
            self.logger.info(f"DRY RUN: {description}")
            return True
            
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            if result.returncode == 0:
                self.logger.debug(f"Successfully {description.lower()}")
                return True
            else:
                self.logger.warning(f"Failed to {description.lower()}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error {description.lower()}: {e}")
            return False
    
    def setup_libvirt_access(self, path: Path) -> bool:
        """
        Set up libvirt access for a file or directory.
        
        This method ensures that the libvirt-qemu user can access the
        specified path by:
        1. Setting ACL permissions on the path itself
        2. Ensuring parent directories are traversable
        3. Setting appropriate default ACLs for directories
        
        Args:
            path: Path to file or directory
            
        Returns:
            True if successful, False otherwise
        """
        if not self.libvirt_user:
            self.logger.warning("No libvirt user found, skipping permission setup")
            return False
            
        if not path.exists():
            self.logger.warning(f"Path does not exist: {path}")
            return False
        
        success = True
        
        # Set ACL for the target path
        if path.is_dir():
            # Directory: rwx (read, write, execute)
            success &= self._set_acl(path, self.libvirt_user, "rwx")
            # Set default ACL for future files
            success &= self._set_default_acl(path, self.libvirt_user, "rwx")
        else:
            # File: rw (read, write)  
            success &= self._set_acl(path, self.libvirt_user, "rw")
        
        # Ensure parent directories are traversable
        success &= self._ensure_path_traversable(path)
        
        return success
    
    def _set_acl(self, path: Path, user: str, permissions: str) -> bool:
        """Set ACL for user on path."""
        cmd = ["setfacl", "-m", f"u:{user}:{permissions}", str(path)]
        return self._run_command(cmd, f"Set ACL u:{user}:{permissions} on {path}")
    
    def _set_default_acl(self, path: Path, user: str, permissions: str) -> bool:
        """Set default ACL for user on directory."""
        if not path.is_dir():
            return True
            
        cmd = ["setfacl", "-d", "-m", f"u:{user}:{permissions}", str(path)]
        return self._run_command(cmd, f"Set default ACL u:{user}:{permissions} on {path}")
    
    def _ensure_path_traversable(self, path: Path) -> bool:
        """Ensure all parent directories are traversable by libvirt user."""
        success = True
        
        # Check each parent directory in the path
        current_path = path.parent if path.is_file() else path
        
        while current_path != current_path.parent:  # Stop at filesystem root
            # Only set execute permission for traversal
            success &= self._set_acl(current_path, self.libvirt_user, "rx")
            current_path = current_path.parent
            
            # Stop at common boundaries to avoid setting ACL on system directories
            if current_path.name in ['home', 'var', 'tmp']:
                break
        
        return success
    
    def setup_cyris_environment(self, base_path: Path) -> bool:
        """
        Set up permissions for the entire CyRIS environment.
        
        This method sets up permissions for:
        - Base CyRIS directory
        - Cyber range directory  
        - Images directory
        - Any existing range directories
        
        Args:
            base_path: Base CyRIS installation path
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Setting up CyRIS environment permissions")
        
        success = True
        
        # Set up base directories
        directories = [
            base_path,
            base_path / "cyber_range", 
            base_path / "images"
        ]
        
        for directory in directories:
            if directory.exists():
                success &= self.setup_libvirt_access(directory)
            else:
                self.logger.debug(f"Directory does not exist, skipping: {directory}")
        
        # Set up existing range directories
        cyber_range_dir = base_path / "cyber_range"
        if cyber_range_dir.exists():
            for range_dir in cyber_range_dir.iterdir():
                if range_dir.is_dir():
                    success &= self.setup_libvirt_access(range_dir)
                    
                    # Also set up disk directories
                    disks_dir = range_dir / "disks"
                    if disks_dir.exists():
                        success &= self.setup_libvirt_access(disks_dir)
        
        # Set up base images  
        images_dir = base_path / "images"
        if images_dir.exists():
            for img_file in images_dir.glob("*.qcow2"):
                success &= self.setup_libvirt_access(img_file)
        
        if success:
            self.logger.info("Successfully set up CyRIS environment permissions")
        else:
            self.logger.warning("Some permission setups failed")
            
        return success
    
    def check_libvirt_compatibility(self) -> Dict[str, Any]:
        """
        Check system compatibility for libvirt permissions.
        
        Returns:
            Dictionary with compatibility information
        """
        info = {
            "libvirt_user": self.libvirt_user,
            "acl_supported": self._check_acl_support(),
            "current_user_groups": self._get_current_user_groups(),
            "recommendations": []
        }
        
        if not info["libvirt_user"]:
            info["recommendations"].append("Install libvirt-daemon-system package")
        
        if not info["acl_supported"]:
            info["recommendations"].append("Install acl package for permission management")
        
        if "libvirt" not in info["current_user_groups"]:
            info["recommendations"].append("Add current user to libvirt group: sudo usermod -a -G libvirt $USER")
        
        return info
    
    def _check_acl_support(self) -> bool:
        """Check if ACL commands are available."""
        try:
            subprocess.run(["which", "setfacl"], capture_output=True, check=True)
            subprocess.run(["which", "getfacl"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _get_current_user_groups(self) -> List[str]:
        """Get list of groups for current user."""
        try:
            user = pwd.getpwuid(os.getuid()).pw_name
            groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
            # Also add primary group
            groups.append(grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name)
            return list(set(groups))
        except Exception as e:
            self.logger.error(f"Failed to get user groups: {e}")
            return []


def setup_permissions_for_file(file_path: Path, dry_run: bool = False) -> bool:
    """
    Convenience function to set up permissions for a single file.
    
    Args:
        file_path: Path to file or directory
        dry_run: If True, only log what would be done
        
    Returns:
        True if successful, False otherwise
    """
    manager = PermissionManager(dry_run=dry_run)
    return manager.setup_libvirt_access(file_path)


def setup_cyris_permissions(base_path: Path, dry_run: bool = False) -> bool:
    """
    Convenience function to set up permissions for CyRIS environment.
    
    Args:
        base_path: Base CyRIS installation path
        dry_run: If True, only log what would be done
        
    Returns:
        True if successful, False otherwise  
    """
    manager = PermissionManager(dry_run=dry_run)
    return manager.setup_cyris_environment(base_path)