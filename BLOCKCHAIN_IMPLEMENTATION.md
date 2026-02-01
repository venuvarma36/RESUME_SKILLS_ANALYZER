# Blockchain Implementation for Resume Skill Recognition System

## Overview

This system implements a **blockchain-based secure storage solution** to protect sensitive user data including resumes, job descriptions, and user credentials. The implementation ensures data privacy, transparency, and immutability through cryptographic techniques.

---

## Why Blockchain?

### 1. **Data Security & Privacy**
- All sensitive data (resume text, skills, job descriptions, passwords) is **encrypted** before storage
- Only authorized users with the correct encryption key can decrypt and access data
- Even if the blockchain file is accessed, the data remains unreadable without the master key

### 2. **Data Transparency**
- Every data operation is recorded as a **block** in the chain
- Each block contains a cryptographic hash linking it to the previous block
- Any tampering with data is immediately detectable through hash verification
- Complete audit trail of all data operations

### 3. **Immutability**
- Once data is added to the blockchain, it cannot be altered or deleted
- Proof-of-work mining ensures computational cost for adding blocks
- Chain validation prevents unauthorized modifications

### 4. **Decentralized Trust**
- No single point of failure
- Data integrity is maintained through cryptographic verification
- Users can verify their data hasn't been tampered with

---

## Architecture

### Components

```
blockchain/
├── __init__.py              # Module initialization
├── blockchain.py            # Core blockchain implementation
├── encryption.py            # Encryption/decryption utilities
└── secure_storage.py        # High-level secure storage API
```

### Data Flow

```
User Data (Resume/JD/Password)
    ↓
[Encryption Layer - AES-256]
    ↓
[Blockchain Block Creation]
    ↓
[Proof-of-Work Mining]
    ↓
[Block Added to Chain]
    ↓
[Saved to Secure Storage]
```

---

## Implementation Details

### 1. Block Structure

Each block contains:

```python
{
    "index": 123,                    # Block number in chain
    "timestamp": 1706745600.0,       # Creation time
    "data": {                        # Block payload
        "type": "resume",            # Data type
        "data": {...},               # Encrypted data
        "created_at": "2026-01-31T..."
    },
    "previous_hash": "abc123...",    # Link to previous block
    "nonce": 45678,                  # Proof-of-work nonce
    "hash": "def456..."              # This block's hash
}
```

### 2. Encryption Methods

#### AES-256 Encryption (Fernet)
- **Algorithm**: AES in CBC mode with 128-bit key
- **Key Derivation**: PBKDF2 with SHA-256 (100,000 iterations)
- **Salt**: Fixed salt for deterministic key generation
- **Encoding**: Base64 for storage

```python
# Example: Encrypting resume text
encrypted_text = encryption.encrypt_text("Resume content here...")
# Result: "gAAAAABl2K3X4Y..."
```

#### Password Hashing
- **Algorithm**: SHA-256
- **Salt**: Fixed application salt
- **Output**: 64-character hexadecimal hash

```python
# Example: Hashing password
password_hash = encryption.hash_password("myPassword123")
# Result: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
```

### 3. Proof-of-Work Mining

Each block requires computational work before being added:

```python
# Mining difficulty: 4 leading zeros (configurable)
target = "0000"

while block.hash[:4] != target:
    block.nonce += 1
    block.hash = block.calculate_hash()

# Result: hash like "0000a7b3c4..."
```

**Difficulty = 4**: ~16^4 = 65,536 average attempts per block
- Prevents rapid chain manipulation
- Adds computational cost to attacks
- Configurable via `config.yaml`

---

## Usage Examples

### 1. Storing Resume Data Securely

```python
from blockchain import SecureDataStorage

# Initialize secure storage
storage = SecureDataStorage()

# Resume data to store
resume_data = {
    'text': 'John Doe\nSoftware Engineer\n...',
    'file_path': '/path/to/resume.pdf',
    'skills': {
        'technical_skills': ['Python', 'JavaScript'],
        'tools': ['Docker', 'Git']
    }
}

# Store encrypted in blockchain
metadata = storage.store_resume(resume_data, user_id='user123')

print(f"Stored at block #{metadata['block_index']}")
print(f"Block hash: {metadata['block_hash']}")
print(f"Data hash: {metadata['data_hash']}")
```

**What happens internally:**
1. Resume text, file path, and skills are encrypted
2. Data hash is generated for verification
3. New block is created with encrypted data
4. Block is mined (proof-of-work)
5. Block is added to chain and saved

### 2. Retrieving Resume Data

