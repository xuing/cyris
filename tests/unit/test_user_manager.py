#!/usr/bin/env python3

"""
Comprehensive tests for User Manager
Following TDD principles: test real functionality where possible, mock only external dependencies
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Set

import sys
sys.path.insert(0, '/home/ubuntu/cyris/src')

from cyris.tools.user_manager import (
    UserManager, UserAccount, UserGroup, UserRole
)
from cyris.tools.ssh_manager import SSHManager, SSHCredentials, SSHResult


class TestUserRole:
    """Test user role enumeration"""
    
    def test_user_roles(self):
        """Test all user role values"""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.INSTRUCTOR.value == "instructor"
        assert UserRole.STUDENT.value == "student"
        assert UserRole.GUEST.value == "guest"


class TestUserAccount:
    """Test UserAccount dataclass"""
    
    def test_user_account_creation_minimal(self):
        """Test user account creation with minimal parameters"""
        user = UserAccount(
            username="testuser",
            full_name="Test User",
            role=UserRole.STUDENT
        )
        
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.role == UserRole.STUDENT
        assert user.password_hash is None
        assert user.ssh_public_keys == []
        assert user.groups == set()
        assert user.home_directory is None
        assert user.shell == "/bin/bash"
        assert user.sudo_access is False
        assert user.account_enabled is True
        assert user.expires_at is None
        assert user.metadata == {}
    
    def test_user_account_creation_full(self):
        """Test user account creation with all parameters"""
        user = UserAccount(
            username="admin",
            full_name="Administrator",
            role=UserRole.ADMIN,
            password_hash="$6$salt$hash",
            ssh_public_keys=["ssh-rsa AAAA..."],
            groups={"wheel", "sudo"},
            home_directory="/home/admin",
            shell="/bin/zsh",
            sudo_access=True,
            account_enabled=True,
            expires_at="2025-12-31",
            metadata={"created_by": "system"}
        )
        
        assert user.username == "admin"
        assert user.full_name == "Administrator"
        assert user.role == UserRole.ADMIN
        assert user.password_hash == "$6$salt$hash"
        assert user.ssh_public_keys == ["ssh-rsa AAAA..."]
        assert user.groups == {"wheel", "sudo"}
        assert user.home_directory == "/home/admin"
        assert user.shell == "/bin/zsh"
        assert user.sudo_access is True
        assert user.account_enabled is True
        assert user.expires_at == "2025-12-31"
        assert user.metadata == {"created_by": "system"}


class TestUserGroup:
    """Test UserGroup dataclass"""
    
    def test_user_group_creation(self):
        """Test user group creation"""
        group = UserGroup(
            group_name="developers",
            description="Software developers",
            members={"user1", "user2"},
            permissions={"read", "write"},
            metadata={"department": "engineering"}
        )
        
        assert group.group_name == "developers"
        assert group.description == "Software developers"
        assert group.members == {"user1", "user2"}
        assert group.permissions == {"read", "write"}
        assert group.metadata == {"department": "engineering"}


class TestUserManagerBasics:
    """Test User Manager basic functionality"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for user configurations"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_ssh_manager(self):
        """Create mock SSH manager"""
        return Mock(spec=SSHManager)
    
    @pytest.fixture
    def user_manager(self, mock_ssh_manager, temp_config_dir):
        """Create user manager with mocked SSH manager"""
        return UserManager(
            ssh_manager=mock_ssh_manager,
            config_dir=temp_config_dir
        )
    
    def test_user_manager_init(self, user_manager, temp_config_dir, mock_ssh_manager):
        """Test user manager initialization"""
        assert user_manager.ssh_manager == mock_ssh_manager
        assert user_manager.config_dir == temp_config_dir
        assert temp_config_dir.exists()
        assert len(user_manager._users) == 0
        assert len(user_manager._groups) == 0
        
        # Check password policy defaults
        policy = user_manager.password_policy
        assert policy["min_length"] == 8
        assert policy["require_uppercase"] is True
        assert policy["require_lowercase"] is True
        assert policy["require_numbers"] is True
        assert policy["require_special"] is True
        assert policy["forbid_common_passwords"] is True
        
        # Check default role groups
        assert UserRole.ADMIN in user_manager.default_role_groups
        assert "wheel" in user_manager.default_role_groups[UserRole.ADMIN]
        assert "sudo" in user_manager.default_role_groups[UserRole.ADMIN]
    
    def test_create_user_minimal(self, user_manager):
        """Test creating user with minimal parameters"""
        user = user_manager.create_user(
            username="testuser",
            full_name="Test User",
            role=UserRole.STUDENT
        )
        
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.role == UserRole.STUDENT
        assert user.password_hash is not None  # Should be generated
        assert user.home_directory == "/home/testuser"
        assert user.sudo_access is False  # Student role default
        assert "students" in user.groups
        assert "cyris-students" in user.groups
    
    def test_create_user_admin(self, user_manager):
        """Test creating admin user"""
        user = user_manager.create_user(
            username="admin",
            full_name="Administrator",
            role=UserRole.ADMIN,
            password="SecurePass123!",
            ssh_public_keys=["ssh-rsa AAAA..."]
        )
        
        assert user.username == "admin"
        assert user.role == UserRole.ADMIN
        assert user.sudo_access is True  # Admin role default
        assert "wheel" in user.groups
        assert "sudo" in user.groups
        assert "adm" in user.groups
        assert user.ssh_public_keys == ["ssh-rsa AAAA..."]
    
    def test_create_user_duplicate_error(self, user_manager):
        """Test error when creating duplicate user"""
        # Create first user
        user_manager.create_user(
            username="duplicate",
            full_name="First User",
            role=UserRole.STUDENT
        )
        
        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            user_manager.create_user(
                username="duplicate",
                full_name="Second User",
                role=UserRole.INSTRUCTOR
            )
    
    def test_create_user_invalid_username(self, user_manager):
        """Test error with invalid username"""
        with pytest.raises(ValueError, match="Invalid username"):
            user_manager.create_user(
                username="123invalid",  # Cannot start with number
                full_name="Invalid User",
                role=UserRole.STUDENT
            )
        
        with pytest.raises(ValueError, match="Invalid username"):
            user_manager.create_user(
                username="user@invalid",  # Invalid characters
                full_name="Invalid User",
                role=UserRole.STUDENT
            )
    
    def test_create_user_invalid_password(self, user_manager):
        """Test error with invalid password"""
        with pytest.raises(ValueError, match="does not meet policy"):
            user_manager.create_user(
                username="testuser",
                full_name="Test User",
                role=UserRole.STUDENT,
                password="weak"  # Too short, no uppercase, no numbers, no special
            )
    
    def test_get_user(self, user_manager):
        """Test getting user by username"""
        # Create user
        created_user = user_manager.create_user(
            username="getuser",
            full_name="Get User",
            role=UserRole.STUDENT
        )
        
        # Get user
        retrieved_user = user_manager.get_user("getuser")
        assert retrieved_user == created_user
        
        # Non-existent user
        assert user_manager.get_user("nonexistent") is None
    
    def test_list_users(self, user_manager):
        """Test listing users with filters"""
        # Create users of different roles
        user_manager.create_user("admin1", "Admin One", UserRole.ADMIN)
        user_manager.create_user("admin2", "Admin Two", UserRole.ADMIN)
        user_manager.create_user("student1", "Student One", UserRole.STUDENT)
        user_manager.create_user("instructor1", "Instructor One", UserRole.INSTRUCTOR)
        
        # Disable one user
        user_manager.modify_user("student1", account_enabled=False)
        
        # Test list all users
        all_users = user_manager.list_users(enabled_only=False)
        assert len(all_users) == 4
        
        # Test list enabled only
        enabled_users = user_manager.list_users(enabled_only=True)
        assert len(enabled_users) == 3
        
        # Test filter by role
        admins = user_manager.list_users(role=UserRole.ADMIN)
        assert len(admins) == 2
        assert all(u.role == UserRole.ADMIN for u in admins)
        
        students = user_manager.list_users(role=UserRole.STUDENT)
        assert len(students) == 0  # Student is disabled, and enabled_only=True by default
        
        # Test with enabled_only=False
        all_students = user_manager.list_users(role=UserRole.STUDENT, enabled_only=False)
        assert len(all_students) == 1  # Should get the disabled student too
        
    def test_modify_user(self, user_manager):
        """Test modifying existing user"""
        # Create user
        user = user_manager.create_user(
            username="modifyuser",
            full_name="Modify User",
            role=UserRole.STUDENT
        )
        
        original_role = user.role
        original_groups = user.groups.copy()
        
        # Modify user
        modified_user = user_manager.modify_user(
            username="modifyuser",
            full_name="Modified User",
            role=UserRole.INSTRUCTOR,
            password="NewPass123!",
            sudo_access=True,
            account_enabled=False
        )
        
        assert modified_user.full_name == "Modified User"
        assert modified_user.role == UserRole.INSTRUCTOR
        assert modified_user.sudo_access is True
        assert modified_user.account_enabled is False
        # Should have instructor groups now
        assert "instructors" in modified_user.groups
        assert "cyris-instructors" in modified_user.groups
    
    def test_modify_user_nonexistent(self, user_manager):
        """Test modifying non-existent user"""
        with pytest.raises(ValueError, match="not found"):
            user_manager.modify_user("nonexistent", full_name="New Name")
    
    def test_delete_user(self, user_manager):
        """Test deleting user"""
        # Create user
        user_manager.create_user("deleteuser", "Delete User", UserRole.STUDENT)
        
        # Verify user exists
        assert user_manager.get_user("deleteuser") is not None
        
        # Delete user
        result = user_manager.delete_user("deleteuser")
        assert result is True
        
        # Verify user is gone
        assert user_manager.get_user("deleteuser") is None
        
        # Try to delete again
        result = user_manager.delete_user("deleteuser")
        assert result is False


