import paramiko
import sys
import time
import random
import re

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 test58.py <ip> <username> <password>")
    sys.exit(1)

ip = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

MAX_LIMIT = 128

print("=" * 65)
print("TEST CASE : 58 — Max L3 Interfaces (IPv4 + IPv6 MIXED)")
print("=" * 65)

# -------------------------------------------------------
# SSH CONNECT (FIXED SOCKET ISSUE)
# -------------------------------------------------------
def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(
        ip,
        username=username,
        password=password,
        timeout=20,
        look_for_keys=False,
        allow_agent=False
    )

    shell = client.invoke_shell()
    time.sleep(2)

    # flush buffer
    if shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

    print("✅ SSH Connected")
    return client, shell


# -------------------------------------------------------
# SEND FUNCTION
# -------------------------------------------------------
def send(shell, cmd, wait=0.7):
    try:
        shell.send(cmd + "\n")
        time.sleep(wait)

        output = ""
        while shell.recv_ready():
            output += shell.recv(65535).decode(errors="ignore")

        return output
    except Exception as e:
        print(f"❌ SEND ERROR: {e}")
        return ""


client, shell = ssh_connect()

# -------------------------------------------------------
# STEP 1: FETCH EXISTING COUNT
# -------------------------------------------------------
print("\nSTEP 1: Fetch existing interfaces")

output = send(shell, "show ip interface")
output += send(shell, "show ipv6 interface")

vlan_list = []

for line in output.splitlines():
    match = re.search(r"VLAN\s+(\d+)", line)
    if match:
        vlan_list.append(match.group(1))

existing = len(vlan_list)

print(f"Existing interfaces: {existing}")

remaining = MAX_LIMIT - existing

if remaining <= 0:
    print("⚠️ Already reached max limit. Exiting.")
    client.close()
    sys.exit()

print(f"Can create up to: {remaining}")

# -------------------------------------------------------
# STEP 2: CREATE RANDOM MIXED IPV4 + IPV6
# -------------------------------------------------------
print("\nSTEP 2: Creating Mixed Interfaces")

created = 0
used_vlans = set()
created_vlans = []

while created < remaining:

    vlan = random.randint(2, 4094)

    if vlan in used_vlans:
        continue

    used_vlans.add(vlan)

    # Random IPv4
    ipv4 = f"10.{random.randint(0,255)}.{random.randint(0,255)}.1"

    # Random IPv6 (UNIQUE)
    ipv6 = f"2001:4860:{random.randint(1,500)}:{random.randint(1,150)}::1"

    print(f"\n[VLAN {vlan}] IPv4 → {ipv4} | IPv6 → {ipv6}/64")

    cmd = f"""configure terminal
vlan {vlan}
interface vlan {vlan}
ip address {ipv4} 255.255.255.0
ipv6 address {ipv6}/64
end
"""

    output = send(shell, cmd, wait=1)

    print("\n--- SWITCH RESPONSE ---")
    print(output.strip())
    print("-----------------------")

    out = output.lower()

    # STOP condition (IMPORTANT)
    if "number of allowed ip interfaces reached" in out:
        print("🛑 LIMIT REACHED FROM SWITCH")
        break

    # avoid duplicate / failed configs
    if ("error" not in out and 
        "failed" not in out and 
        "duplicate" not in out):

        created += 1
        created_vlans.append(vlan)
        print(f"✅ Created Count: {created}")

# -------------------------------------------------------
# STEP 3: VALIDATION
# -------------------------------------------------------
print("\nSTEP 3: Validation")

total = existing + created

print(f"Existing : {existing}")
print(f"Created  : {created}")
print(f"Total    : {total}")

if total >= MAX_LIMIT:
    print("✅ PASS — Limit reached correctly")
else:
    print("❌ FAIL — Limit not reached")

# -------------------------------------------------------
# STEP 4: CLEANUP
# -------------------------------------------------------
print("\nSTEP 4: Cleanup")

for vlan in created_vlans:
    send(shell, f"""configure terminal
no interface vlan {vlan}
no vlan {vlan}
end
""", wait=0.5)

client.close()

print("\n✅ TEST COMPLETED")
