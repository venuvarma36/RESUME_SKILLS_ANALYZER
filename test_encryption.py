"""Test script to verify blockchain encryption."""

from blockchain.secure_storage import SecureDataStorage

# Initialize storage
storage = SecureDataStorage()

# Test storing resume data
resume_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "JavaScript", "React"],
    "text": "Senior Developer with 10 years experience"
}

print("Storing resume data...")
resume_result = storage.store_resume(resume_data, user_id="user123")
print(f"✅ Resume stored at block #{resume_result['block_index']}")
print(f"   Block hash: {resume_result['block_hash'][:20]}...")

# Test storing job description
jd_data = {
    "title": "Senior Python Developer",
    "company": "Tech Corp",
    "skills": ["Python", "Django", "PostgreSQL"],
    "text": "Looking for a senior developer with Python expertise"
}

print("\nStoring job description...")
jd_result = storage.store_job_description(jd_data, company="Tech Corp")
print(f"✅ Job description stored at block #{jd_result['block_index']}")
print(f"   Block hash: {jd_result['block_hash'][:20]}...")

print("\n" + "="*60)
print("Storage Statistics:")
print("="*60)
stats = storage.get_storage_stats()
print(f"Total blocks: {stats['total_blocks']}")
print(f"Resume blocks: {stats['resume_count']}")
print(f"Job description blocks: {stats['job_description_count']}")
print(f"Blockchain valid: {stats['is_valid']}")

print("\n" + "="*60)
print("Blockchain file (blockchain.json) now contains ENCRYPTED data!")
print("="*60)
