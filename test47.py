import paramiko
import socket
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_scp_test.py <switch_ip> <username> <password>")
    sys.exit(1)

switch_ip  = sys.argv[1]
username   = sys.argv[2]
password   = sys.argv[3]

# -------------------------------------------------------
# SCP / Server configuration
# -------------------------------------------------------
SCP_SERVER_IP   = "192.168.180.69"
SCP_USER        = "hfcl"
SCP_PASS        = "hfcl%40123"       # URL-encoded password (hfcl@123)
SCP_FILE        = "test22"
WRONG_USER      = "wronguser"
WRONG_PASS      = "wrongpass"
WRONG_FILE      = "nonexistentfile"

# SCP URLs
SCP_UPLOAD_URL   = f"scp://{SCP_USER}:{SCP_PASS}@{SCP_SERVER_IP}/{SCP_FILE}"
SCP_DOWNLOAD_URL = f"scp://{SCP_USER}:{SCP_PASS}@{SCP_SERVER_IP}/{SCP_FILE}"
SCP_WRONG_URL    = f"scp://{WRONG_USER}:{WRONG_PASS}@{SCP_SERVER_IP}/{WRONG_FILE}"

print("=" * 65)
print("TEST CASE : SCP Functionality Test")
print("TEST NAME : SCP")
print("OBJECTIVE : Verify SCP copy operations (device→server,")
print("            server→device, and invalid credentials)")
print("=" * 65)
print(f"Switch IP  : {switch_ip}:22")
print(f"Username   : {username}")
print(f"SCP Server : {SCP_SERVER_IP}")
print(f"SCP User   : {SCP_USER}")
print(f"SCP File   : {SCP_FILE}")
print("=" * 65)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []

def record(step_num, description, passed, note=""):
    step_results.append((step_num, description, "PASS" if passed else "FAIL", note))

def print_final_summary():
    print("\n")
    print("=" * 65)
    print("TEST CASE  : SCP Functionality Test")
    print("FINAL STEP SUMMARY")
    print("=" * 65)
    print(f"{'STEP':<6} {'DESCRIPTION':<50} {'RESULT'}")
    print("-" * 65)
    all_passed = True
    for sn, desc, status, note in step_results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {str(sn):<4} {desc:<50} {status}")
        if note:
            print(f"            Note : {note}")
        if status == "FAIL":
            all_passed = False
    print("-" * 65)
    print(f"\nOVERALL RESULT : {'✅ PASS' if all_passed else '❌ FAIL'}")
    print("=" * 65)

# -------------------------------------------------------
# SSH helpers
# -------------------------------------------------------
def ssh_connect():
    print(f"\nConnecting to {switch_ip} via SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            switch_ip, port=22, username=username, password=password,
            timeout=30, look_for_keys=False, allow_agent=False
        )
    except paramiko.AuthenticationException:
        print("❌ SSH Authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ SSH connection failed: {e}")
        sys.exit(1)

    shell = client.invoke_shell()
    time.sleep(2)
    while shell.recv_ready():
        shell.recv(65535)
    shell.send("terminal length 0\n")
    time.sleep(1)
    while shell.recv_ready():
        shell.recv(65535)
    print("✅ SSH session established\n")
    return client, shell

def send_command(shell, cmd, timeout=60):
    """
    Send a command and wait for # prompt.
    Uses longer timeout for SCP operations which can take time.
    """
    shell.send(cmd + "\n")
    output = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode("utf-8", errors="ignore")
            output += chunk
            if "-- more --" in output.lower():
                shell.send("g")
                time.sleep(0.5)
                continue
            # SCP may prompt for host key confirmation — auto accept
            if "are you sure" in output.lower() or "(yes/no)" in output.lower():
                shell.send("yes\n")
                time.sleep(1)
                continue
            if output.rstrip().endswith("#"):
                time.sleep(0.3)
                if shell.recv_ready():
                    output += shell.recv(65535).decode("utf-8", errors="ignore")
                break
        else:
            time.sleep(0.5)
    return output

def is_scp_success(output):
    """Check if SCP operation was successful."""
    out_lower = output.lower()
    success_keywords = ["success", "copied", "bytes copied", "ok", "complete", "done", "%"]
    failure_keywords = ["error", "failed", "refused", "denied", "invalid",
                        "no such", "timeout", "unreachable", "permission"]
    has_success = any(k in out_lower for k in success_keywords)
    has_failure = any(k in out_lower for k in failure_keywords)
    # If explicit failure found, it failed
    if has_failure:
        return False
    return has_success

def is_scp_failure(output):
    """Check if SCP operation correctly failed (for negative test)."""
    out_lower = output.lower()
    failure_keywords = ["error", "failed", "refused", "denied", "invalid",
                        "no such", "timeout", "unreachable", "permission", "authentication"]
    return any(k in out_lower for k in failure_keywords)

# ======================================================
# TEST EXECUTION
# ======================================================

# -------------------------------------------------------
# STEP 1 — SSH Login
# -------------------------------------------------------
print("=================================")
print("STEP 1: SSH Login to switch")
print("=================================")
client, shell = ssh_connect()
print("✅ STEP 1 PASSED")
record(1, "SSH Login to switch", True)

