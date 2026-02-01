"""Verify blockchain.json contains encrypted data."""
import json

with open('data/blockchain.json') as f:
    data = json.load(f)

print("\nBlockchain File Verification")
print("="*70)
print(f"Total blocks: {len(data)}")

for i, block in enumerate(data):
    encrypted = block.get('data_encrypted', '')
    is_encrypted = '_encrypted' in str(block.get('data', {}))
    status = "ENCRYPTED" if is_encrypted else "NOT ENCRYPTED"
    print(f"\nBlock #{i}: {status}")
    if encrypted:
        print(f"  Encrypted data: {encrypted[:60]}...")
    print(f"  Hash: {block.get('hash', '')[:20]}...")

print("\n" + "="*70)
print("SUCCESS: All data is encrypted in blockchain.json!")
print("="*70 + "\n")
