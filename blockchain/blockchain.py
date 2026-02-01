"""
Blockchain Implementation for Resume Skill Recognition System
Provides immutable, transparent, and secure data storage.
"""

import hashlib
import json
import time
import base64
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from utils import get_logger, config


logger = get_logger(__name__)


class Block:
    """Represents a single block in the blockchain."""
    
    def __init__(self, index: int, timestamp: float, data: Dict[str, Any],
                 previous_hash: str, nonce: int = 0):
        """
        Initialize a block.
        
        Args:
            index: Block index in the chain
            timestamp: Block creation timestamp
            data: Encrypted data stored in the block
            previous_hash: Hash of the previous block
            nonce: Nonce for proof-of-work
        """
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """
        Calculate the hash of the block.
        
        Returns:
            SHA-256 hash of the block
        """
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce
        }, sort_keys=True)
        
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty: int = 4):
        """
        Mine the block using proof-of-work.
        
        Args:
            difficulty: Number of leading zeros required in hash
        """
        target = '0' * difficulty
        
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        
        logger.debug("Block mined: %s", self.hash)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert block to dictionary.
        
        Returns:
            Block as dictionary
        """
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'hash': self.hash
        }
    
    @classmethod
    def from_dict(cls, block_dict: Dict[str, Any]) -> 'Block':
        """
        Create block from dictionary.
        
        Args:
            block_dict: Block data as dictionary
            
        Returns:
            Block instance
        """
        block = cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'],
            data=block_dict['data'],
            previous_hash=block_dict['previous_hash'],
            nonce=block_dict['nonce']
        )
        block.hash = block_dict['hash']
        return block


class BlockchainManager:
    """Manages the blockchain for secure data storage."""
    
    def __init__(self, chain_file: str = None, encryption_key: str = None):
        """
        Initialize blockchain manager.
        
        Args:
            chain_file: Path to blockchain storage file
            encryption_key: Key for encrypting block data in storage
        """
        if chain_file is None:
            project_root = Path(__file__).parent.parent
            chain_file = project_root / "data" / "blockchain.json"
        
        self.chain_file = Path(chain_file)
        self.chain_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.difficulty = config.get('blockchain.difficulty', 4)
        self.encryption_key = encryption_key or config.get('blockchain.master_key', None)
        self.chain: List[Block] = []
        
        # Initialize encryption for storage if available
        self.storage_encryption = None
        if self.encryption_key:
            try:
                from .encryption import DataEncryption
                self.storage_encryption = DataEncryption(self.encryption_key)
                logger.info("Storage encryption enabled for blockchain")
            except Exception as e:
                logger.warning("Could not enable storage encryption: %s", str(e))
        
        # Load or create chain
        if self.chain_file.exists():
            self.load_chain()
        else:
            self.create_genesis_block()
        
        logger.info("BlockchainManager initialized with %d blocks", len(self.chain))
    
    def create_genesis_block(self):
        """Create the first block in the chain (genesis block)."""
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            data={'message': 'Genesis Block - Resume Skill Recognition System'},
            previous_hash='0'
        )
        genesis_block.mine_block(self.difficulty)
        self.chain.append(genesis_block)
        self.save_chain()
        logger.info("Genesis block created")
    
    def get_latest_block(self) -> Block:
        """
        Get the latest block in the chain.
        
        Returns:
            Latest block
        """
        return self.chain[-1]
    
    def add_block(self, data: Dict[str, Any], data_type: str = "general") -> Block:
        """
        Add a new block to the chain.
        
        Args:
            data: Encrypted data to store
            data_type: Type of data (resume, job_description, user, etc.)
            
        Returns:
            Created block
        """
        previous_block = self.get_latest_block()
        
        # Add metadata
        block_data = {
            'type': data_type,
            'data': data,
            'created_at': datetime.now().isoformat()
        }
        
        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            data=block_data,
            previous_hash=previous_block.hash
        )
        
        new_block.mine_block(self.difficulty)
        self.chain.append(new_block)
        self.save_chain()
        
        logger.info("Block #%d added to chain (type: %s)", new_block.index, data_type)
        return new_block
    
    def is_chain_valid(self) -> bool:
        """
        Validate the entire blockchain.
        
        Returns:
            True if chain is valid, False otherwise
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Check if current block's hash is correct
            if current_block.hash != current_block.calculate_hash():
                logger.error("Invalid hash at block %d", i)
                return False
            
            # Check if previous hash matches
            if current_block.previous_hash != previous_block.hash:
                logger.error("Invalid previous hash at block %d", i)
                return False
        
        return True
    
    def get_blocks_by_type(self, data_type: str) -> List[Block]:
        """
        Get all blocks of a specific type.
        
        Args:
            data_type: Type of data to filter
            
        Returns:
            List of matching blocks
        """
        return [
            block for block in self.chain
            if block.data.get('type') == data_type
        ]
    
    def get_block_by_index(self, index: int) -> Optional[Block]:
        """
        Get block by index.
        
        Args:
            index: Block index
            
        Returns:
            Block or None if not found
        """
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None
    
    def search_blocks(self, search_term: str, data_type: str = None) -> List[Block]:
        """
        Search blocks containing a term.
        
        Args:
            search_term: Term to search for
            data_type: Optional data type filter
            
        Returns:
            List of matching blocks
        """
        results = []
        
        for block in self.chain:
            if data_type and block.data.get('type') != data_type:
                continue
            
            block_str = json.dumps(block.data, default=str).lower()
            if search_term.lower() in block_str:
                results.append(block)
        
        return results
    
    def save_chain(self):
        """Save blockchain to file (with encrypted block data if encryption is enabled)."""
        try:
            chain_data = []
            
            for block in self.chain:
                block_dict = block.to_dict()
                
                # Encrypt block data if encryption is available
                if self.storage_encryption:
                    try:
                        block_data_json = json.dumps(block_dict['data'])
                        encrypted_data = self.storage_encryption.encrypt_text(block_data_json)
                        block_dict['data_encrypted'] = encrypted_data
                        block_dict['data'] = {'_encrypted': True}  # Marker that data is encrypted
                        logger.debug("Block #%d data encrypted for storage", block.index)
                    except Exception as e:
                        logger.warning("Failed to encrypt block #%d data: %s", block.index, str(e))
                        # Fall back to unencrypted storage
                
                chain_data.append(block_dict)
            
            with open(self.chain_file, 'w', encoding='utf-8') as f:
                json.dump(chain_data, f, indent=2)
            
            logger.debug("Blockchain saved to %s (encryption: %s)", 
                        self.chain_file, "enabled" if self.storage_encryption else "disabled")
        except Exception as e:
            logger.error("Failed to save blockchain: %s", str(e))
    
    def load_chain(self):
        """Load blockchain from file (with decryption of encrypted block data if encryption is enabled)."""
        try:
            with open(self.chain_file, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)
            
            # Decrypt block data if it was encrypted
            for block_dict in chain_data:
                if block_dict.get('data', {}).get('_encrypted') and block_dict.get('data_encrypted'):
                    if self.storage_encryption:
                        try:
                            encrypted_data = block_dict['data_encrypted']
                            decrypted_data_json = self.storage_encryption.decrypt_text(encrypted_data)
                            block_dict['data'] = json.loads(decrypted_data_json)
                            del block_dict['data_encrypted']  # Remove encrypted data from memory
                            logger.debug("Block #%d data decrypted from storage", block_dict['index'])
                        except Exception as e:
                            logger.error("Failed to decrypt block #%d data: %s", block_dict['index'], str(e))
                            raise ValueError(f"Failed to decrypt block data: {str(e)}")
                    else:
                        logger.error("Block data is encrypted but no encryption key available")
                        raise ValueError("Encrypted blockchain data found but no encryption key configured")
            
            self.chain = [Block.from_dict(block_dict) for block_dict in chain_data]
            
            # Validate loaded chain
            if not self.is_chain_valid():
                logger.error("Loaded blockchain is invalid!")
                raise ValueError("Invalid blockchain detected")
            
            logger.info("Blockchain loaded from %s (%d blocks)", 
                       self.chain_file, len(self.chain))
        except Exception as e:
            logger.error("Failed to load blockchain: %s", str(e))
            logger.info("Creating new blockchain")
            self.create_genesis_block()
    
    def get_chain_info(self) -> Dict[str, Any]:
        """
        Get information about the blockchain.
        
        Returns:
            Blockchain statistics
        """
        return {
            'total_blocks': len(self.chain),
            'is_valid': self.is_chain_valid(),
            'latest_block_hash': self.get_latest_block().hash,
            'genesis_block_hash': self.chain[0].hash,
            'difficulty': self.difficulty,
            'chain_file': str(self.chain_file)
        }
    
    def export_chain(self, output_file: str):
        """
        Export blockchain to JSON file.
        
        Args:
            output_file: Path to output file
        """
        chain_data = [block.to_dict() for block in self.chain]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chain_data, f, indent=2)
        
        logger.info("Blockchain exported to %s", output_file)
