import paramiko
import socket
import sys
import time
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_028.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

HTTPS_URL = f"https://{ip}"

# Suppress SSL warnings
if REQUESTS_AVAILABLE:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

print("=" * 60)
print("TEST CASE : HFCL-SW-028")
print("TEST NAME : Management")
print("OBJECTIVE : Validate SSL (HTTPS) configuration and unconfigure")
print("=" * 60)
print(f"Target    : {ip}:22")
print(f"Username  : {username}")
print(f"HTTPS URL : {HTTPS_URL}")
print("=" * 60)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []   # list of (step_number, description, status, note)

def record(step_num, description, passed, note=""):
    status = "PASS" if passed else "FAIL"
    step_results.append((step_num, description, status, note))

# -------------------------------------------------------
# SSH connect
# -------------------------------------------------------
def ssh_connect():
    print(f"\nConnecting to {ip} via SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ip, port=22, username=username, password=password,
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

def send_command(shell, cmd, timeout=20):
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
            if output.rstrip().endswith("#"):
                time.sleep(0.2)
                if shell.recv_ready():
                    output += shell.recv(65535).decode("utf-8", errors="ignore")
                break
        else:
            time.sleep(0.3)
    return output

def check_https_access(url):
    if REQUESTS_AVAILABLE:
        try:
            resp = requests.get(url, verify=False, timeout=10)
            return True, f"HTTP {resp.status_code} — page loaded successfully"
        except requests.exceptions.SSLError:
            return True, "SSL handshake response received (server is up)"
        except requests.exceptions.ConnectionError:
            return False, "Connection refused — HTTPS port is closed"
        except requests.exceptions.Timeout:
            return False, "Connection timed out — HTTPS not responding"
        except Exception as e:
            return False, f"Unreachable — {type(e).__name__}"
    else:
        try:
            sock = socket.create_connection((ip, 443), timeout=10)
            sock.close()
            return True, "TCP port 443 is OPEN — HTTPS is reachable"
        except ConnectionRefusedError:
            return False, "TCP port 443 is CLOSED — HTTPS is not reachable"
        except socket.timeout:
            return False, "Connection to port 443 timed out"
        except Exception as e:
            return False, f"Unreachable — {type(e).__name__}"

def print_https_result(accessible, reason, expect_accessible):
    print("\n--- BROWSER ACCESS RESULT ---")
    print(f"URL      : {HTTPS_URL}")
    print(f"Status   : {'ACCESSIBLE' if accessible else 'NOT ACCESSIBLE'}")
    print(f"Details  : {reason}")
    print(f"Expected : {'ACCESSIBLE' if expect_accessible else 'NOT ACCESSIBLE'}")
    print("-----------------------------")

# -------------------------------------------------------
# STEP 1 — SSH Login
# -------------------------------------------------------
print("=================================")
print("STEP 1: SSH Login")
print("=================================")
client, shell = ssh_connect()
print("✅ STEP 1 PASSED")
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — Configure ip http secure-server
# -------------------------------------------------------
print("\n=================================")
print("STEP 2: Configure SSL (HTTPS)")
print("Command : ip http secure-server")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, "ip http secure-server")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 2 {'PASSED' if passed else 'FAILED'} — ip http secure-server configured")
record(2, "Configure ip http secure-server", passed)

# -------------------------------------------------------
# STEP 3 — Verify with show running-config | include secure-server
# -------------------------------------------------------
print("\n=================================")
print("STEP 3: Verify SSL in running-config")
print("Command : show running-config | include secure-server")
print("=================================")

output = send_command(shell, "show running-config | include secure-server", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "ip http secure-server" in output
print(f"{'✅' if passed else '⚠️ '} STEP 3 {'PASSED' if passed else 'WARNING'} — 'ip http secure-server' {'present' if passed else 'not found'} in running-config")
record(3, "Verify ip http secure-server in running-config", passed)

# -------------------------------------------------------
# STEP 4 — Verify with show ip http
# -------------------------------------------------------
print("\n=================================")
print("STEP 4: Verify HTTPS status")
print("Command : show ip http")
print("=================================")

output = send_command(shell, "show ip http")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "enabled" in output.lower() or "secure" in output.lower()
print(f"{'✅' if passed else '⚠️ '} STEP 4 {'PASSED' if passed else 'WARNING'} — secure server {'enabled' if passed else 'status unclear'}")
record(4, "show ip http — secure server enabled", passed)

# -------------------------------------------------------
# STEP 5 — Browser check (HTTPS should be accessible)
# -------------------------------------------------------
print("\n=================================")
print("STEP 5: Browser check — HTTPS should be ACCESSIBLE")
print(f"URL     : {HTTPS_URL}")
print("=================================")

time.sleep(2)
accessible, reason = check_https_access(HTTPS_URL)
print_https_result(accessible, reason, expect_accessible=True)

passed = accessible
print(f"{'✅' if passed else '❌'} STEP 5 {'PASSED' if passed else 'FAILED'} — HTTPS {'is' if passed else 'is NOT'} accessible")
record(5, f"Browser access HTTPS (expect ACCESSIBLE)", passed, reason)

# -------------------------------------------------------
# STEP 6 — Unconfigure ip http secure-server
# -------------------------------------------------------
print("\n=================================")
print("STEP 6: Remove SSL configuration")
print("Command : no ip http secure-server")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, "no ip http secure-server")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 6 {'PASSED' if passed else 'FAILED'} — no ip http secure-server configured")
record(6, "Remove ip http secure-server (no ip http secure-server)", passed)