```python
# Retrieve by block index
resume_data = storage.retrieve_resume(block_index=15)

print(resume_data['text'])        # Decrypted: "John Doe..."
print(resume_data['skills'])      # Decrypted: {'technical_skills': [...]}
```

**What happens internally:**
1. Block is located in chain by index
2. Encrypted data is extracted
3. Data is decrypted using master key
4. Original resume data is returned

### 3. Storing Job Descriptions

```python
# Job description data
jd_data = {
    'text': 'We are looking for a Python Developer...',
    'skills': {
        'technical_skills': ['Python', 'Django', 'REST API'],
        'tools': ['PostgreSQL', 'Redis']
    }
}

# Store encrypted in blockchain
metadata = storage.store_job_description(jd_data, company='TechCorp')

print(f"JD stored at block #{metadata['block_index']}")
```

### 4. Secure User Authentication

```python
# Store user credentials
metadata = storage.store_user_credentials(
    username='john_doe',
    password='SecurePass123!',
    user_data={
        'email': 'john@example.com',
        'name': 'John Doe'
    }
)

# Verify credentials later
user_info = storage.verify_user_credentials('john_doe', 'SecurePass123!')

if user_info:
    print(f"Login successful! User: {user_info['username']}")
    print(f"User data: {user_info['user_data']}")
else:
    print("Invalid credentials")
```

**What happens internally:**
1. Password is hashed using SHA-256
2. User data is encrypted
3. Credentials stored in blockchain
4. During verification, password is hashed and compared
5. If valid, encrypted user data is decrypted and returned

### 5. Verifying Data Integrity

```python
# Verify entire blockchain
is_valid = storage.verify_data_integrity()

if is_valid:
    print("✓ Blockchain is valid - no tampering detected")
else:
    print("✗ Blockchain integrity compromised!")

# Get storage statistics
stats = storage.get_storage_stats()
print(f"Total blocks: {stats['total_blocks']}")
print(f"Resumes stored: {stats['resume_count']}")
print(f"Job descriptions: {stats['job_description_count']}")
print(f"Users: {stats['user_count']}")
```

---

## Integration with Existing System

### Matching Engine Integration

The matching engine has been updated to use secure storage:

```python
# In matching_engine/matcher.py

class ResumeJDMatcher:
    def __init__(self):
        # Initialize secure storage
        self.secure_storage = SecureDataStorage()
        # ... other initializations
    
    def process_resume(self, resume_path: str):
        # Extract text
        extraction_result = self.text_extractor.extract(resume_path)
        
        # Extract skills
        skills = self.skill_extractor.extract(extraction_result['text'])
        
        # Store securely in blockchain
        resume_data = {
            'text': extraction_result['text'],
            'file_path': resume_path,
            'skills': skills,
            'extraction_method': extraction_result['method']
        }
        
        metadata = self.secure_storage.store_resume(resume_data)
        
        # Continue with matching using decrypted data
        # ...
```

### Authentication System Integration

```python
# In data/auth/accounts.json replacement

# OLD: Plain JSON storage
{
    "users": [
        {"username": "john", "password": "plain123"}  # INSECURE!
    ]
}

# NEW: Blockchain-based storage
storage = SecureDataStorage()
storage.store_user_credentials('john', 'plain123', {
    'email': 'john@example.com',
    'role': 'user'
})

# Verification
if storage.verify_user_credentials('john', 'plain123'):
    # Grant access
    pass
```

---

## Configuration

Add these settings to `config/config.yaml`:

```yaml
# Blockchain Configuration
blockchain:
  difficulty: 4                    # Proof-of-work difficulty (number of leading zeros)
  master_key: "YOUR_MASTER_KEY"   # Encryption master key (keep secret!)
  chain_file: "data/blockchain.json"  # Blockchain storage location
```

**Important**: 
- **Never commit the master key to version control**
- Store it in environment variables in production
- Generate a new key for each deployment

### Generating a Master Key

```python
import secrets
import base64

master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
print(f"Master Key: {master_key}")
# Example output: "x3JvR3JhdGVkX19+VGhpc0lzQVNlY3VyZUtleQ=="
```

---

## Security Considerations

### 1. **Key Management**
- Master key must be kept secret and secure
- Use environment variables for production
- Implement key rotation policies
- Consider hardware security modules (HSM) for critical deployments

### 2. **Access Control**
- Only authorized users can decrypt data
- Implement role-based access control (RBAC)
- Log all access attempts
- Monitor for suspicious activity

