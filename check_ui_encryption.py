"""Quick verification that blockchain encryption is enabled in UI."""
import sys
import subprocess
import time
import threading

def monitor_output():
    """Monitor the UI startup logs for blockchain status."""
    process = subprocess.Popen(
        [sys.executable, "main.py", "--ui"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    blockchain_found = False
    start_time = time.time()
    
    print("Monitoring logs for blockchain encryption status...\n")
    
    for line in process.stdout:
        if any(keyword in line for keyword in ["blockchain", "encryption", "Blockchain", "Encryption"]):
            print(line.rstrip())
            if "Blockchain encryption: ENABLED" in line:
                blockchain_found = True
        
        # Stop after 30 seconds or if we found the status
        if time.time() - start_time > 30 or blockchain_found:
            process.terminate()
            break
    
    if blockchain_found:
        print("\n✅ BLOCKCHAIN ENCRYPTION ENABLED IN UI!")
    else:
        print("\n⚠️ Could not confirm blockchain status")

if __name__ == "__main__":
    monitor_output()
