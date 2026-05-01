import paramiko
import socket
import sys
import time
import subprocess

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_025.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

# -------------------------------------------------------
# Test configuration
# -------------------------------------------------------
VALID_HOSTNAME = "Hfcl-QA-Testing-switch"

# Exactly 255 characters — should be ACCEPTED
HOSTNAME_255 = (
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKL"
)

# Exactly 256 characters — should be REJECTED
HOSTNAME_256 = (
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIKLq"
)

REBOOT_WAIT = 150  # ~2.5 minutes

print("=" * 60)
print("TEST CASE : HFCL-SW-025")
print("TEST NAME : Management")
print("OBJECTIVE : Verify hostname config, invalid hostname rejection,")
print("            and hostname persistence after save + reload warm")
print("=" * 60)
print(f"Target         : {ip}:22")
print(f"Username       : {username}")
print(f"Valid hostname : {VALID_HOSTNAME}")
print(f"255-char len   : {len(HOSTNAME_255)}")
print(f"256-char len   : {len(HOSTNAME_256)}")
print("=" * 60)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []

def record(step_num, description, passed, note=""):
    step_results.append((step_num, description, "PASS" if passed else "FAIL", note))

# -------------------------------------------------------
# SSH helpers
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

def ping_host(host, retries=3):
    for _ in range(retries):
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if r.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def print_final_summary():
    print("\n")
    print("=" * 65)
    print("TEST CASE  : HFCL-SW-025")
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

# ======================================================
# TEST EXECUTION
# ======================================================

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
# STEP 2 — Set valid hostname
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 2: Set valid hostname '{VALID_HOSTNAME}'")
print(f"Command : hostname {VALID_HOSTNAME}")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, f"hostname {VALID_HOSTNAME}")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower() and "% " not in output
print(f"{'✅' if passed else '❌'} STEP 2 {'PASSED' if passed else 'FAILED'} — hostname '{VALID_HOSTNAME}' {'accepted' if passed else 'rejected'}")
record(2, f"Set valid hostname '{VALID_HOSTNAME}'", passed)

# -------------------------------------------------------
# STEP 3 — Verify valid hostname in show running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 3: Verify valid hostname in show running-config")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = f"hostname {VALID_HOSTNAME}" in output
print(f"{'✅' if passed else '❌'} STEP 3 {'PASSED' if passed else 'FAILED'} — 'hostname {VALID_HOSTNAME}' {'found' if passed else 'NOT found'} in running-config")
record(3, f"Verify 'hostname {VALID_HOSTNAME}' in running-config", passed)

# -------------------------------------------------------
# STEP 4 — Set 255-character hostname (should be ACCEPTED)
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 4: Set 255-character hostname (should be ACCEPTED)")
print(f"Length  : {len(HOSTNAME_255)} characters")
print(f"Command : hostname {HOSTNAME_255[:50]}...")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, f"hostname {HOSTNAME_255}")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

is_rejected = "error" in output.lower() or "invalid" in output.lower() or "% " in output
passed = not is_rejected
print(f"{'✅' if passed else '❌'} STEP 4 {'PASSED' if passed else 'FAILED'} — 255-char hostname {'accepted as expected' if passed else 'rejected (unexpected)'}")
record(4, "Set 255-char hostname (expect ACCEPTED)", passed,
       "" if passed else "Switch rejected 255-char hostname — check switch limit")

# Restore valid hostname after 255-char test
send_command(shell, "configure terminal")
send_command(shell, f"hostname {VALID_HOSTNAME}")
send_command(shell, "end")

# -------------------------------------------------------
# STEP 5 — Set 256-character hostname (should be REJECTED)
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 5: Set 256-character hostname (should be REJECTED with error)")
print(f"Length  : {len(HOSTNAME_256)} characters")
print(f"Command : hostname {HOSTNAME_256[:50]}...")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, f"hostname {HOSTNAME_256}")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

is_rejected = "error" in output.lower() or "invalid" in output.lower() or "% " in output
passed = is_rejected
print(f"{'✅' if passed else '❌'} STEP 5 {'PASSED' if passed else 'FAILED'} — 256-char hostname {'rejected as expected' if passed else 'accepted (unexpected — should have been rejected)'}")
record(5, "Set 256-char hostname (expect REJECTED with error)", passed,
       "Rejected as expected" if passed else "WARNING: Switch accepted 256-char hostname")

# -------------------------------------------------------
# STEP 6 — Verify 256-char hostname NOT in running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 6: Verify 256-char hostname NOT applied in running-config")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