### 3. **Network Security**
- Encrypt data in transit (HTTPS/TLS)
- Secure API endpoints
- Implement rate limiting
- Use authentication tokens (JWT)

### 4. **Data Retention**
- Blockchain is immutable - plan retention policies
- Implement data expiry mechanisms
- Comply with data protection regulations (GDPR, CCPA)

### 5. **Backup & Recovery**
- Regularly backup blockchain file
- Encrypt backups
- Test recovery procedures
- Store backups in secure locations

---

## Performance Considerations

### Mining Performance

| Difficulty | Avg. Attempts | Time (CPU) |
|------------|---------------|------------|
| 2          | 256           | ~0.01s     |
| 3          | 4,096         | ~0.1s      |
| 4          | 65,536        | ~1-2s      |
| 5          | 1,048,576     | ~15-30s    |

**Recommendation**: Use difficulty 3-4 for development, 4-5 for production

### Encryption Performance

- AES encryption: ~1-2ms per 1KB of data
- Password hashing: ~50-100ms (intentionally slow)
- Decryption: ~1-2ms per 1KB of data

### Scalability

- Blockchain grows linearly with data
- Current implementation: File-based storage
- For large scale: Consider database backend (PostgreSQL, MongoDB)
- Implement block pruning for old data

---

## Advantages Over Traditional Storage

| Feature | Traditional Storage | Blockchain Storage |
|---------|-------------------|-------------------|
| **Encryption** | Optional | Built-in, mandatory |
| **Audit Trail** | Requires separate logs | Inherent in blockchain |
| **Tampering Detection** | Difficult | Automatic via hashing |
| **Data Integrity** | Vulnerable | Cryptographically guaranteed |
| **Transparency** | Limited | Complete history visible |
| **Trust** | Centralized | Decentralized verification |

---

## Future Enhancements

### 1. **Distributed Blockchain**
- Deploy across multiple nodes
- Consensus mechanisms (Proof-of-Stake)
- Peer-to-peer synchronization

### 2. **Smart Contracts**
- Automated data sharing permissions
- Time-based data expiry
- Conditional access rules

### 3. **Enhanced Privacy**
- Zero-knowledge proofs
- Homomorphic encryption
- Differential privacy

### 4. **Performance Optimization**
- Database backend (PostgreSQL)
- Merkle trees for efficient verification
- Sharding for scalability

### 5. **Compliance Features**
- GDPR right-to-be-forgotten
- Data export capabilities
- Audit report generation

---

## Testing & Validation

### Unit Tests

```python
# Run blockchain tests
python -m pytest tests/test_blockchain.py -v
```

### Integrity Verification

```python
from blockchain import SecureDataStorage

storage = SecureDataStorage()

# Add some test data
storage.store_resume({'text': 'Test resume'}, user_id='test')
storage.store_job_description({'text': 'Test JD'})

# Verify integrity
assert storage.verify_data_integrity() == True
print("✓ All tests passed!")
```

---

## Troubleshooting

### Issue: "Invalid blockchain detected"
**Cause**: Chain file corrupted or tampered
**Solution**: 
```python
# Delete corrupted chain and create new one
import os
os.remove('data/blockchain.json')
storage = SecureDataStorage()  # Creates new chain
```

### Issue: "Decryption failed"
**Cause**: Wrong master key
**Solution**: Ensure correct master key in config.yaml

### Issue: "Block mining too slow"
**Cause**: High difficulty setting
**Solution**: Reduce difficulty in config.yaml

---

## Compliance & Legal

### GDPR Compliance
- **Right to Access**: Users can retrieve their encrypted data
- **Right to Erasure**: Implement off-chain deletion markers
- **Data Portability**: Export functionality included
- **Data Minimization**: Only essential data encrypted

### Data Protection Best Practices
- Encrypt data at rest and in transit
- Implement access controls
- Regular security audits
- Incident response plan
- Data breach notification procedures

---

## References

- [Blockchain Basics](https://en.wikipedia.org/wiki/Blockchain)
- [AES Encryption](https://en.wikipedia.org/wiki/Advanced_Encryption_Standard)
- [SHA-256 Hashing](https://en.wikipedia.org/wiki/SHA-2)
- [Cryptography Library](https://cryptography.io/)
- [GDPR Guidelines](https://gdpr.eu/)

---

## Contact & Support

For questions or issues related to blockchain implementation:
- Review this documentation
- Check logs in `logs/` directory
- Verify configuration in `config/config.yaml`
- Run integrity checks regularly

**Remember**: Keep your master encryption key secure and never share it publicly!
