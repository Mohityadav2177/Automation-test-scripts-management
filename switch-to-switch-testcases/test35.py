import paramiko
import sys
import time
import re

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 tc35_lldp_stats.py <dut_ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

INTERFACE = "gig 1/24"
FULL_INTF = "GigabitEthernet 1/24"

print("=" * 70)
print("TEST CASE : 35 — LLDP Statistics")
print("OBJECTIVE : Validate LLDP counters increment, reset, stop & resume")
print("=" * 70)

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

    while shell.recv_ready():
        shell.recv(65535)

    shell.send("terminal length 0\n")
    time.sleep(1)

    print("✅ Connected")
    return client, shell

# -------------------------------------------------------
# SEND FUNCTION
# -------------------------------------------------------
def send(shell, cmd, wait=2):
    while shell.recv_ready():
        shell.recv(65535)

    print(f"\n>>> COMMAND: {cmd}")
    shell.send(cmd + "\n")
    time.sleep(wait)

    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode(errors="ignore")

    print("--- OUTPUT ---")
    print(output.strip())
    print("--------------")

    return output

# -------------------------------------------------------
# FIXED PARSER (NO BUG)
# -------------------------------------------------------
def get_intf_stats(output):
    for line in output.splitlines():

        line = line.strip()

        # Skip unwanted lines
        if line.startswith("show"):
            continue
        if line.startswith("Interface") or line.startswith("---------"):
            continue

        # Match correct interface row
        if line.startswith("GigabitEthernet"):
            parts = line.split()

            if len(parts) >= 10 and parts[0] == "GigabitEthernet" and parts[1] == "1/24":
                counters = parts[-8:]
                try:
                    return list(map(int, counters))
                except:
                    return []

    return []

# -------------------------------------------------------
# WAIT FOR COUNTER INCREMENT
# -------------------------------------------------------
def wait_for_increment(shell, cmd, retries=5, delay=10):
    prev = get_intf_stats(send(shell, cmd))

    if not prev:
        print("⚠️ Could not read initial counters")
        return False

    for i in range(retries):
        time.sleep(delay)
        new = get_intf_stats(send(shell, cmd))

        if new and (new[0] > prev[0] or new[1] > prev[1]):
            return True

    return False

# -------------------------------------------------------
# STEP 1: CONNECT
# -------------------------------------------------------
client, shell = ssh_connect()

# -------------------------------------------------------
# STEP 2: CHECK NEIGHBOR
# -------------------------------------------------------
print("\nSTEP 2: Check LLDP Neighbor")

lldp = send(shell, "show lldp neighbors")

if not lldp.strip():
    print("❌ FAIL — No LLDP neighbor")
    sys.exit(1)

print("✅ LLDP neighbor present")

# -------------------------------------------------------
# STEP 3: INCREMENT CHECK
# -------------------------------------------------------
print("\nSTEP 3: Verify counters increment")

step3_result = wait_for_increment(
    shell,
    f"show lldp statistics interface {FULL_INTF}")
time.sleep(5)

print("✅ PASS — Counters increasing" if step3_result else "❌ FAIL — No increment")

# -------------------------------------------------------
# STEP 4: CLEAR STATS
# -------------------------------------------------------
print("\nSTEP 4: Clear LLDP statistics")

send(shell, "clear lldp statistics")
time.sleep(0.5)

after_clear = get_intf_stats(send(shell, f"show lldp statistics interface {FULL_INTF}"))

print("After Clear:", after_clear)

if after_clear and all(v == 0 for v in after_clear):
    print("✅ PASS — Counters reset")
    step4_result = True
else:
    print("❌ FAIL — Counters not reset")
    step4_result = False

# -------------------------------------------------------
# STEP 5: DISABLE LLDP
# -------------------------------------------------------
print("\nSTEP 5: Disable LLDP")

send(shell, "configure terminal")
send(shell, f"interface {INTERFACE}")
send(shell, "no lldp transmit")
send(shell, "no lldp receive")
send(shell, "end")

time.sleep(5)

before = get_intf_stats(send(shell, f"show lldp statistics interface {FULL_INTF}"))
time.sleep(5)
after = get_intf_stats(send(shell, f"show lldp statistics interface {FULL_INTF}"))

if before == after:
    print("✅ PASS — Counters stopped")
    step5_result = True
else:
    print("❌ FAIL — Counters still increasing")
    step5_result = False

# -------------------------------------------------------
# STEP 6: ENABLE LLDP
# -------------------------------------------------------
print("\nSTEP 6: Re-enable LLDP")

send(shell, "configure terminal")
send(shell, f"interface {INTERFACE}")
send(shell, "lldp transmit")
send(shell, "lldp receive")
send(shell, "end")

step6_result = wait_for_increment(
    shell,
    f"show lldp statistics interface {FULL_INTF}"
)

print("✅ PASS — Counters resumed" if step6_result else "❌ FAIL — No increment")

# -------------------------------------------------------
# FINAL RESULT
# -------------------------------------------------------
print("\n" + "=" * 70)

if step3_result and step4_result and step5_result and step6_result:
    print("FINAL RESULT : ✅ PASS")
else:
    print("FINAL RESULT : ❌ FAIL")

print("=" * 70)

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()
