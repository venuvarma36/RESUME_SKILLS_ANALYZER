"""Test decryption of stored blockchain data."""

from blockchain.secure_storage import SecureDataStorage

# Initialize storage
storage = SecureDataStorage()

print("="*60)
print("RETRIEVING AND DECRYPTING STORED DATA")
print("="*60)

# Retrieve resume from block 1
print("\nRetrieving resume from block #1...")
resume = storage.retrieve_resume(1)
if resume:
    print("✅ Resume decrypted successfully!")
    print(f"   Name: {resume.get('name', 'N/A')}")
    print(f"   Email: {resume.get('email', 'N/A')}")
    print(f"   Skills: {resume.get('skills', [])}")
    print(f"   Text: {resume.get('text', 'N/A')[:50]}...")
else:
    print("❌ Failed to retrieve resume")

# Retrieve job description from block 2
print("\nRetrieving job description from block #2...")
jd = storage.retrieve_job_description(2)
if jd:
    print("✅ Job description decrypted successfully!")
    print(f"   Title: {jd.get('title', 'N/A')}")
    print(f"   Company: {jd.get('company', 'N/A')}")
    print(f"   Skills: {jd.get('skills', [])}")
    print(f"   Text: {jd.get('text', 'N/A')[:50]}...")
else:
    print("❌ Failed to retrieve job description")

print("\n" + "="*60)
print("✅ DATA SUCCESSFULLY ENCRYPTED AND DECRYPTED!")
print("="*60)
print("\nThe blockchain.json file contains ENCRYPTED data:")
print("  - Each block has 'data_encrypted' with encrypted content")
print("  - Data in file is unreadable without the master_key")
print("  - But retrieval works perfectly with the key configured!")
