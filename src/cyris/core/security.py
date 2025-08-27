"""
Security utilities and helpers for CyRIS
"""

import secrets
import hashlib
import base64
import logging
import subprocess
import shlex
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


logger = logging.getLogger(__name__)


class CyRISSecurityError(Exception):
    """CyRIS security related errors"""
    pass


class SecureCommandExecutor:
    """Secure command execution without shell injection vulnerabilities"""
    
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def execute_command(
        self, 
        command_parts: List[str], 
        input_data: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None
    ) -> tuple[bool, str, str]:
        """
        Securely execute a command without shell injection risks.
        
        Args:
            command_parts: Command and arguments as separate list items
            input_data: Optional stdin data
            env: Optional environment variables
            cwd: Optional working directory
            
        Returns:
            (success, stdout, stderr)
        """
        try:
            # Validate command parts
            if not command_parts or not isinstance(command_parts, list):
                raise CyRISSecurityError("Command parts must be a non-empty list")
            
            # Sanitize command parts
            sanitized_parts = []
            for part in command_parts:
                if not isinstance(part, str):
                    raise CyRISSecurityError("All command parts must be strings")
                # Basic validation - no shell metacharacters in executable name
                if command_parts.index(part) == 0 and any(char in part for char in ';|&$()`'):
                    raise CyRISSecurityError(f"Invalid executable name: {part}")
                sanitized_parts.append(part)
            
            self.logger.debug(f"Executing command: {sanitized_parts[0]} (with {len(sanitized_parts)-1} args)")
            
            result = subprocess.run(
                sanitized_parts,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=env,
                cwd=cwd
            )
            
            success = result.returncode == 0
            if not success:
                self.logger.warning(f"Command failed with return code {result.returncode}")
            
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {self.timeout} seconds")
            return False, "", "Command execution timed out"
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            return False, "", str(e)


class SecretManager:
    """Secure management of sensitive information"""
    
    def __init__(self, key_file: Optional[Path] = None):
        self.key_file = key_file or Path.home() / ".cyris" / "secret.key"
        self._key = self._load_or_generate_key()
        self.cipher = Fernet(self._key)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def _load_or_generate_key(self) -> bytes:
        """Load existing key or generate new one"""
        try:
            if self.key_file.exists():
                return self.key_file.read_bytes()
            else:
                # Generate new key
                key = Fernet.generate_key()
                # Create directory if needed
                self.key_file.parent.mkdir(parents=True, exist_ok=True)
                # Write key with secure permissions
                self.key_file.write_bytes(key)
                self.key_file.chmod(0o600)
                self.logger.info(f"Generated new encryption key: {self.key_file}")
                return key
        except Exception as e:
            raise CyRISSecurityError(f"Failed to load/generate encryption key: {e}")
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            encrypted = self.cipher.encrypt(data.encode('utf-8'))
            return base64.b64encode(encrypted).decode('ascii')
        except Exception as e:
            raise CyRISSecurityError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('ascii'))
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            raise CyRISSecurityError(f"Decryption failed: {e}")
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
        """Hash password securely using PBKDF2"""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = kdf.derive(password.encode('utf-8'))
        hash_value = base64.b64encode(key).decode('ascii')
        salt_value = base64.b64encode(salt).decode('ascii')
        
        return hash_value, salt_value


class SecureLogger:
    """Logger that masks sensitive information"""
    
    SENSITIVE_PATTERNS = [
        'password', 'passwd', 'secret', 'key', 'token', 'credential'
    ]
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _mask_sensitive(self, message: str) -> str:
        """Mask sensitive information in log messages"""
        masked_message = message
        for pattern in self.SENSITIVE_PATTERNS:
            # Replace pattern=value with pattern=***
            import re
            masked_message = re.sub(
                rf'({pattern}["\']?\s*[:=]\s*["\']?)([^\s"\']+)',
                r'\1***',
                masked_message,
                flags=re.IGNORECASE
            )
        return masked_message
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with sensitive data masked"""
        self.logger.debug(self._mask_sensitive(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with sensitive data masked"""
        self.logger.info(self._mask_sensitive(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with sensitive data masked"""
        self.logger.warning(self._mask_sensitive(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with sensitive data masked"""
        self.logger.error(self._mask_sensitive(message), *args, **kwargs)


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure password"""
    if length < 8:
        raise CyRISSecurityError("Password length must be at least 8 characters")
    
    # Character sets
    lowercase = 'abcdefghijklmnopqrstuvwxyz'
    uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    numbers = '0123456789'
    special = '!@#$%^&*()-_=+[]{}|;:,.<>?'
    
    # Ensure at least one character from each set
    password_chars = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(numbers),
        secrets.choice(special)
    ]
    
    # Fill remaining length with random choices
    all_chars = lowercase + uppercase + numbers + special
    for _ in range(length - 4):
        password_chars.append(secrets.choice(all_chars))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


def validate_user_input(input_value: str, input_type: str = "general") -> bool:
    """Validate user input to prevent injection attacks"""
    if not isinstance(input_value, str):
        return False
    
    # Basic validation rules
    if input_type == "username":
        # Username should be alphanumeric plus underscore, hyphen, dot
        import re
        return bool(re.match(r'^[a-zA-Z0-9_.-]+$', input_value)) and len(input_value) <= 32
    
    elif input_type == "range_id":
        # Range ID should be numeric or alphanumeric
        return input_value.isalnum() and len(input_value) <= 16
    
    elif input_type == "vm_name":
        # VM names should be safe for filesystem and XML
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', input_value)) and len(input_value) <= 64
    
    elif input_type == "file_path":
        # File paths should not contain dangerous sequences
        dangerous = ['../', '.\\', '$(', '`', '|', ';', '&']
        return not any(danger in input_value for danger in dangerous)
    
    # General validation - no control characters or dangerous sequences
    dangerous_patterns = ['\x00', '\n', '\r', '$(', '`', ';', '|', '&&', '||']
    return not any(pattern in input_value for pattern in dangerous_patterns)


def sanitize_for_shell(value: str) -> str:
    """Sanitize string for safe shell usage"""
    return shlex.quote(value)