# -------------------------------------------------------
# STEP 7 — Verify removed from running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 7: Verify SSL removed from running-config")
print("Command : show running-config | include secure-server")
print("=================================")

output = send_command(shell, "show running-config | include secure-server", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output — entry removed ✅)")
print("---------------------")

passed = "ip http secure-server" not in output
print(f"{'✅' if passed else '❌'} STEP 7 {'PASSED' if passed else 'FAILED'} — 'ip http secure-server' {'absent' if passed else 'still present'} in running-config")
record(7, "Verify ip http secure-server removed from running-config", passed)

# -------------------------------------------------------
# STEP 8 — Verify show ip http shows disabled
# -------------------------------------------------------
print("\n=================================")
print("STEP 8: Verify HTTPS status shows disabled")
print("Command : show ip http")
print("=================================")

output = send_command(shell, "show ip http")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "disabled" in output.lower() or "ip http secure-server" not in output.lower()
print(f"{'✅' if passed else '⚠️ '} STEP 8 {'PASSED' if passed else 'WARNING'} — secure server {'disabled' if passed else 'status unclear'}")
record(8, "show ip http — secure server disabled", passed)

# -------------------------------------------------------
# STEP 9 — Browser check (HTTPS should NOT be accessible)
# -------------------------------------------------------
print("\n=================================")
print("STEP 9: Browser check — HTTPS should be NOT ACCESSIBLE")
print(f"URL     : {HTTPS_URL}")
print("=================================")

time.sleep(3)
accessible, reason = check_https_access(HTTPS_URL)
print_https_result(accessible, reason, expect_accessible=False)

passed = not accessible
print(f"{'✅' if passed else '❌'} STEP 9 {'PASSED' if passed else 'FAILED'} — HTTPS {'correctly blocked' if passed else 'still accessible (unexpected)'}")
record(9, "Browser access HTTPS (expect NOT ACCESSIBLE)", passed, reason)

# -------------------------------------------------------
# STEP 10 — Restore ip http secure-server
# -------------------------------------------------------
print("\n=================================")
print("STEP 10: Restore SSL configuration")
print("Command : ip http secure-server")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, "ip http secure-server")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 10 {'PASSED' if passed else 'FAILED'} — ip http secure-server restored")
record(10, "Restore ip http secure-server", passed)

# -------------------------------------------------------
# STEP 11 — Verify restored in running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 11: Verify SSL restored in running-config")
print("Command : show running-config | include secure-server")
print("=================================")

output = send_command(shell, "show running-config | include secure-server", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "ip http secure-server" in output
print(f"{'✅' if passed else '⚠️ '} STEP 11 {'PASSED' if passed else 'WARNING'} — 'ip http secure-server' {'restored' if passed else 'not found'} in running-config")
record(11, "Verify ip http secure-server restored in running-config", passed)

# -------------------------------------------------------
# STEP 12 — Browser check after restore (should be accessible again)
# -------------------------------------------------------
print("\n=================================")
print("STEP 12: Browser check — HTTPS should be ACCESSIBLE again")
print(f"URL     : {HTTPS_URL}")
print("=================================")

time.sleep(2)
accessible, reason = check_https_access(HTTPS_URL)
print_https_result(accessible, reason, expect_accessible=True)

passed = accessible
print(f"{'✅' if passed else '❌'} STEP 12 {'PASSED' if passed else 'FAILED'} — HTTPS {'accessible after restore' if passed else 'NOT accessible after restore'}")
record(12, "Browser access HTTPS after restore (expect ACCESSIBLE)", passed, reason)

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
print("\n")
print("=" * 60)
print("TEST CASE  : HFCL-SW-028")
print("FINAL STEP SUMMARY")
print("=" * 60)
print(f"{'STEP':<6} {'DESCRIPTION':<45} {'RESULT':<6} {'NOTE'}")
print("-" * 60)

all_passed = True
for step_num, desc, status, note in step_results:
    icon = "✅" if status == "PASS" else "❌"
    note_str = f"  ({note})" if note else ""
    print(f"{icon} {str(step_num):<4} {desc:<45} {status}{note_str}")
    if status == "FAIL":
        all_passed = False

print("-" * 60)
print(f"\nOVERALL RESULT : {'✅ PASS' if all_passed else '❌ FAIL'}")
print("=" * 60)
