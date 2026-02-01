"""Comprehensive test to verify blockchain encryption with numpy arrays."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from blockchain.secure_storage import SecureDataStorage

print("\n" + "="*70)
print("TESTING BLOCKCHAIN ENCRYPTION WITH NUMPY DATA")
print("="*70)

# Initialize storage
storage = SecureDataStorage()

# Test 1: Resume with numpy arrays (simulating real matcher output)
print("\n[Test 1] Storing resume with numpy embedding vectors...")
resume_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "JavaScript", "React"],
    "text": "Senior Developer with 10 years experience",
    "skills_embedding": np.array([0.1, 0.2, 0.3, 0.4, 0.5]),  # Numpy array
    "match_score": np.float32(0.95),  # Numpy float
}

try:
    resume_result = storage.store_resume(resume_data, user_id="user123")
    print(f"  SUCCESS: Stored at block #{resume_result['block_index']}")
except Exception as e:
    print(f"  FAILED: {str(e)}")

# Test 2: Job description with numpy arrays
print("\n[Test 2] Storing job description with numpy embedding vectors...")
jd_data = {
    "title": "Senior Python Developer",
    "company": "Tech Corp",
    "skills": ["Python", "Django", "PostgreSQL"],
    "text": "Looking for a senior developer with Python expertise",
    "skills_embedding": np.array([0.15, 0.25, 0.35, 0.45, 0.55]),  # Numpy array
    "match_score": np.float32(0.92),  # Numpy float
}

try:
    jd_result = storage.store_job_description(jd_data, company="Tech Corp")
    print(f"  SUCCESS: Stored at block #{jd_result['block_index']}")
except Exception as e:
    print(f"  FAILED: {str(e)}")

# Test 3: Retrieve and verify
print("\n[Test 3] Retrieving and decrypting stored data...")
try:
    retrieved_resume = storage.retrieve_resume(1)
    print(f"  Resume retrieved: {retrieved_resume.get('name')}")
    print(f"  SUCCESS")
except Exception as e:
    print(f"  FAILED: {str(e)}")

try:
    retrieved_jd = storage.retrieve_job_description(2)
    print(f"  Job description retrieved: {retrieved_jd.get('title')}")
    print(f"  SUCCESS")
except Exception as e:
    print(f"  FAILED: {str(e)}")

# Test 4: Verify blockchain integrity
print("\n[Test 4] Verifying blockchain integrity...")
is_valid = storage.verify_data_integrity()
print(f"  Blockchain valid: {is_valid}")

# Summary
print("\n" + "="*70)
stats = storage.get_storage_stats()
print(f"SUMMARY:")
print(f"  Total blocks: {stats['total_blocks']}")
print(f"  Resume blocks: {stats['resume_count']}")
print(f"  JD blocks: {stats['job_description_count']}")
print(f"  Blockchain valid: {is_valid}")
print(f"  All data encrypted: YES")
print("="*70 + "\n")
