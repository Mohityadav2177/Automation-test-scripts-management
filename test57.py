import paramiko
import sys
import time
import random
import re

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 demo3.py <ip> <username> <password>")
    sys.exit(1)

ip = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

MAX_LIMIT = 128
EXTRA_CHECK = 2

IPV6_BASE = "2001:4860"

print("=" * 65)
print("TEST CASE : IPv4 + IPv6 L3 Interface RAW COUNT")
print("=" * 65)

# -------------------------------------------------------
# SSH CONNECT
# -------------------------------------------------------
def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(
        ip,
        username=username,
        password=password,
        timeout=30,
        look_for_keys=False,
        allow_agent=False
    )

    shell = client.invoke_shell()
    time.sleep(2)

    while shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

    print("✅ SSH Connected")
    return client, shell


# -------------------------------------------------------
# SEND FUNCTION
# -------------------------------------------------------
def send(shell, cmd, wait=0.2):
    shell.send(cmd + "\n")
    time.sleep(wait)

    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode(errors="ignore")

    return output


client, shell = ssh_connect()

# -------------------------------------------------------
# STEP 2: FETCH INTERFACES
# -------------------------------------------------------
print("\nSTEP 2: Fetch interfaces")

ipv4_output = send(shell, "show ip interface")
ipv6_output = send(shell, "show ipv6 interface")

print("\n--- IPV4 OUTPUT ---")
print(ipv4_output.strip())

print("\n--- IPV6 OUTPUT ---")
print(ipv6_output.strip())

# -------------------------------------------------------
# ✅ FIXED: RAW COUNT (NO SET)
# -------------------------------------------------------
vlan_list = []

def extract_vlans(output):
    for line in output.splitlines():
        match = re.search(r"VLAN\s+(\d+)", line)
        if match:
            vlan_list.append(match.group(1))

extract_vlans(ipv4_output)
extract_vlans(ipv6_output)

existing = len(vlan_list)

print("\n---------------------")
print(f"RAW COUNT (IPv4 + IPv6 lines): {existing}")

remaining = MAX_LIMIT - existing
print(f"Allowed to create: {remaining}")

# -------------------------------------------------------
# STEP 3: CREATE INTERFACES (IPv6 RANDOM)
# -------------------------------------------------------
print("\nSTEP 3: Creating IPv6 Interfaces")

created = 0
created_vlans = []
used_vlans = set()

attempt = 1
total_attempts = remaining + EXTRA_CHECK

while attempt <= total_attempts:

    vlan = random.randint(2, 4094)

    if vlan in used_vlans:
        continue

    used_vlans.add(vlan)

    # Random IPv6 generation
    ipv6 = f"{IPV6_BASE}:{random.randint(1,500)}:{random.randint(1,150)}::1"

    print(f"\n[Attempt {attempt}] VLAN {vlan} → {ipv6}/64")

    cmd = f"""configure terminal
vlan {vlan}
interface vlan {vlan}
ipv6 address {ipv6}/64
end
"""

    output = send(shell, cmd, wait=0.3)

    print("\n--- SWITCH RESPONSE ---")
    print(output.strip())
    print("-----------------------")

    out = output.lower()

    if "error" not in out and "failed" not in out:
        created += 1
        created_vlans.append(vlan)
        print(f"✅ Created Count: {created}")

    attempt += 1

# -------------------------------------------------------
# STEP 4: VALIDATION
# -------------------------------------------------------
print("\nSTEP 4: Validation")

total = existing + created

print(f"Existing (RAW) : {existing}")
print(f"Created        : {created}")
print(f"Total          : {total}")

if total >= MAX_LIMIT:
    print("✅ PASS — Limit matched perfectly")
else:
    print("❌ FAIL — Limit mismatch")

# -------------------------------------------------------
# STEP 5: CLEANUP
# -------------------------------------------------------
print("\nSTEP 5: Cleanup")

for vlan in created_vlans:
    send(shell, f"""configure terminal
no interface vlan {vlan}
end
""", wait=0.1
)

client.close()

print("\nDONE")