class TestUserManagerGroups:
    """Test user group management functionality"""
    
    @pytest.fixture
    def temp_config_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_ssh_manager(self):
        return Mock(spec=SSHManager)
    
    @pytest.fixture
    def user_manager(self, mock_ssh_manager, temp_config_dir):
        return UserManager(
            ssh_manager=mock_ssh_manager,
            config_dir=temp_config_dir
        )
    
    def test_create_group(self, user_manager):
        """Test creating user group"""
        group = user_manager.create_group(
            group_name="developers",
            description="Software developers",
            members={"user1", "user2"},
            permissions={"code", "deploy"}
        )
        
        assert group.group_name == "developers"
        assert group.description == "Software developers"
        assert group.members == {"user1", "user2"}
        assert group.permissions == {"code", "deploy"}
    
    def test_create_group_duplicate_error(self, user_manager):
        """Test error when creating duplicate group"""
        user_manager.create_group("duplicate", "First Group")
        
        with pytest.raises(ValueError, match="already exists"):
            user_manager.create_group("duplicate", "Second Group")
    
    def test_add_user_to_group(self, user_manager):
        """Test adding user to group"""
        # Create user and group
        user_manager.create_user("testuser", "Test User", UserRole.STUDENT)
        user_manager.create_group("testgroup", "Test Group")
        
        # Add user to group
        result = user_manager.add_user_to_group("testuser", "testgroup")
        assert result is True
        
        # Verify membership
        user = user_manager.get_user("testuser")
        group = user_manager.get_group("testgroup")
        
        assert "testgroup" in user.groups
        assert "testuser" in group.members
    
    def test_add_nonexistent_user_to_group(self, user_manager):
        """Test adding non-existent user to group"""
        user_manager.create_group("testgroup", "Test Group")
        
        result = user_manager.add_user_to_group("nonexistent", "testgroup")
        assert result is False
    
    def test_add_user_to_nonexistent_group(self, user_manager):
        """Test adding user to non-existent group"""
        user_manager.create_user("testuser", "Test User", UserRole.STUDENT)
        
        result = user_manager.add_user_to_group("testuser", "nonexistent")
        assert result is False
    
    def test_remove_user_from_group(self, user_manager):
        """Test removing user from group"""
        # Create user and group
        user_manager.create_user("testuser", "Test User", UserRole.STUDENT)
        user_manager.create_group("testgroup", "Test Group")
        
        # Add user to group
        user_manager.add_user_to_group("testuser", "testgroup")
        
        # Remove user from group
        result = user_manager.remove_user_from_group("testuser", "testgroup")
        assert result is True
        
        # Verify removal
        user = user_manager.get_user("testuser")
        group = user_manager.get_group("testgroup")
        
        assert "testgroup" not in user.groups
        assert "testuser" not in group.members
    
    def test_get_group(self, user_manager):
        """Test getting group by name"""
        created_group = user_manager.create_group("testgroup", "Test Group")
        
        retrieved_group = user_manager.get_group("testgroup")
        assert retrieved_group == created_group
        
        assert user_manager.get_group("nonexistent") is None
    
    def test_list_groups(self, user_manager):
        """Test listing all groups"""
        user_manager.create_group("group1", "Group One")
        user_manager.create_group("group2", "Group Two")
        
        groups = user_manager.list_groups()
        assert len(groups) == 2
        assert any(g.group_name == "group1" for g in groups)
        assert any(g.group_name == "group2" for g in groups)