invalid_applied = HOSTNAME_256 in output
valid_present   = f"hostname {VALID_HOSTNAME}" in output
passed          = not invalid_applied and valid_present

print(f"  256-char hostname in config   : {'❌ YES — unexpected' if invalid_applied else '✅ NO — correct'}")
print(f"  Valid hostname still present  : {'✅ YES' if valid_present else '❌ NO'}")
print(f"{'✅' if passed else '❌'} STEP 6 {'PASSED' if passed else 'FAILED'} — invalid hostname not applied, valid hostname retained")
record(6, "Verify 256-char hostname NOT applied, valid retained", passed)

# -------------------------------------------------------
# STEP 7 — Save config
# -------------------------------------------------------
print("\n=================================")
print("STEP 7: Save running-config to startup-config")
print("Command : copy running-config startup-config")
print("=================================")

output = send_command(shell, "copy running-config startup-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "error" not in output.lower() and "failed" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 7 {'PASSED' if passed else 'FAILED'} — config saved to startup-config")
record(7, "Save config (copy running-config startup-config)", passed)

# -------------------------------------------------------
# STEP 8 — Reload warm
# -------------------------------------------------------
print("\n=================================")
print("STEP 8: Reload device with 'reload warm'")
print("Command : reload warm")
print("=================================")
print(f"⚠️  Device rebooting — waiting {REBOOT_WAIT}s (~2.5 min)...")

shell.send("reload warm\n")
time.sleep(2)
shell.send("y\n")
time.sleep(2)
client.close()

for remaining in range(REBOOT_WAIT, 0, -10):
    print(f"    ... {remaining}s remaining")
    time.sleep(10)

print("✅ STEP 8 PASSED — reload warm sent, waiting complete")
record(8, "Reload device (reload warm)", True)

# -------------------------------------------------------
# STEP 9 — Ping check after reboot
# -------------------------------------------------------
print("\n=================================")
print("STEP 9: Ping check after reboot")
print(f"Target  : {ip}")
print("=================================")

ping_ok = ping_host(ip, retries=3)

print("\n--- PING RESULT ---")
if ping_ok:
    print(f"Host {ip} is reachable ✅")
    print("-------------------")
    print(f"✅ STEP 9 PASSED — device reachable at {ip}")
    record(9, f"Ping check after reboot — {ip} reachable", True)
else:
    print(f"Host {ip} is NOT reachable")
    print(f"⚠️  Management IP may have changed via DHCP.")
    print(f"    Please check DHCP server for the new IP address.")
    print("-------------------")
    print("⚠️  STEP 9 INFO — IP may have changed, skipping SSH reconnect")
    record(9, f"Ping check — {ip} reachable after reboot", False,
           "IP may have changed via DHCP — check DHCP server for new IP")
    print_final_summary()
    sys.exit(0)

# -------------------------------------------------------
# STEP 10 — Reconnect after reboot
# -------------------------------------------------------
print("\n=================================")
print("STEP 10: Reconnect via SSH after reboot")
print("=================================")

MAX_RETRIES = 10
client, shell = None, None
for attempt in range(1, MAX_RETRIES + 1):
    print(f"    Connection attempt {attempt}/{MAX_RETRIES}...")
    try:
        client, shell = ssh_connect()
        break
    except SystemExit:
        if attempt < MAX_RETRIES:
            print(f"    Not ready yet, retrying in 15s...")
            time.sleep(15)
        else:
            print("❌ STEP 10 FAILED — could not reconnect after reboot")
            record(10, "Reconnect via SSH after reboot", False, "Max retries exceeded")
            print_final_summary()
            sys.exit(1)

print("✅ STEP 10 PASSED — reconnected successfully")
record(10, "Reconnect via SSH after reboot", True)

# -------------------------------------------------------
# STEP 11 — Verify hostname persists after reload warm
# -------------------------------------------------------
print("\n=================================")
print("STEP 11: Verify hostname persists after save + reload warm")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = f"hostname {VALID_HOSTNAME}" in output
print(f"{'✅' if passed else '❌'} STEP 11 {'PASSED' if passed else 'FAILED'} — hostname '{VALID_HOSTNAME}' {'persists after reload warm' if passed else 'NOT found after reload warm'}")
record(11, f"Verify hostname '{VALID_HOSTNAME}' persists after reload warm", passed,
       "Hostname retained as expected" if passed else "Hostname lost after reboot — config may not have saved")

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
