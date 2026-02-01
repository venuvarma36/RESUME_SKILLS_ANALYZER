"""
Secure Storage Module
Integrates blockchain and encryption for secure data storage.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from .blockchain import BlockchainManager
from .encryption import DataEncryption
from utils import get_logger


logger = get_logger(__name__)


class SecureDataStorage:
    """Manages secure storage of resumes, job descriptions, and user data."""
    
    def __init__(self, master_key: str = None, chain_file: str = None):
        """
        Initialize secure storage.
        
        Args:
            master_key: Encryption master key
            chain_file: Blockchain storage file
        """
        self.encryption = DataEncryption(master_key)
        self.blockchain = BlockchainManager(chain_file, encryption_key=self.encryption.master_key)
        
        logger.info("SecureDataStorage initialized with encryption enabled")
    
    def store_resume(self, resume_data: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
        """
        Securely store resume data in blockchain.
        
        Args:
            resume_data: Resume data to store
            user_id: Optional user identifier
            
        Returns:
            Storage metadata
        """
        # Encrypt sensitive resume data
        encrypted_data = self.encryption.encrypt_resume_data(resume_data)
        
        # Add metadata
        storage_data = {
            'encrypted_resume': encrypted_data,
            'user_id': user_id,
            'data_hash': self.encryption.generate_data_hash(resume_data)
        }
        
        # Store in blockchain
        block = self.blockchain.add_block(storage_data, data_type='resume')
        
        logger.info("Resume stored in blockchain (block #%d)", block.index)
        
        return {
            'block_index': block.index,
            'block_hash': block.hash,
            'timestamp': block.timestamp,
            'data_hash': storage_data['data_hash']
        }
    
    def retrieve_resume(self, block_index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt resume data from blockchain.
        
        Args:
            block_index: Block index to retrieve
            
        Returns:
            Decrypted resume data or None
        """
        block = self.blockchain.get_block_by_index(block_index)
        
        if not block or block.data.get('type') != 'resume':
            logger.warning("Resume not found at block index %d", block_index)
            return None
        
        encrypted_data = block.data['data']['encrypted_resume']
        
        # Decrypt resume data
        decrypted_data = self.encryption.decrypt_resume_data(encrypted_data)
        
        logger.info("Resume retrieved from blockchain (block #%d)", block_index)
        
        return decrypted_data
    
    def store_job_description(self, jd_data: Dict[str, Any], 
                             company: str = None) -> Dict[str, Any]:
        """
        Securely store job description in blockchain.
        
        Args:
            jd_data: Job description data
            company: Company name
            
        Returns:
            Storage metadata
        """
        # Encrypt sensitive job description data
        encrypted_data = self.encryption.encrypt_job_description(jd_data)
        
        # Add metadata
        storage_data = {
            'encrypted_jd': encrypted_data,
            'company': company,
            'data_hash': self.encryption.generate_data_hash(jd_data)
        }
        
        # Store in blockchain
        block = self.blockchain.add_block(storage_data, data_type='job_description')
        
        logger.info("Job description stored in blockchain (block #%d)", block.index)
        
        return {
            'block_index': block.index,
            'block_hash': block.hash,
            'timestamp': block.timestamp,
            'data_hash': storage_data['data_hash']
        }
    
    def retrieve_job_description(self, block_index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt job description from blockchain.
        
        Args:
            block_index: Block index to retrieve
            
        Returns:
            Decrypted job description data or None
        """
        block = self.blockchain.get_block_by_index(block_index)
        
        if not block or block.data.get('type') != 'job_description':
            logger.warning("Job description not found at block index %d", block_index)
            return None
        
        encrypted_data = block.data['data']['encrypted_jd']
        
        # Decrypt job description data
        decrypted_data = self.encryption.decrypt_job_description(encrypted_data)
        
        logger.info("Job description retrieved from blockchain (block #%d)", block_index)
        
        return decrypted_data
    
    def store_user_credentials(self, username: str, password: str,
                              user_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Securely store user credentials in blockchain.
        
        Args:
            username: Username
            password: Plain text password (will be hashed)
            user_data: Additional user data
            
        Returns:
            Storage metadata
        """
        # Hash password
        password_hash = self.encryption.hash_password(password)
        
        # Prepare user data
        storage_data = {
            'username': username,
            'password_hash': password_hash,
            'user_data': self.encryption.encrypt_dict(user_data) if user_data else {}
        }
        
        # Store in blockchain
        block = self.blockchain.add_block(storage_data, data_type='user_credentials')
        
        logger.info("User credentials stored in blockchain (block #%d)", block.index)
        
        return {
            'block_index': block.index,
            'block_hash': block.hash,
            'username': username
        }
    
    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify user credentials against blockchain.
        
        Args:
            username: Username
            password: Password to verify
            
        Returns:
            User data if credentials are valid, None otherwise
        """
        # Search for user in blockchain
        user_blocks = self.blockchain.get_blocks_by_type('user_credentials')
        
        for block in user_blocks:
            block_data = block.data['data']
            
            if block_data['username'] == username:
                # Verify password
                if self.encryption.verify_password(password, block_data['password_hash']):
                    logger.info("User credentials verified for %s", username)
                    
                    # Decrypt user data
                    user_data = {}
                    if block_data.get('user_data'):
                        user_data = self.encryption.decrypt_dict(block_data['user_data'])
                    
                    return {
                        'username': username,
                        'block_index': block.index,
                        'user_data': user_data
                    }
                else:
                    logger.warning("Invalid password for user %s", username)
                    return None
        
        logger.warning("User %s not found", username)
        return None
    
    def get_user_resumes(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all resumes for a specific user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of resume data
        """
        resume_blocks = self.blockchain.get_blocks_by_type('resume')
        user_resumes = []
        
        for block in resume_blocks:
            block_data = block.data['data']
            
            if block_data.get('user_id') == user_id:
                encrypted_data = block_data['encrypted_resume']
                decrypted_data = self.encryption.decrypt_resume_data(encrypted_data)
                
                user_resumes.append({
                    'block_index': block.index,
                    'resume_data': decrypted_data,
                    'timestamp': block.timestamp
                })
        
        logger.info("Retrieved %d resumes for user %s", len(user_resumes), user_id)
        
        return user_resumes
    
    def verify_data_integrity(self) -> bool:
        """
        Verify blockchain integrity.
        
        Returns:
            True if blockchain is valid
        """
        is_valid = self.blockchain.is_chain_valid()
        
        if is_valid:
            logger.info("Blockchain integrity verified: VALID")
        else:
            logger.error("Blockchain integrity verification FAILED")
        
        return is_valid
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Storage statistics
        """
        resume_count = len(self.blockchain.get_blocks_by_type('resume'))
        jd_count = len(self.blockchain.get_blocks_by_type('job_description'))
        user_count = len(self.blockchain.get_blocks_by_type('user_credentials'))
        
        return {
            **self.blockchain.get_chain_info(),
            'resume_count': resume_count,
            'job_description_count': jd_count,
            'user_count': user_count
        }
