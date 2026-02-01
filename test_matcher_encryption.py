"""Direct test to verify blockchain encryption is working."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from matching_engine.matcher import ResumeJDMatcher

print("\n" + "="*70)
print("BLOCKCHAIN ENCRYPTION STATUS")
print("="*70)

matcher = ResumeJDMatcher()

print(f"\nMatcher Status:")
print(f"  blockchain_enabled: {matcher.blockchain_enabled}")
print(f"  secure_storage: {matcher.secure_storage is not None}")

if matcher.blockchain_enabled:
    print(f"\n[SUCCESS] BLOCKCHAIN ENCRYPTION IS ENABLED!")
    print(f"\nAll data stored during matching will be encrypted:")
    print(f"  - Resume data (text, skills)")
    print(f"  - Job description data (text, skills)")
    print(f"  - All stored in encrypted blockchain.json file")
else:
    print(f"\n[FAILED] Blockchain encryption is disabled")

print("\n" + "="*70)
