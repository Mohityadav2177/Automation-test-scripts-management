import paramiko
import sys
import time
import re

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_inventory_test.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

print("=" * 65)
print("TEST CASE : 63 — System Info / Inventory Information")
print("=" * 65)

# -------------------------------------------------------
# Step tracker
# -------------------------------------------------------
step_results = []

def record(step, desc, status, note=""):
    step_results.append((step, desc, "PASS" if status else "FAIL", note))

def print_summary():
    print("\n" + "=" * 65)
    print("FINAL SUMMARY")
    print("=" * 65)

    all_ok = True
    for s, d, r, n in step_results:
        icon = "✅" if r == "PASS" else "❌"
        print(f"{icon} STEP {s:<2} {d:<40} {r}")
        if n:
            print(f"     Note: {n}")
        if r == "FAIL":
            all_ok = False

    print("\nOVERALL:", "✅ PASS" if all_ok else "❌ FAIL")
    print("=" * 65)

# -------------------------------------------------------
# PROMPT DETECTION (KEY UPGRADE)
# -------------------------------------------------------
def detect_prompt(shell):
    shell.send("\n")
    time.sleep(1)

    output = ""
    if shell.recv_ready():
        output = shell.recv(65535).decode(errors="ignore")

    lines = output.strip().splitlines()

    if not lines:
        return "#"

    last_line = lines[-1]

    # Extract prompt ending with # or >
    match = re.search(r'([^\n\r]+[>#])', last_line)
    if match:
        return match.group(1).strip()

    return "#"

# -------------------------------------------------------
# SSH CONNECT
# -------------------------------------------------------
def ssh_connect():
    print(f"\nConnecting to {ip} ...")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(ip, username=username, password=password,
                   timeout=20, look_for_keys=False, allow_agent=False)

    shell = client.invoke_shell()
    time.sleep(2)

    if shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

    prompt = detect_prompt(shell)
    print(f"✅ Connected | Detected Prompt: {prompt}")

    return client, shell, prompt

# -------------------------------------------------------
# SEND COMMAND (PROMPT BASED)
# -------------------------------------------------------
def send_command(shell, cmd, prompt, timeout=30):
    shell.send(cmd + "\n")

    output = ""
    end_time = time.time() + timeout

    while time.time() < end_time:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode(errors="ignore")
            output += chunk

            # Handle pagination
            if "-- more --" in chunk.lower():
                shell.send("g")
                continue

            # Stop when prompt appears again
            if prompt in output:
                break

        else:
            time.sleep(0.3)

    return output

# -------------------------------------------------------
# PARSER
# -------------------------------------------------------
def parse_inventory(output):
    inventory = {}
    for line in output.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            inventory[key.strip().lower()] = val.strip()
    return inventory

# ======================================================
# TEST EXECUTION
# ======================================================

# STEP 1
client, shell, prompt = ssh_connect()
record(1, "SSH Login + Prompt Detection", True, prompt)

# STEP 2
print("\nSTEP 2: Running show system")
system_output = send_command(shell, "show system", prompt)

print("\n--- RAW OUTPUT ---")
print(system_output.strip())
print("------------------")

passed = "system" in system_output.lower()
record(2, "Execute show system", passed)

# STEP 3
inventory = parse_inventory(system_output)
passed = bool(inventory)
record(3, "Parse inventory", passed)

# STEP 4+ VALIDATION
fields = {
    "System Description": "system description",
    "Model Name": "model name",
    "Serial Number": "serial number",
    "Hardware Version": "hardware version",
    "MAC Address": "mac address",
    "System Uptime": "system uptime",
    "Software Version": "software version",
}

print("\nSTEP 4+: Field Validation\n")

step_num = 4
all_ok = True

for label, key in fields.items():
    value = inventory.get(key, "")

    print(f"{label:<20}: {value if value else 'NOT FOUND'}")

    ok = bool(value)
    if not ok:
        all_ok = False

    record(step_num, f"{label} validation", ok, value if value else "Missing")
    step_num += 1

# CLOSE
client.close()

# FINAL
print_summary()