class TestUserManagerPasswordGeneration:
    """Test password generation and validation"""
    
    @pytest.fixture
    def user_manager(self):
        mock_ssh = Mock(spec=SSHManager)
        return UserManager(ssh_manager=mock_ssh)
    
    def test_generate_password_default(self, user_manager):
        """Test password generation with default length"""
        password = user_manager.generate_password()
        
        assert len(password) == 12
        # Should contain at least one of each required type
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in "!@#$%^&*" for c in password)
    
    def test_generate_password_custom_length(self, user_manager):
        """Test password generation with custom length"""
        password = user_manager.generate_password(length=16)
        
        assert len(password) == 16
        # Should still meet all requirements
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in "!@#$%^&*" for c in password)
    
    def test_validate_password_valid(self, user_manager):
        """Test password validation with valid passwords"""
        valid_passwords = [
            "SecurePass123!",
            "MyP@ssw0rd",
            "Str0ng!Pass",
            "Valid123@Password"
        ]
        
        for password in valid_passwords:
            assert user_manager._validate_password(password) is True
    
    def test_validate_password_invalid(self, user_manager):
        """Test password validation with invalid passwords"""
        invalid_passwords = [
            "short",           # Too short
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoNumbers!",       # No numbers
            "NoSpecial123",     # No special characters
            "password123!"      # Common password
        ]
        
        for password in invalid_passwords:
            assert user_manager._validate_password(password) is False
    
    def test_validate_username_valid(self, user_manager):
        """Test username validation with valid usernames"""
        valid_usernames = [
            "user",
            "testuser",
            "user123",
            "test-user",
            "test_user"
        ]
        
        for username in valid_usernames:
            assert user_manager._validate_username(username) is True
    
    def test_validate_username_invalid(self, user_manager):
        """Test username validation with invalid usernames"""
        invalid_usernames = [
            "123user",         # Cannot start with number
            "User",            # No uppercase allowed
            "user@domain",     # Invalid character
            "user.name",       # Invalid character
            "user space",      # No spaces
            "a" * 40          # Too long
        ]
        
        for username in invalid_usernames:
            assert user_manager._validate_username(username) is False


