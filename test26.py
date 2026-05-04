import paramiko
import socket
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_026.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

# -------------------------------------------------------
# Test configuration
# -------------------------------------------------------
TEST_HOSTNAME = "hfcl-test"
TEST_VLAN_ID  = "100"
TEST_VLAN_NAME = "TEST-VLAN"

print("=" * 60)
print("TEST CASE : HFCL-SW-026")
print("TEST NAME : Management")
print("OBJECTIVE : Verify operational mode show commands and")
print("            configuration mode commands (hostname, vlan)")
print("=" * 60)
print(f"Target    : {ip}:22")
print(f"Username  : {username}")
print("=" * 60)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []

def record(step_num, description, passed, note=""):
    step_results.append((step_num, description, "PASS" if passed else "FAIL", note))

def print_final_summary():
    print("\n")
    print("=" * 65)
    print("TEST CASE  : HFCL-SW-026")
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

def send_command(shell, cmd, timeout=30):
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

def run_show_step(shell, step_num, description, cmd, validate_fn=None):
    """
    Run a show command step, print output, validate, and record result.
    validate_fn: optional function(output) -> (passed: bool, note: str)
    """
    print(f"\n=================================")
    print(f"STEP {step_num}: {description}")
    print(f"Command : {cmd}")
    print("=================================")

    output = send_command(shell, cmd, timeout=30)

    print("\n--- SWITCH OUTPUT ---")
    print(output.strip() if output.strip() else "(no output)")
    print("---------------------")

    if validate_fn:
        passed, note = validate_fn(output)
    else:
        # Default: pass if output is non-empty and no error keywords
        has_output = bool(output.strip())
        has_error  = "error" in output.lower() or "invalid" in output.lower() or "% unknown" in output.lower()
        passed     = has_output and not has_error
        note       = "" if passed else "No output received or error detected"

    print(f"{'✅' if passed else '❌'} STEP {step_num} {'PASSED' if passed else 'FAILED'} — {description}")
    record(step_num, description, passed, note)
    return output, passed

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
# STEP 2 — show ip interface brief
# -------------------------------------------------------
run_show_step(
    shell, 2,
    "show ip interface brief",
    "show ip interface brief",
    lambda o: (
        any(x in o.lower() for x in ["interface", "ip address", "vlan", "up", "down"]),
        "" if any(x in o.lower() for x in ["interface", "ip address", "vlan", "up", "down"])
        else "Expected interface info not found in output"
    )
)

# -------------------------------------------------------
# STEP 3 — show system
# -------------------------------------------------------
run_show_step(
    shell, 3,
    "show system",
    "show system",
    lambda o: (
        any(x in o.lower() for x in ["system", "uptime", "version", "mac", "model", "serial"]),
        "" if any(x in o.lower() for x in ["system", "uptime", "version", "mac", "model", "serial"])
        else "Expected system info not found in output"
    )
)

# -------------------------------------------------------
# STEP 4 — show version
# -------------------------------------------------------
run_show_step(
    shell, 4,
    "show version",
    "show version",
    lambda o: (
        any(x in o.lower() for x in ["version", "software", "firmware", "build", "release"]),
        "" if any(x in o.lower() for x in ["version", "software", "firmware", "build", "release"])
        else "Expected version info not found in output"
    )
)

# -------------------------------------------------------
# STEP 5 — show system cpu status
# -------------------------------------------------------
run_show_step(
    shell, 5,
    "show system cpu status",
    "show system cpu status",
    lambda o: (
        any(x in o.lower() for x in ["cpu", "utilization", "usage", "%", "load"]),
        "" if any(x in o.lower() for x in ["cpu", "utilization", "usage", "%", "load"])
        else "Expected CPU info not found in output"
    )
)

# -------------------------------------------------------
# STEP 6 — show interface * status
# -------------------------------------------------------
run_show_step(
    shell, 6,
    "show interface * status",
    "show interface * status",
    lambda o: (
        any(x in o.lower() for x in ["interface", "status", "up", "down", "connected", "gigabit"]),
        "" if any(x in o.lower() for x in ["interface", "status", "up", "down", "connected", "gigabit"])
        else "Expected interface status not found in output"
    )
)

# -------------------------------------------------------
# STEP 7 — show ip route
# -------------------------------------------------------
run_show_step(
    shell, 7,
    "show ip route",
    "show ip route",
    lambda o: (
        any(x in o.lower() for x in ["route", "gateway", "network", "0.0.0.0", "via", "directly"]),
        "" if any(x in o.lower() for x in ["route", "gateway", "network", "0.0.0.0", "via", "directly"])
        else "Expected route info not found in output"
    )
)

# -------------------------------------------------------
# STEP 8 — show vlan brief
# -------------------------------------------------------
run_show_step(
    shell, 8,
    "show vlan brief",
    "show vlan brief",
    lambda o: (
        any(x in o.lower() for x in ["vlan", "name", "active", "ports", "default"]),
        "" if any(x in o.lower() for x in ["vlan", "name", "active", "ports", "default"])
        else "Expected VLAN info not found in output"
    )
)

