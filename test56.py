import paramiko
import sys
import time
import random
import re

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 tc56_l3_limit.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

MAX_LIMIT   = 128
EXTRA_CHECK = 2

print("=" * 70)
print("TEST CASE : 56 — Max L3 Interfaces")
print("OBJECTIVE : Validate max 128 VLAN L3 interfaces supported")
print("=" * 70)

# -------------------------------------------------------
# SSH CONNECT
# -------------------------------------------------------
def ssh_connect():
    print(f"\nConnecting to {ip} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(ip, username=username, password=password,
                   timeout=30, look_for_keys=False, allow_agent=False)

    shell = client.invoke_shell()
    time.sleep(2)

    while shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

    print("✅ SSH Connected")
    return client, shell

# -------------------------------------------------------
# SEND FUNCTION (ROBUST)
# -------------------------------------------------------
def send(shell, cmd, wait=2):
    while shell.recv_ready():
        shell.recv(65535)

    shell.send(cmd + "\n")
    time.sleep(wait)

    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode(errors="ignore")

    return output

# -------------------------------------------------------
# STEP 1: SSH
# -------------------------------------------------------
client, shell = ssh_connect()

# -------------------------------------------------------
# STEP 2: FETCH EXISTING INTERFACES
# -------------------------------------------------------
print("\nSTEP 2: Fetch existing interfaces")

output_v4 = send(shell, "show ip interface")
time.sleep(1)
output_v6 = send(shell, "show ipv6 interface")

print("\n--- IPV4 OUTPUT ---")
print(output_v4.strip())

print("\n--- IPV6 OUTPUT ---")
print(output_v6.strip())

combined_output = output_v4 + "\n" + output_v6

# Extract VLANs
vlans = set()

for line in combined_output.splitlines():
    match = re.search(r"(?i)vlan\s*(\d+)", line)
    if match:
        vlans.add(match.group(1))

# ✅ Save initial VLANs (IMPORTANT)
initial_vlans = set(vlans)

existing = len(vlans)

print("\n---------------------")
print(f"Detected Existing VLAN L3 Interfaces: {existing}")

expected_new = MAX_LIMIT - existing
print(f"Interfaces allowed to create: {expected_new}")

# -------------------------------------------------------
# STEP 3: CREATE INTERFACES
# -------------------------------------------------------
print("\nSTEP 3: Creating Interfaces")

created = 0
created_vlans = []
used_vlans = set()

limit_detected = False
limit_attempt = None

attempt = 1
total_attempts = expected_new + EXTRA_CHECK

while attempt <= total_attempts:

    vlan = random.randint(2, 4094)
    if vlan in used_vlans:
        continue
    used_vlans.add(vlan)

    ip_addr = f"10.{random.randint(0,255)}.{random.randint(0,255)}.1"

    print(f"\n[Attempt {attempt}] VLAN {vlan} → {ip_addr}")

    shell.send(f"""configure terminal
vlan {vlan}
interface vlan {vlan}
ip address {ip_addr} 255.255.255.0
end
""")

    time.sleep(0.2)

    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode(errors="ignore")

    print("\n--- SWITCH RESPONSE ---")
    print(output.strip())
    print("-----------------------")

    out = output.lower()

    # LIMIT DETECT
    if ("number of allowed ip interfaces reached" in out or
        "no such ip interface" in out):

        print(f"⚠️ LIMIT DETECTED at attempt {attempt}")

        if not limit_detected:
            limit_detected = True
            limit_attempt = attempt

        attempt += 1
        continue

    # IP conflict
    if "conflict" in out:
        print("⚠️ IP Conflict → retry")
        continue

    # SUCCESS
    if ("failed" not in out and "error" not in out):
        created += 1
        created_vlans.append(vlan)
        print(f"✅ Created Count: {created}")
    else:
        print("⚠️ Not counted due to failure")

    attempt += 1

# -------------------------------------------------------
# STEP 4: VALIDATION
# -------------------------------------------------------
print("\nSTEP 4: Validation")

total = existing + created

print(f"Existing : {existing}")
print(f"Created  : {created}")
print(f"Total    : {total}")
print(f"Limit detected at attempt: {limit_attempt}")

if total >= MAX_LIMIT:
    print("✅ PASS — Max L3 interface limit validated correctly")
    result = "PASS"
else:
    print("❌ FAIL — Limit not matching expected 128")
    result = "FAIL"

# -------------------------------------------------------
# STEP 5: CLEANUP
# -------------------------------------------------------
print("\nSTEP 5: Cleanup")

for vlan in created_vlans:
    print(f"Removing VLAN {vlan}")

    shell.send(f"""configure terminal
no interface vlan {vlan}
end
""")

    time.sleep(0.2)

    while shell.recv_ready():
        shell.recv(65535)

# -------------------------------------------------------
# VERIFY CLEANUP (FIXED LOGIC)
# -------------------------------------------------------
print("\nVerifying cleanup...")
time.sleep(2)

output_v4 = send(shell, "show ip interface")
output_v6 = send(shell, "show ipv6 interface")

final_output = output_v4 + "\n" + output_v6

print("\n--- SWITCH OUTPUT ---")
print(final_output.strip())
print("---------------------")

# Extract final VLANs
final_vlans = set()

for line in final_output.splitlines():
    match = re.search(r"(?i)vlan\s*(\d+)", line)
    if match:
        final_vlans.add(match.group(1))

# Check only created VLANs
leftover = []

for vlan in created_vlans:
    if str(vlan) in final_vlans:
        leftover.append(vlan)

if not leftover:
    cleanup_ok = True
else:
    cleanup_ok = False
    print(f"❌ VLANs not removed: {leftover}")

print("Cleanup Status:", "✅ SUCCESS" if cleanup_ok else "❌ FAILED")

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()

# -------------------------------------------------------
# FINAL RESULT
# -------------------------------------------------------
print("\n" + "=" * 70)
print(f"FINAL RESULT : {'✅ PASS' if result=='PASS' else '❌ FAIL'}")
print("=" * 70)
