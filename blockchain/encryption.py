"""
Encryption Module for Blockchain Data Security
Provides AES encryption for sensitive data.
"""

import hashlib
import base64
import secrets
import json
import numpy as np
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from utils import get_logger, config


logger = get_logger(__name__)


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle numpy arrays and other non-serializable types."""
    def default(self, obj):  # pylint: disable=method-hidden
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


class DataEncryption:
    """Handles encryption and decryption of sensitive data."""
    
    def __init__(self, master_key: str = None):
        """
        Initialize encryption manager.
        
        Args:
            master_key: Master encryption key (generated if not provided)
        """
        if master_key is None:
            master_key = config.get('blockchain.master_key', None)
            if master_key is None:
                # Generate a new master key
                master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
                logger.warning("No master key configured. Generated new key: %s", master_key[:10] + "...")
                logger.warning("Store this key in config.yaml under blockchain.master_key")
        
        self.master_key = master_key
        self.cipher = self._create_cipher(master_key)
        
        logger.info("DataEncryption initialized")
    
    def _create_cipher(self, key: str) -> Fernet:
        """
        Create Fernet cipher from master key.
        
        Args:
            key: Master key
            
        Returns:
            Fernet cipher
        """
        # Derive a proper Fernet key from master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'resume_skill_recognition_salt',  # Fixed salt for deterministic key
            iterations=100000,
            backend=default_backend()
        )
        
        derived_key = base64.urlsafe_b64encode(
            kdf.derive(key.encode())
        )
        
        return Fernet(derived_key)
    
    def encrypt_text(self, text: str) -> str:
        """
        Encrypt text data.
        
        Args:
            text: Plain text to encrypt
            
        Returns:
            Encrypted text (base64 encoded)
        """
        try:
            encrypted_bytes = self.cipher.encrypt(text.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            logger.error("Encryption failed: %s", str(e))
            raise
    
    def decrypt_text(self, encrypted_text: str) -> str:
        """
        Decrypt text data.
        
        Args:
            encrypted_text: Encrypted text (base64 encoded)
            
        Returns:
            Decrypted plain text
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error("Decryption failed: %s", str(e))
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Encrypt dictionary data.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Dictionary with encrypted values
        """
        encrypted_data = {}
        
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                # Convert complex types to string first
                import json
                value_str = json.dumps(value, default=str)
            else:
                value_str = str(value)
            
            encrypted_data[key] = self.encrypt_text(value_str)
        
        return encrypted_data
    
    def decrypt_dict(self, encrypted_data: Dict[str, str]) -> Dict[str, str]:
        """
        Decrypt dictionary data.
        
        Args:
            encrypted_data: Dictionary with encrypted values
            
        Returns:
            Dictionary with decrypted values
        """
        decrypted_data = {}
        
        for key, encrypted_value in encrypted_data.items():
            decrypted_data[key] = self.decrypt_text(encrypted_value)
        
        return decrypted_data
    
    def hash_password(self, password: str) -> str:
        """
        Hash password using SHA-256.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password (hex)
        """
        # Add salt for additional security
        salt = b'resume_skill_system_salt_2026'
        salted_password = password.encode() + salt
        
        return hashlib.sha256(salted_password).hexdigest()
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            password: Plain text password
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        return self.hash_password(password) == hashed_password
    
    def encrypt_resume_data(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt resume data for blockchain storage.
        
        Args:
            resume_data: Resume data dictionary
            
        Returns:
            Encrypted resume data
        """
        # Fields to encrypt
        sensitive_fields = ['text', 'file_path', 'skills', 'extraction_method']
        
        encrypted_data = {}
        
        for key, value in resume_data.items():
            if key in sensitive_fields:
                if value is not None:
                    if isinstance(value, (dict, list, np.ndarray)):
                        # Use NumpyEncoder to handle numpy arrays and other types
                        value_str = json.dumps(value, cls=NumpyEncoder)
                    else:
                        value_str = str(value)
                    encrypted_data[key] = self.encrypt_text(value_str)
                else:
                    encrypted_data[key] = None
            else:
                # Store non-sensitive metadata unencrypted (convert numpy types)
                if isinstance(value, np.ndarray):
                    encrypted_data[key] = value.tolist()
                elif isinstance(value, (np.integer, np.floating)):
                    encrypted_data[key] = float(value)
                elif isinstance(value, np.bool_):
                    encrypted_data[key] = bool(value)
                else:
                    encrypted_data[key] = value
        
        return encrypted_data
    
    def decrypt_resume_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt resume data from blockchain.
        
        Args:
            encrypted_data: Encrypted resume data
            
        Returns:
            Decrypted resume data
        """
        sensitive_fields = ['text', 'file_path', 'skills', 'extraction_method']
        
        decrypted_data = {}
        
        for key, value in encrypted_data.items():
            if key in sensitive_fields and value is not None:
                decrypted_str = self.decrypt_text(value)
                
                # Try to parse JSON for complex types
                if key in ['skills']:
                    try:
                        decrypted_data[key] = json.loads(decrypted_str)
                    except json.JSONDecodeError:
                        decrypted_data[key] = decrypted_str
                else:
                    decrypted_data[key] = decrypted_str
            else:
                decrypted_data[key] = value
        
        return decrypted_data
    
    def encrypt_job_description(self, jd_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt job description data.
        
        Args:
            jd_data: Job description data
            
        Returns:
            Encrypted job description data
        """
        sensitive_fields = ['text', 'skills']
        
        encrypted_data = {}
        
        for key, value in jd_data.items():
            if key in sensitive_fields and value is not None:
                if isinstance(value, (dict, list, np.ndarray)):
                    # Use NumpyEncoder to handle numpy arrays
                    value_str = json.dumps(value, cls=NumpyEncoder)
                else:
                    value_str = str(value)
                encrypted_data[key] = self.encrypt_text(value_str)
            else:
                # Convert numpy types for non-sensitive fields
                if isinstance(value, np.ndarray):
                    encrypted_data[key] = value.tolist()
                elif isinstance(value, (np.integer, np.floating)):
                    encrypted_data[key] = float(value)
                elif isinstance(value, np.bool_):
                    encrypted_data[key] = bool(value)
                else:
                    encrypted_data[key] = value
        
        return encrypted_data
    
    def decrypt_job_description(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt job description data.
        
        Args:
            encrypted_data: Encrypted job description data
            
        Returns:
            Decrypted job description data
        """
        sensitive_fields = ['text', 'skills']
        
        decrypted_data = {}
        
        for key, value in encrypted_data.items():
            if key in sensitive_fields and value is not None:
                decrypted_str = self.decrypt_text(value)
                
                if key in ['skills']:
                    try:
                        decrypted_data[key] = json.loads(decrypted_str)
                    except json.JSONDecodeError:
                        decrypted_data[key] = decrypted_str
                else:
                    decrypted_data[key] = decrypted_str
            else:
                decrypted_data[key] = value
        
        return decrypted_data
    
    def generate_data_hash(self, data: Any) -> str:
        """
        Generate SHA-256 hash of data for verification.
        
        Args:
            data: Data to hash
            
        Returns:
            Hex hash string
        """
        import json
        
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
