"""
User Manager

This module provides user account management capabilities for cyber ranges,
including user creation, modification, and access control.
"""

import logging
import crypt
import secrets
import string
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from .ssh_manager import SSHManager, SSHCredentials, SSHCommand


class UserRole(Enum):
    """User roles in cyber range"""
    ADMIN = "admin"
    INSTRUCTOR = "instructor"
    STUDENT = "student"
    GUEST = "guest"


@dataclass
class UserAccount:
    """Represents a user account"""
    username: str
    full_name: str
    role: UserRole
    password_hash: Optional[str] = None
    ssh_public_keys: List[str] = field(default_factory=list)
    groups: Set[str] = field(default_factory=set)
    home_directory: Optional[str] = None
    shell: str = "/bin/bash"
    sudo_access: bool = False
    account_enabled: bool = True
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserGroup:
    """Represents a user group"""
    group_name: str
    description: str
    members: Set[str] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


class UserManager:
    """
    User account and access management service.
    
    This service manages user accounts, groups, and permissions across
    cyber range virtual machines and hosts.
    
    Capabilities:
    - User account creation and management
    - Group management and membership
    - Password management and policies
    - SSH key management
    - Sudo access control
    - Cross-host user synchronization
    - Role-based access control
    
    Follows SOLID principles:
    - Single Responsibility: Focuses on user management
    - Open/Closed: Extensible authentication and authorization
    - Interface Segregation: Focused user management interface
    - Dependency Inversion: Uses abstract SSH interface
    """
    
    def __init__(
        self,
        ssh_manager: SSHManager,
        config_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize user manager.
        
        Args:
            ssh_manager: SSH manager for remote operations
            config_dir: Directory to store user configurations
            logger: Optional logger instance
        """
        self.ssh_manager = ssh_manager
        self.config_dir = Path(config_dir) if config_dir else Path("/tmp/cyris/users")
        self.logger = logger or logging.getLogger(__name__)
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # User and group registries
        self._users: Dict[str, UserAccount] = {}
        self._groups: Dict[str, UserGroup] = {}
        
        # Password policy
        self.password_policy = {
            "min_length": 8,
            "require_uppercase": True,
            "require_lowercase": True,
            "require_numbers": True,
            "require_special": True,
            "forbid_common_passwords": True
        }
        
        # Default groups for roles
        self.default_role_groups = {
            UserRole.ADMIN: {"wheel", "sudo", "adm"},
            UserRole.INSTRUCTOR: {"instructors", "cyris-instructors"},
            UserRole.STUDENT: {"students", "cyris-students"},
            UserRole.GUEST: {"guests", "cyris-guests"}
        }
        
        self.logger.info("UserManager initialized")
    
    def create_user(
        self,
        username: str,
        full_name: str,
        role: UserRole,
        password: Optional[str] = None,
        ssh_public_keys: Optional[List[str]] = None,
        custom_groups: Optional[Set[str]] = None,
        sudo_access: Optional[bool] = None,
        home_directory: Optional[str] = None
    ) -> UserAccount:
        """
        Create a new user account.
        
        Args:
            username: Username
            full_name: Full name of the user
            role: User role
            password: Password (will be generated if not provided)
            ssh_public_keys: List of SSH public keys
            custom_groups: Additional groups beyond default role groups
            sudo_access: Override default sudo access for role
            home_directory: Custom home directory path
        
        Returns:
            Created user account
        
        Raises:
            ValueError: If user already exists or invalid parameters
        """
        if username in self._users:
            raise ValueError(f"User '{username}' already exists")
        
        # Validate username
        if not self._validate_username(username):
            raise ValueError(f"Invalid username '{username}'")
        
        # Generate password if not provided
        if not password:
            password = self.generate_password()
        
        # Validate password
        if not self._validate_password(password):
            raise ValueError("Password does not meet policy requirements")
        
        # Hash password
        password_hash = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
        
        # Determine sudo access
        if sudo_access is None:
            sudo_access = role in [UserRole.ADMIN, UserRole.INSTRUCTOR]
        
        # Determine groups
        groups = set(custom_groups) if custom_groups else set()
        groups.update(self.default_role_groups.get(role, set()))
        
        # Create user account
        user = UserAccount(
            username=username,
            full_name=full_name,
            role=role,
            password_hash=password_hash,
            ssh_public_keys=ssh_public_keys or [],
            groups=groups,
            home_directory=home_directory or f"/home/{username}",
            sudo_access=sudo_access
        )
        
        # Register user
        self._users[username] = user
        
        # Save configuration
        self._save_user_config(user)
        
        self.logger.info(f"Created user account: {username} ({role.value})")
        return user
    
    def create_user_on_hosts(
        self,
        username: str,
        host_credentials: List[SSHCredentials]
    ) -> Dict[str, bool]:
        """
        Create user account on remote hosts.
        
        Args:
            username: Username to create
            host_credentials: List of host credentials
        
        Returns:
            Dictionary mapping hostname to success status
        """
        user = self._users.get(username)
        if not user:
            raise ValueError(f"User '{username}' not found in registry")
        
        results = {}
        
        for credentials in host_credentials:
            try:
                success = self._create_user_on_host(user, credentials)
                results[credentials.hostname] = success
                
                if success:
                    self.logger.info(f"Created user {username} on {credentials.hostname}")
                else:
                    self.logger.error(f"Failed to create user {username} on {credentials.hostname}")
                    
            except Exception as e:
                self.logger.error(f"Error creating user {username} on {credentials.hostname}: {e}")
                results[credentials.hostname] = False
        
        return results
    
    def modify_user(
        self,
        username: str,
        full_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        password: Optional[str] = None,
        ssh_public_keys: Optional[List[str]] = None,
        groups: Optional[Set[str]] = None,
        sudo_access: Optional[bool] = None,
        account_enabled: Optional[bool] = None
    ) -> UserAccount:
        """
        Modify existing user account.
        
        Args:
            username: Username to modify
            full_name: New full name
            role: New role
            password: New password
            ssh_public_keys: New SSH public keys
            groups: New groups
            sudo_access: New sudo access setting
            account_enabled: Enable/disable account
        
        Returns:
            Modified user account
        
        Raises:
            ValueError: If user not found
        """
        user = self._users.get(username)
        if not user:
            raise ValueError(f"User '{username}' not found")
        
        # Update fields
        if full_name is not None:
            user.full_name = full_name
        
        if role is not None:
            user.role = role
            # Update default groups for new role
            user.groups.update(self.default_role_groups.get(role, set()))
        
        if password is not None:
            if not self._validate_password(password):
                raise ValueError("Password does not meet policy requirements")
            user.password_hash = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
        
        if ssh_public_keys is not None:
            user.ssh_public_keys = ssh_public_keys
        
        if groups is not None:
            user.groups = groups
        
        if sudo_access is not None:
            user.sudo_access = sudo_access
        
        if account_enabled is not None:
            user.account_enabled = account_enabled
        
        # Save configuration
        self._save_user_config(user)
        
        self.logger.info(f"Modified user account: {username}")
        return user
    
    def delete_user(self, username: str) -> bool:
        """
        Delete user account from registry.
        
        Args:
            username: Username to delete
        
        Returns:
            True if successful, False if user not found
        """
        if username not in self._users:
            return False
        
        # Remove from registry
        del self._users[username]
        
        # Remove configuration file
        config_file = self.config_dir / f"user_{username}.json"
        if config_file.exists():
            config_file.unlink()
        
        self.logger.info(f"Deleted user account: {username}")
        return True
    
    def delete_user_from_hosts(
        self,
        username: str,
        host_credentials: List[SSHCredentials],
        remove_home: bool = False
    ) -> Dict[str, bool]:
        """
        Delete user account from remote hosts.
        
        Args:
            username: Username to delete
            host_credentials: List of host credentials
            remove_home: Whether to remove home directory
        
        Returns:
            Dictionary mapping hostname to success status
        """
        results = {}
        
        for credentials in host_credentials:
            try:
                success = self._delete_user_from_host(username, credentials, remove_home)
                results[credentials.hostname] = success
                
                if success:
                    self.logger.info(f"Deleted user {username} from {credentials.hostname}")
                else:
                    self.logger.error(f"Failed to delete user {username} from {credentials.hostname}")
                    
            except Exception as e:
                self.logger.error(f"Error deleting user {username} from {credentials.hostname}: {e}")
                results[credentials.hostname] = False
        
        return results
    
    def create_group(
        self,
        group_name: str,
        description: str,
        members: Optional[Set[str]] = None,
        permissions: Optional[Set[str]] = None
    ) -> UserGroup:
        """
        Create a new user group.
        
        Args:
            group_name: Name of the group
            description: Group description
            members: Initial group members
            permissions: Group permissions
        
        Returns:
            Created user group
        
        Raises:
            ValueError: If group already exists
        """
        if group_name in self._groups:
            raise ValueError(f"Group '{group_name}' already exists")
        
        group = UserGroup(
            group_name=group_name,
            description=description,
            members=members or set(),
            permissions=permissions or set()
        )
        
        # Register group
        self._groups[group_name] = group
        
        # Save configuration
        self._save_group_config(group)
        
        self.logger.info(f"Created group: {group_name}")
        return group
    
    def add_user_to_group(self, username: str, group_name: str) -> bool:
        """
        Add user to group.
        
        Args:
            username: Username
            group_name: Group name
        
        Returns:
            True if successful, False otherwise
        """
        user = self._users.get(username)
        group = self._groups.get(group_name)
        
        if not user:
            self.logger.error(f"User '{username}' not found")
            return False
        
        if not group:
            self.logger.error(f"Group '{group_name}' not found")
            return False
        
        # Add to group
        group.members.add(username)
        user.groups.add(group_name)
        
        # Save configurations
        self._save_user_config(user)
        self._save_group_config(group)
        
        self.logger.info(f"Added user {username} to group {group_name}")
        return True
    
    def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """
        Remove user from group.
        
        Args:
            username: Username
            group_name: Group name
        
        Returns:
            True if successful, False otherwise
        """
        user = self._users.get(username)
        group = self._groups.get(group_name)
        
        if not user or not group:
            return False
        
        # Remove from group
        group.members.discard(username)
        user.groups.discard(group_name)
        
        # Save configurations
        self._save_user_config(user)
        self._save_group_config(group)
        
        self.logger.info(f"Removed user {username} from group {group_name}")
        return True
    
    def generate_password(self, length: int = 12) -> str:
        """
        Generate a secure password.
        
        Args:
            length: Password length
        
        Returns:
            Generated password
        """
        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        numbers = string.digits
        special = "!@#$%^&*"
        
        # Ensure password contains at least one from each required set
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(numbers),
            secrets.choice(special)
        ]
        
        # Fill remaining length with random characters
        all_chars = lowercase + uppercase + numbers + special
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # Shuffle the password list
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)
    
    def get_user(self, username: str) -> Optional[UserAccount]:
        """Get user account by username"""
        return self._users.get(username)
    
    def list_users(
        self,
        role: Optional[UserRole] = None,
        enabled_only: bool = True
    ) -> List[UserAccount]:
        """
        List user accounts.
        
        Args:
            role: Filter by role
            enabled_only: Only return enabled accounts
        
        Returns:
            List of user accounts
        """
        users = list(self._users.values())
        
        if role:
            users = [u for u in users if u.role == role]
        
        if enabled_only:
            users = [u for u in users if u.account_enabled]
        
        return users
    
    def get_group(self, group_name: str) -> Optional[UserGroup]:
        """Get group by name"""
        return self._groups.get(group_name)
    
    def list_groups(self) -> List[UserGroup]:
        """List all groups"""
        return list(self._groups.values())
    
    def sync_users_to_hosts(
        self,
        host_credentials: List[SSHCredentials],
        usernames: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, bool]]:
        """
        Synchronize users to multiple hosts.
        
        Args:
            host_credentials: List of host credentials
            usernames: Specific users to sync (all if None)
        
        Returns:
            Nested dictionary: {hostname: {username: success_status}}
        """
        users_to_sync = usernames or list(self._users.keys())
        results = {}
        
        for credentials in host_credentials:
            hostname = credentials.hostname
            results[hostname] = {}
            
            for username in users_to_sync:
                try:
                    success = self.create_user_on_hosts(username, [credentials])[hostname]
                    results[hostname][username] = success
                except Exception as e:
                    self.logger.error(f"Error syncing user {username} to {hostname}: {e}")
                    results[hostname][username] = False
        
        return results
    
    def get_user_manager_stats(self) -> Dict[str, Any]:
        """Get user manager statistics"""
        user_stats = {}
        for role in UserRole:
            user_stats[role.value] = len([u for u in self._users.values() if u.role == role])
        
        return {
            "total_users": len(self._users),
            "enabled_users": len([u for u in self._users.values() if u.account_enabled]),
            "total_groups": len(self._groups),
            "users_by_role": user_stats,
            "config_directory": str(self.config_dir)
        }
    
    def _create_user_on_host(self, user: UserAccount, credentials: SSHCredentials) -> bool:
        """Create user account on a specific host"""
        commands = []
        
        # Create user with home directory
        useradd_cmd = f"useradd -m -s {user.shell} -c '{user.full_name}' {user.username}"
        if user.home_directory and user.home_directory != f"/home/{user.username}":
            useradd_cmd += f" -d {user.home_directory}"
        
        commands.append(SSHCommand(useradd_cmd, "Create user account"))
        
        # Set password
        if user.password_hash:
            commands.append(SSHCommand(
                f"echo '{user.username}:{user.password_hash}' | chpasswd -e",
                "Set user password"
            ))
        
        # Add to groups
        for group in user.groups:
            commands.append(SSHCommand(
                f"groupadd -f {group}; usermod -a -G {group} {user.username}",
                f"Add user to group {group}"
            ))
        
        # Configure sudo access
        if user.sudo_access:
            commands.append(SSHCommand(
                f"echo '{user.username} ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/{user.username}",
                "Configure sudo access"
            ))
        
        # Install SSH keys
        if user.ssh_public_keys:
            ssh_dir = f"{user.home_directory}/.ssh"
            commands.extend([
                SSHCommand(f"mkdir -p {ssh_dir}", "Create SSH directory"),
                SSHCommand(f"chmod 700 {ssh_dir}", "Set SSH directory permissions"),
                SSHCommand(f"chown {user.username}:{user.username} {ssh_dir}", "Set SSH directory ownership")
            ])
            
            for key in user.ssh_public_keys:
                commands.append(SSHCommand(
                    f"echo '{key}' >> {ssh_dir}/authorized_keys",
                    "Add SSH public key"
                ))
            
            commands.extend([
                SSHCommand(f"chmod 600 {ssh_dir}/authorized_keys", "Set authorized_keys permissions"),
                SSHCommand(f"chown {user.username}:{user.username} {ssh_dir}/authorized_keys", "Set authorized_keys ownership")
            ])
        
        # Execute all commands
        for command in commands:
            result = self.ssh_manager.execute_command(credentials, command)
            if not result.success and "already exists" not in result.stderr:
                self.logger.error(f"Failed to execute: {command.command} - {result.stderr}")
                return False
        
        return True
    
    def _delete_user_from_host(
        self,
        username: str,
        credentials: SSHCredentials,
        remove_home: bool
    ) -> bool:
        """Delete user from a specific host"""
        # Build userdel command
        userdel_cmd = f"userdel {'-r' if remove_home else ''} {username}"
        
        # Remove sudo configuration
        sudo_cleanup = f"rm -f /etc/sudoers.d/{username}"
        
        commands = [
            SSHCommand(sudo_cleanup, "Remove sudo configuration", ignore_errors=True),
            SSHCommand(userdel_cmd, "Delete user account", ignore_errors=True)
        ]
        
        success = True
        for command in commands:
            result = self.ssh_manager.execute_command(credentials, command)
            if not result.success and "does not exist" not in result.stderr:
                self.logger.error(f"Failed to execute: {command.command} - {result.stderr}")
                success = False
        
        return success
    
    def _validate_username(self, username: str) -> bool:
        """Validate username format"""
        import re
        # Username must start with letter, contain only letters, numbers, underscore, hyphen
        return bool(re.match(r'^[a-z][a-z0-9_-]*$', username)) and len(username) <= 32
    
    def _validate_password(self, password: str) -> bool:
        """Validate password against policy"""
        policy = self.password_policy
        
        if len(password) < policy["min_length"]:
            return False
        
        if policy["require_uppercase"] and not any(c.isupper() for c in password):
            return False
        
        if policy["require_lowercase"] and not any(c.islower() for c in password):
            return False
        
        if policy["require_numbers"] and not any(c.isdigit() for c in password):
            return False
        
        if policy["require_special"] and not any(c in "!@#$%^&*" for c in password):
            return False
        
        # Check against common passwords
        if policy["forbid_common_passwords"]:
            common_passwords = {"password", "123456", "admin", "root", "user"}
            if password.lower() in common_passwords:
                return False
        
        return True
    
    def _save_user_config(self, user: UserAccount) -> None:
        """Save user configuration to file"""
        config_data = {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.value,
            "password_hash": user.password_hash,
            "ssh_public_keys": user.ssh_public_keys,
            "groups": list(user.groups),
            "home_directory": user.home_directory,
            "shell": user.shell,
            "sudo_access": user.sudo_access,
            "account_enabled": user.account_enabled,
            "expires_at": user.expires_at,
            "metadata": user.metadata
        }
        
        config_file = self.config_dir / f"user_{user.username}.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def _save_group_config(self, group: UserGroup) -> None:
        """Save group configuration to file"""
        config_data = {
            "group_name": group.group_name,
            "description": group.description,
            "members": list(group.members),
            "permissions": list(group.permissions),
            "metadata": group.metadata
        }
        
        config_file = self.config_dir / f"group_{group.group_name}.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)