class TestUserManagerRemoteOperations:
    """Test remote user management operations"""
    
    @pytest.fixture
    def temp_config_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_ssh_manager(self):
        return Mock(spec=SSHManager)
    
    @pytest.fixture
    def user_manager(self, mock_ssh_manager, temp_config_dir):
        return UserManager(
            ssh_manager=mock_ssh_manager,
            config_dir=temp_config_dir
        )
    
    @pytest.fixture
    def sample_credentials(self):
        return [
            SSHCredentials(hostname="host1.example.com", username="root"),
            SSHCredentials(hostname="host2.example.com", username="root")
        ]
    
    def test_create_user_on_hosts_success(self, user_manager, mock_ssh_manager, sample_credentials):
        """Test creating user on remote hosts successfully"""
        # Create user locally first
        user_manager.create_user(
            username="remoteuser",
            full_name="Remote User",
            role=UserRole.STUDENT
        )
        
        # Mock successful SSH command execution
        mock_ssh_manager.execute_command.return_value = SSHResult(
            hostname="host1.example.com",
            command="useradd ...",
            return_code=0,
            stdout="",
            stderr="",
            execution_time=1.0,
            success=True
        )
        
        # Create user on hosts
        results = user_manager.create_user_on_hosts("remoteuser", sample_credentials)
        
        # Verify results
        assert len(results) == 2
        assert results["host1.example.com"] is True
        assert results["host2.example.com"] is True
        
        # Verify SSH commands were called
        assert mock_ssh_manager.execute_command.call_count >= 2
    
    def test_create_user_on_hosts_nonexistent_user(self, user_manager, sample_credentials):
        """Test creating non-existent user on hosts"""
        with pytest.raises(ValueError, match="not found in registry"):
            user_manager.create_user_on_hosts("nonexistent", sample_credentials)
    
    def test_delete_user_from_hosts(self, user_manager, mock_ssh_manager, sample_credentials):
        """Test deleting user from remote hosts"""
        # Mock successful SSH command execution
        mock_ssh_manager.execute_command.return_value = SSHResult(
            hostname="host1.example.com",
            command="userdel ...",
            return_code=0,
            stdout="",
            stderr="",
            execution_time=1.0,
            success=True
        )
        
        # Delete user from hosts
        results = user_manager.delete_user_from_hosts(
            "testuser", 
            sample_credentials, 
            remove_home=True
        )
        
        # Verify results
        assert len(results) == 2
        assert results["host1.example.com"] is True
        assert results["host2.example.com"] is True
        
        # Verify SSH commands were called
        assert mock_ssh_manager.execute_command.call_count >= 2
    
    def test_sync_users_to_hosts(self, user_manager, mock_ssh_manager, sample_credentials):
        """Test synchronizing multiple users to hosts"""
        # Create some users
        user_manager.create_user("user1", "User One", UserRole.STUDENT)
        user_manager.create_user("user2", "User Two", UserRole.INSTRUCTOR)
        
        # Mock successful SSH command execution
        mock_ssh_manager.execute_command.return_value = SSHResult(
            hostname="host1.example.com",
            command="useradd ...",
            return_code=0,
            stdout="",
            stderr="",
            execution_time=1.0,
            success=True
        )
        
        # Sync users to hosts
        results = user_manager.sync_users_to_hosts(sample_credentials, ["user1", "user2"])
        
        # Verify results structure
        assert len(results) == 2
        assert "host1.example.com" in results
        assert "host2.example.com" in results
        assert "user1" in results["host1.example.com"]
        assert "user2" in results["host1.example.com"]


