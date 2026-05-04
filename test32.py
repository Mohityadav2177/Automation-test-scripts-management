import paramiko
import socket
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_032.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

# -------------------------------------------------------
# Test configuration
# -------------------------------------------------------
REACHABLE_IP   = "192.168.180.12"
UNREACHABLE_IP = "192.18.10.12"

print("=" * 60)
print("TEST CASE : HFCL-SW-032")
print("TEST NAME : Management")
print("OBJECTIVE : Verify traceroute functionality")
print("=" * 60)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []

def record(step_num, description, passed, note=""):
    step_results.append((step_num, description, "PASS" if passed else "FAIL", note))

def print_final_summary():
    print("\n" + "=" * 65)
    print("FINAL STEP SUMMARY")
    print("=" * 65)
    all_passed = True
    for sn, desc, status, note in step_results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} STEP {sn}: {desc} -> {status}")
        if note:
            print(f"   Note: {note}")
        if status == "FAIL":
            all_passed = False

    print("\nOVERALL RESULT :", "✅ PASS" if all_passed else "❌ FAIL")
    print("=" * 65)

# -------------------------------------------------------
# SSH
# -------------------------------------------------------
def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(ip, username=username, password=password,
                   look_for_keys=False, allow_agent=False)

    shell = client.invoke_shell()
    time.sleep(2)
    shell.send("terminal length 0\n")
    time.sleep(1)

    return client, shell

def send_command(shell, cmd, timeout=40):
    shell.send(cmd + "\n")
    output = ""
    end_time = time.time() + timeout

    while time.time() < end_time:
        if shell.recv_ready():
            data = shell.recv(65535).decode()
            output += data

            if "-- more --" in output.lower():
                shell.send("g")

        time.sleep(0.3)

    return output

# ======================================================
# TEST START
# ======================================================

client, shell = ssh_connect()
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — Reachable
# -------------------------------------------------------
output = send_command(shell, f"traceroute ip {REACHABLE_IP}")

print("\n--- STEP 2 OUTPUT ---\n", output)

has_hops = any(str(i) in output for i in range(1, 6))
has_latency = "ms" in output.lower()

passed = has_hops and has_latency

record(2, "Traceroute reachable destination", passed,
       "" if passed else "Hop/latency missing")

# -------------------------------------------------------
# STEP 3 — Unreachable (FIXED LOGIC)
# -------------------------------------------------------
output = send_command(shell, f"traceroute ip {UNREACHABLE_IP}")

print("\n--- STEP 3 OUTPUT ---\n", output)

output_lower = output.lower()

# ✅ Improved validation
failure_patterns = ["* * *", "timeout", "unreachable", "no route"]

has_failure_pattern = any(p in output_lower for p in failure_patterns)

# Also check if NO successful completion (no latency lines)
has_success_latency = "ms" in output_lower and not "* * *" in output

# Final decision
passed = has_failure_pattern or not has_success_latency

record(3, "Traceroute unreachable destination", passed,
       "" if passed else "Device did not indicate failure properly")

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()

print_final_summary()
