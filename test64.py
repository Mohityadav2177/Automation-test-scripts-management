import paramiko
import sys
import time
import re

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 tc64_port_desc.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

PORTS = ["GigabitEthernet 1/1", "GigabitEthernet 1/8", "GigabitEthernet 1/24"]
DESCRIPTION = "port-towards-cctv"

print("=" * 65)
print("TEST CASE : 64 — Port Description")
print("TEST NAME : Verify Port Description Setting")
print("OBJECTIVE : Verify description is configured and displayed correctly")
print("=" * 65)
print(f"Target   : {ip}:22")
print(f"Username : {username}")
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
    print("TEST CASE  : 64 — Port Description")
    print("FINAL STEP SUMMARY")
    print("=" * 65)
    print(f"{'STEP':<6} {'DESCRIPTION':<50} {'RESULT'}")
    print("-" * 65)

    all_passed = True
    for sn, desc, status, note in step_results:
        icon = "✅" if status == "PASS" else ("⚠️" if status == "SKIP" else "❌")
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
        client.connect(ip, username=username, password=password,
                       timeout=30, look_for_keys=False, allow_agent=False)
    except Exception as e:
        print(f"❌ SSH failed: {e}")
        sys.exit(1)

    shell = client.invoke_shell()
    time.sleep(2)

    while shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

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
                continue

            if output.rstrip().endswith("#"):
                break
        else:
            time.sleep(0.3)

    return output

# -------------------------------------------------------
# Helper functions
# -------------------------------------------------------
def interface_exists(output):
    return not ("invalid" in output.lower() or "error" in output.lower())

def get_description(output, interface):
    short_intf = interface.replace("GigabitEthernet", "Gi")

    pattern = rf"^{short_intf}\s+(.+)$"

    for line in output.splitlines():
        match = re.match(pattern, line.strip())
        if match:
            return match.group(1).strip()

    return ""

# ======================================================
# TEST EXECUTION
# ======================================================

# STEP 1 — SSH Login
print("=================================")
print("STEP 1: SSH Login")
print("=================================")

client, shell = ssh_connect()
record(1, "SSH Login", True)

step = 2

# -------------------------------------------------------
# LOOP THROUGH PORTS
# -------------------------------------------------------
for intf in PORTS:

    print("\n=================================")
    print(f"STEP {step}: Check Interface {intf}")
    print("=================================")

    show_cmd = f"show interface {intf} description"
    output = send_command(shell, show_cmd)

    print("\n--- SWITCH OUTPUT ---")
    print(output.strip())
    print("---------------------")

    if not interface_exists(output):
        print(f"⚠️ {intf} NOT PRESENT → SKIP")
        record(step, f"{intf} not present", True, "SKIPPED")
        step += 1
        continue

    record(step, f"{intf} exists", True)
    step += 1

    # -------------------------------------------------------
    # CONFIGURE DESCRIPTION
    # -------------------------------------------------------
    print("\n=================================")
    print(f"STEP {step}: Configure Description on {intf}")
    print("=================================")

    print("\n--- CONFIGURATION SENT ---")
    print(f"""
configure terminal
interface {intf}
description {DESCRIPTION}
end
""")

    send_command(shell, "configure terminal")
    send_command(shell, f"interface {intf}")
    send_command(shell, f"description {DESCRIPTION}")
    send_command(shell, "end")

    print("✅ Configuration applied")

    record(step, f"{intf} description configured", True, DESCRIPTION)
    step += 1

    # -------------------------------------------------------
    # VERIFY
    # -------------------------------------------------------
    print("\n=================================")
    print(f"STEP {step}: Verify Description on {intf}")
    print("=================================")

    output = send_command(shell, show_cmd)

    print("\n--- SWITCH OUTPUT ---")
    print(output.strip())
    print("---------------------")

    desc = get_description(output, intf)
    passed = (desc == DESCRIPTION)

    print(f"{'✅' if passed else '❌'} Description Found: {desc if desc else 'NOT FOUND'}")

    record(step,
           f"{intf} description verification",
           passed,
           desc if desc else "Not Found")

    step += 1

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
