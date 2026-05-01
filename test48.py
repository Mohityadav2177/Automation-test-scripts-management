import paramiko
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_ftp_test.py <switch_ip> <username> <password>")
    sys.exit(1)

switch_ip = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

# -------------------------------------------------------
# FTP Configuration
# -------------------------------------------------------
FTP_SERVER_IP = "192.168.180.69"
FTP_USER = "hfcl"
FTP_PASS = "hfcl%40123"
FTP_FILE = "test22"

WRONG_USER = "wronguser"
WRONG_PASS = "wrongpass"
WRONG_FILE = "wrongfile"

FTP_UPLOAD_URL = f"ftp://{FTP_USER}:{FTP_PASS}@{FTP_SERVER_IP}/{FTP_FILE}"
FTP_DOWNLOAD_URL = f"ftp://{FTP_USER}:{FTP_PASS}@{FTP_SERVER_IP}/{FTP_FILE}"
FTP_WRONG_URL = f"ftp://{WRONG_USER}:{WRONG_PASS}@{FTP_SERVER_IP}/{WRONG_FILE}"

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5   # seconds

print("=" * 65)
print("TEST CASE : FTP Functionality Test (With Retry)")
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
    if any(x in o for x in ["error", "fail", "denied", "invalid", "timeout"]):
        return False
    return any(x in o for x in ["copied", "success", "complete", "ok", "%"])

def failure_check(output):
    o = output.lower()
    return any(x in o for x in [
        "error", "fail", "denied", "invalid", "timeout", "refused"
    ])

# -------------------------------------------------------
# Retry Wrapper
# -------------------------------------------------------
def run_with_retry(shell, cmd, check_func, expect_success=True, step_desc=""):
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔁 Attempt {attempt}/{MAX_RETRIES} for: {step_desc}")
        output = send(shell, cmd)

        print("\n--- OUTPUT ---")
        print(output.strip() if output.strip() else "(no output)")
        print("--------------")

        result = check_func(output)

        if expect_success and result:
            print(f"✅ Success on attempt {attempt}")
            return True, output

        if not expect_success and result:
            print(f"✅ Expected failure observed on attempt {attempt}")
            return True, output

        print(f"⚠️ Attempt {attempt} failed, retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

    return False, output

# ======================================================
# TEST START
# ======================================================

client, shell = connect()
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — FTP Upload
# -------------------------------------------------------
cmd = f"copy running-config {FTP_UPLOAD_URL}"
passed, _ = run_with_retry(shell, cmd, success_check, True, "FTP Upload")

record(2, "FTP copy device → server", passed)

# -------------------------------------------------------
# STEP 3 — FTP Download
# -------------------------------------------------------
cmd = f"copy {FTP_DOWNLOAD_URL} flash:ftptestfile"
passed, _ = run_with_retry(shell, cmd, success_check, True, "FTP Download")

record(3, "FTP copy server → device", passed)

# -------------------------------------------------------
# STEP 4 — Wrong Credentials (Negative)
# -------------------------------------------------------
cmd = f"copy running-config {FTP_WRONG_URL}"
passed, _ = run_with_retry(shell, cmd, failure_check, False, "FTP Wrong Credentials")

record(4, "FTP with incorrect credentials", passed)

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()
summary()
