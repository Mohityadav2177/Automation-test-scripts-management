import paramiko
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sftp_test.py <switch_ip> <username> <password>")
    sys.exit(1)

switch_ip = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

# -------------------------------------------------------
# SFTP Configuration
# -------------------------------------------------------
SFTP_SERVER_IP = "192.168.180.69"
SFTP_USER = "hfcl"
SFTP_PASS = "hfcl%40123"
SFTP_FILE = "test22"
DEST_FILE = "sftptestfile"

WRONG_USER = "wrong"
WRONG_PASS = "wrong123"
WRONG_FILE = "wrongfile"

SFTP_UPLOAD_URL = f"sftp://{SFTP_USER}:{SFTP_PASS}@{SFTP_SERVER_IP}/{SFTP_FILE}"
SFTP_DOWNLOAD_URL = f"sftp://{SFTP_USER}:{SFTP_PASS}@{SFTP_SERVER_IP}/{SFTP_FILE}"
SFTP_WRONG_URL = f"sftp://{WRONG_USER}:{WRONG_PASS}@{SFTP_SERVER_IP}/{WRONG_FILE}"

# Retry config
MAX_RETRIES = 3
RETRY_DELAY = 5

print("=" * 65)
print("TEST CASE : SFTP Functionality Test")
print("=" * 65)

# -------------------------------------------------------
# Step Tracker
# -------------------------------------------------------
step_results = []

def record(step, desc, status, note=""):
    step_results.append((step, desc, "PASS" if status else "FAIL", note))

def summary():
    print("\n" + "="*65)
    print("FINAL RESULT")
    print("="*65)
    overall = True
    for s, d, r, n in step_results:
        print(f"{'✅' if r=='PASS' else '❌'} STEP {s}: {d} -> {r}")
        if n:
            print("   Note:", n)
        if r == "FAIL":
            overall = False
    print("\nOVERALL:", "✅ PASS" if overall else "❌ FAIL")
    print("="*65)

# -------------------------------------------------------
# SSH
# -------------------------------------------------------
def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(switch_ip, username=username, password=password,
                   look_for_keys=False, allow_agent=False)

    shell = client.invoke_shell()
    time.sleep(2)
    shell.send("terminal length 0\n")
    time.sleep(1)

    return client, shell

def send(shell, cmd, timeout=120):
    shell.send(cmd + "\n")
    output = ""
    end_time = time.time() + timeout

    while time.time() < end_time:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode()
            output += chunk

            if "(yes/no)" in chunk.lower():
                shell.send("yes\n")

            if output.rstrip().endswith("#"):
                break
        time.sleep(1)

    return output

# -------------------------------------------------------
# Validation
# -------------------------------------------------------
def success_check(output):
    o = output.lower()
    if any(x in o for x in ["error", "fail", "denied", "invalid"]):
        return False
    return any(x in o for x in ["copied", "success", "complete", "ok", "%"])

def failure_check(output):
    o = output.lower()
    return any(x in o for x in ["error", "fail", "denied", "invalid", "refused"])

# -------------------------------------------------------
# Retry Wrapper
# -------------------------------------------------------
def run_with_retry(shell, cmd, check_func, expect_success=True, desc=""):
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔁 Attempt {attempt}/{MAX_RETRIES} - {desc}")
        output = send(shell, cmd)

        print("\n--- OUTPUT ---")
        print(output.strip() if output.strip() else "(no output)")
        print("--------------")

        result = check_func(output)

        if expect_success and result:
            print("✅ Success")
            return True, output

        if not expect_success and result:
            print("✅ Expected failure observed")
            return True, output

        print(f"⚠️ Retry in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

    return False, output

# ======================================================
# TEST START
# ======================================================

client, shell = connect()
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — SFTP Upload
# -------------------------------------------------------
cmd = f"copy running-config {SFTP_UPLOAD_URL}"
passed, _ = run_with_retry(shell, cmd, success_check, True, "SFTP Upload")

record(2, "SFTP device → server", passed)

# -------------------------------------------------------
# STEP 3 — SFTP Download
# -------------------------------------------------------
cmd = f"copy {SFTP_DOWNLOAD_URL} flash:{DEST_FILE}"
passed, _ = run_with_retry(shell, cmd, success_check, True, "SFTP Download")

record(3, "SFTP server → device", passed)

# -------------------------------------------------------
# STEP 4 — Verify file using dir
# -------------------------------------------------------
print("\n=================================")
print("STEP 4: Verify file in switch using 'dir'")
print("=================================")

output = send(shell, "dir")

print("\n--- DIR OUTPUT ---")
print(output)
print("------------------")

file_present = DEST_FILE.lower() in output.lower()
record(4, f"Verify file '{DEST_FILE}' present in switch", file_present,
       "" if file_present else "File not found in dir output")

# -------------------------------------------------------
# STEP 5 — Wrong Credentials (Negative Test)
# -------------------------------------------------------
cmd = f"copy running-config {SFTP_WRONG_URL}"
passed, _ = run_with_retry(shell, cmd, failure_check, False, "SFTP Wrong Credentials")

record(5, "SFTP with incorrect credentials", passed)

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()
summary()