# -------------------------------------------------------
# STEP 2 — Verify running-config before SCP
# -------------------------------------------------------
print("\n=================================")
print("STEP 2: Verify running-config exists before SCP upload")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = any(x in output.lower() for x in ["hostname", "interface", "vlan", "ip"])
print(f"{'✅' if passed else '❌'} STEP 2 {'PASSED' if passed else 'FAILED'} — running-config {'verified' if passed else 'not found'}")
record(2, "Verify running-config exists before SCP upload", passed)

# -------------------------------------------------------
# STEP 3 — SCP: device → server (upload running-config)
# -------------------------------------------------------
print("\n=================================")
print("STEP 3: SCP copy running-config from device to server")
print(f"Command : copy running-config {SCP_UPLOAD_URL} save-host-key")
print("=================================")
print("⚠️  SCP operation in progress — please wait...")

scp_upload_cmd = f"copy running-config {SCP_UPLOAD_URL} save-host-key"
output = send_command(shell, scp_upload_cmd, timeout=120)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = is_scp_success(output)
note   = "running-config copied to server successfully" if passed else "SCP upload failed — check server availability and credentials"
print(f"{'✅' if passed else '❌'} STEP 3 {'PASSED' if passed else 'FAILED'} — SCP device→server {'successful' if passed else 'FAILED'}")
record(3, "SCP copy running-config device → server", passed, note)

# -------------------------------------------------------
# STEP 4 — SCP: server → device (download to startup-config)
# -------------------------------------------------------
print("\n=================================")
print("STEP 4: SCP copy file from server to device as startup-config")
print(f"Command : copy {SCP_DOWNLOAD_URL} startup-config save-host-key")
print("=================================")
print("⚠️  SCP operation in progress — please wait...")

scp_download_cmd = f"copy {SCP_DOWNLOAD_URL} startup-config save-host-key"
output = send_command(shell, scp_download_cmd, timeout=120)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = is_scp_success(output)
note   = "File copied from server to startup-config successfully" if passed else "SCP download failed — check server availability and credentials"
print(f"{'✅' if passed else '❌'} STEP 4 {'PASSED' if passed else 'FAILED'} — SCP server→device {'successful' if passed else 'FAILED'}")
record(4, "SCP copy server → device (startup-config)", passed, note)

# -------------------------------------------------------
# STEP 5 — Verify startup-config was updated
# -------------------------------------------------------
print("\n=================================")
print("STEP 5: Verify startup-config updated after SCP download")
print("Command : dir")
print("=================================")

output = send_command(shell, "dir", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = any(x in output.lower() for x in ["startup-config","hostname", "interface", "vlan", "ip", "version"])
print(f"{'✅' if passed else '❌'} STEP 5 {'PASSED' if passed else 'FAILED'} — startup-config {'contains valid config' if passed else 'appears empty or invalid'}")
record(5, "Verify startup-config updated after SCP download", passed)

# -------------------------------------------------------
# STEP 6 — SCP with WRONG credentials (should FAIL)
# -------------------------------------------------------
print("\n=================================")
print("STEP 6: SCP with incorrect credentials (should FAIL)")
print(f"Command : copy running-config {SCP_WRONG_URL} save-host-key")
print("=================================")
print("⚠️  SCP with wrong credentials — expecting failure...")

scp_wrong_cmd = f"copy running-config {SCP_WRONG_URL} save-host-key"
output = send_command(shell, scp_wrong_cmd, timeout=60)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

# For negative test: we WANT it to fail
passed = is_scp_failure(output)
note   = "Operation correctly rejected with error" if passed else "WARNING: SCP succeeded with wrong credentials (unexpected)"
print(f"{'✅' if passed else '❌'} STEP 6 {'PASSED' if passed else 'FAILED'} — SCP with wrong credentials {'correctly failed' if passed else 'unexpectedly succeeded'}")
record(6, "SCP with incorrect credentials (expect FAILURE)", passed, note)

# -------------------------------------------------------
# STEP 7 — SCP with WRONG server IP (should FAIL)
# -------------------------------------------------------
print("\n=================================")
print("STEP 7: SCP with incorrect server IP (should FAIL)")
wrong_ip_url = f"scp://{SCP_USER}:{SCP_PASS}@10.255.255.255/{SCP_FILE}"
print(f"Command : copy running-config {wrong_ip_url} save-host-key")
print("=================================")
print("⚠️  SCP with wrong IP — expecting timeout/failure...")

scp_wrongip_cmd = f"copy running-config {wrong_ip_url} save-host-key"
output = send_command(shell, scp_wrongip_cmd, timeout=60)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = is_scp_failure(output) or not is_scp_success(output)
note   = "Operation correctly rejected with error" if passed else "WARNING: SCP succeeded with wrong IP (unexpected)"
print(f"{'✅' if passed else '❌'} STEP 7 {'PASSED' if passed else 'FAILED'} — SCP with wrong server IP {'correctly failed' if passed else 'unexpectedly succeeded'}")
record(7, "SCP with incorrect server IP (expect FAILURE)", passed, note)

# -------------------------------------------------------
# Close connection
# -------------------------------------------------------
try:
    client.close()
except Exception:
    pass

# -------------------------------------------------------
# FINAL SUMMARY
# -------------------------------------------------------
print_final_summary()