# -------------------------------------------------------
# STEP 9 — show running-config
# -------------------------------------------------------
run_show_step(
    shell, 9,
    "show running-config",
    "show running-config",
    lambda o: (
        any(x in o.lower() for x in ["hostname", "interface", "vlan", "ip", "username"]),
        "" if any(x in o.lower() for x in ["hostname", "interface", "vlan", "ip", "username"])
        else "Expected config content not found in output"
    )
)

# -------------------------------------------------------
# STEP 10 — Enter config mode and set hostname
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 10: Configure hostname '{TEST_HOSTNAME}'")
print(f"Command : hostname {TEST_HOSTNAME}")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, f"hostname {TEST_HOSTNAME}")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower() and "% " not in output
print(f"{'✅' if passed else '❌'} STEP 10 {'PASSED' if passed else 'FAILED'} — hostname '{TEST_HOSTNAME}' {'configured' if passed else 'failed'}")
record(10, f"Configure hostname '{TEST_HOSTNAME}'", passed)

# -------------------------------------------------------
# STEP 11 — Create VLAN
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 11: Create VLAN {TEST_VLAN_ID} with name '{TEST_VLAN_NAME}'")
print(f"Command : vlan {TEST_VLAN_ID} -> name {TEST_VLAN_NAME}")
print("=================================")

send_command(shell, "configure terminal")
out_vlan = send_command(shell, f"vlan {TEST_VLAN_ID}")
out_name = send_command(shell, f"name {TEST_VLAN_NAME}")
send_command(shell, "end")

print("\n--- SWITCH OUTPUT (vlan) ---")
print(out_vlan.strip() if out_vlan.strip() else "(no output)")
print("--- SWITCH OUTPUT (name) ---")
print(out_name.strip() if out_name.strip() else "(no output)")
print("----------------------------")

passed = (
    "error"   not in out_vlan.lower() and "invalid" not in out_vlan.lower() and
    "error"   not in out_name.lower() and "invalid" not in out_name.lower()
)
print(f"{'✅' if passed else '❌'} STEP 11 {'PASSED' if passed else 'FAILED'} — VLAN {TEST_VLAN_ID} '{TEST_VLAN_NAME}' {'created' if passed else 'failed'}")
record(11, f"Create VLAN {TEST_VLAN_ID} name '{TEST_VLAN_NAME}'", passed)

# -------------------------------------------------------
# STEP 12 — Verify hostname and VLAN in show running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 12: Verify hostname and VLAN in show running-config")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

hostname_ok = f"hostname {TEST_HOSTNAME}" in output
vlan_ok     = f"vlan {TEST_VLAN_ID}"      in output

print(f"  hostname {TEST_HOSTNAME:<20} : {'✅ found' if hostname_ok else '❌ NOT found'}")
print(f"  vlan {TEST_VLAN_ID:<24} : {'✅ found' if vlan_ok else '❌ NOT found'}")

passed = hostname_ok and vlan_ok
print(f"{'✅' if passed else '❌'} STEP 12 {'PASSED' if passed else 'FAILED'} — configurations verified in running-config")
record(12, "Verify hostname + VLAN in show running-config", passed,
       "" if passed else
       f"{'hostname missing ' if not hostname_ok else ''}{'vlan missing' if not vlan_ok else ''}")

# -------------------------------------------------------
# STEP 13 — Verify VLAN in show vlan brief
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 13: Verify VLAN {TEST_VLAN_ID} in show vlan brief")
print("Command : show vlan brief")
print("=================================")

output = send_command(shell, "show vlan brief")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = TEST_VLAN_ID in output
print(f"{'✅' if passed else '❌'} STEP 13 {'PASSED' if passed else 'FAILED'} — VLAN {TEST_VLAN_ID} {'found' if passed else 'NOT found'} in show vlan brief")
record(13, f"Verify VLAN {TEST_VLAN_ID} in show vlan brief", passed)

# -------------------------------------------------------
# STEP 14 — Cleanup: remove test VLAN and restore hostname
# -------------------------------------------------------
print("\n=================================")
print("STEP 14: Cleanup — remove test VLAN and restore hostname")
print("=================================")

send_command(shell, "configure terminal")
out_no_vlan = send_command(shell, f"no vlan {TEST_VLAN_ID}")
print(f"Command : no vlan {TEST_VLAN_ID}")
print("\n--- SWITCH OUTPUT ---")
print(out_no_vlan.strip() if out_no_vlan.strip() else "(no output)")
print("---------------------")

out_hostname = send_command(shell, "hostname Switch")
print("Command : hostname Switch")
print("\n--- SWITCH OUTPUT ---")
print(out_hostname.strip() if out_hostname.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = (
    "error" not in out_no_vlan.lower() and "invalid" not in out_no_vlan.lower() and
    "error" not in out_hostname.lower() and "invalid" not in out_hostname.lower()
)
print(f"{'✅' if passed else '❌'} STEP 14 {'PASSED' if passed else 'FAILED'} — test VLAN removed, hostname restored")
record(14, "Cleanup — remove test VLAN, restore hostname", passed)

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