class TestUserManagerStatistics:
    """Test user manager statistics"""
    
    @pytest.fixture
    def temp_config_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def user_manager(self, temp_config_dir):
        mock_ssh = Mock(spec=SSHManager)
        return UserManager(ssh_manager=mock_ssh, config_dir=temp_config_dir)
    
    def test_get_user_manager_stats(self, user_manager):
        """Test user manager statistics"""
        # Initial stats
        stats = user_manager.get_user_manager_stats()
        assert stats["total_users"] == 0
        assert stats["enabled_users"] == 0
        assert stats["total_groups"] == 0
        assert stats["users_by_role"]["admin"] == 0
        assert stats["users_by_role"]["student"] == 0
        
        # Create some users and groups
        user_manager.create_user("admin1", "Admin One", UserRole.ADMIN)
        user_manager.create_user("admin2", "Admin Two", UserRole.ADMIN)
        user_manager.create_user("student1", "Student One", UserRole.STUDENT)
        user_manager.create_user("instructor1", "Instructor One", UserRole.INSTRUCTOR)
        
        user_manager.create_group("group1", "Group One")
        user_manager.create_group("group2", "Group Two")
        
        # Disable one user
        user_manager.modify_user("student1", account_enabled=False)
        
        # Check updated stats
        stats = user_manager.get_user_manager_stats()
        assert stats["total_users"] == 4
        assert stats["enabled_users"] == 3
        assert stats["total_groups"] == 2
        assert stats["users_by_role"]["admin"] == 2
        assert stats["users_by_role"]["student"] == 1
        assert stats["users_by_role"]["instructor"] == 1
        assert stats["users_by_role"]["guest"] == 0


class TestUserManagerPersistence:
    """Test user configuration persistence"""
    
    @pytest.fixture
    def temp_config_dir(self):
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def user_manager(self, temp_config_dir):
        mock_ssh = Mock(spec=SSHManager)
        return UserManager(ssh_manager=mock_ssh, config_dir=temp_config_dir)
    
    def test_save_user_config(self, user_manager, temp_config_dir):
        """Test saving user configuration to file"""
        # Create user
        user = user_manager.create_user(
            username="configuser",
            full_name="Config User",
            role=UserRole.ADMIN,
            password="TestPass123!"
        )
        
        # Check config file was created
        config_file = temp_config_dir / "user_configuser.json"
        assert config_file.exists()
        
        # Check config file contents
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        assert config_data["username"] == "configuser"
        assert config_data["full_name"] == "Config User"
        assert config_data["role"] == "admin"
        assert config_data["password_hash"] is not None
        assert config_data["shell"] == "/bin/bash"
        assert config_data["sudo_access"] is True
        assert "wheel" in config_data["groups"]
    
    def test_save_group_config(self, user_manager, temp_config_dir):
        """Test saving group configuration to file"""
        # Create group
        group = user_manager.create_group(
            group_name="configgroup",
            description="Config Group",
            members={"user1", "user2"},
            permissions={"read", "write"}
        )
        
        # Check config file was created
        config_file = temp_config_dir / "group_configgroup.json"
        assert config_file.exists()
        
        # Check config file contents
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        assert config_data["group_name"] == "configgroup"
        assert config_data["description"] == "Config Group"
        assert set(config_data["members"]) == {"user1", "user2"}
        assert set(config_data["permissions"]) == {"read", "write"}
    
    def test_delete_user_removes_config(self, user_manager, temp_config_dir):
        """Test that deleting user removes config file"""
        # Create user
        user_manager.create_user("deleteconfig", "Delete Config", UserRole.STUDENT)
        
        # Verify config file exists
        config_file = temp_config_dir / "user_deleteconfig.json"
        assert config_file.exists()
        
        # Delete user
        user_manager.delete_user("deleteconfig")
        
        # Verify config file is gone
        assert not config_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])