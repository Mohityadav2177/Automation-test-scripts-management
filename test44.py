import paramiko
import sys
import time
import re
import random
import string

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 snmp_v3_aes_test.py <switch_ip> <user> <pass>")
    sys.exit(1)

SWITCH_IP = sys.argv[1]
USER      = sys.argv[2]
PASS      = sys.argv[3]

print("="*70)
print("TEST CASE 44 : SNMP V3 USER WITH AES VALIDATION")
print("="*70)

# -------------------------------------------------------
# GLOBAL RESULT TRACKER
# -------------------------------------------------------
results = []

def mark_result(step, status):
    results.append((step, status))
    print(f"{step} : {'✅ PASS' if status else '❌ FAIL'}")

# -------------------------------------------------------
# SSH CONNECT
# -------------------------------------------------------
def connect(ip, user, pwd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, username=user, password=pwd)
    sh = c.invoke_shell()
    time.sleep(2)
    sh.recv(65535)
    return c, sh

# -------------------------------------------------------
# SEND COMMAND (WITH VALIDATION)
# -------------------------------------------------------
def send(sh, cmd, wait=1):
    print(f"\n>>> COMMAND: {cmd}")
    sh.send(cmd + "\n")
    time.sleep(wait)

    out = ""
    while sh.recv_ready():
        out += sh.recv(65535).decode(errors="ignore")

    print("--- OUTPUT ---")
    print(out.strip())
    print("--------------")

    # ❌ Detect CLI error
    if "Invalid" in out or "Error" in out:
        return out, False

    return out, True

# -------------------------------------------------------
# RANDOM USER GENERATOR
# -------------------------------------------------------
def random_user():
    return "hfcl_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))

# -------------------------------------------------------
# CLEANUP FUNCTION
# -------------------------------------------------------
def cleanup(sh, username, engine_id):

    print("\n[CLEANUP] Removing SNMP config")

    send(sh, "configure terminal")
    send(sh, f"no snmp-server user {username} engine-id {engine_id}")
    send(sh, "end")

# -------------------------------------------------------
# CONNECT
# -------------------------------------------------------
sw, sh = connect(SWITCH_IP, USER, PASS)

# Disable pagination
send(sh, "terminal length 0")

print(f"✅ Connected to {SWITCH_IP}")

# -------------------------------------------------------
# STEP 1: FETCH ENGINE ID
# -------------------------------------------------------
out, ok = send(sh, "show snmp")

engine = re.search(r"Engine ID\s*:\s*(\S+)", out)
if engine:
    ENGINE_ID = engine.group(1)
    mark_result("Fetch Engine ID", True)
else:
    mark_result("Fetch Engine ID", False)
    print("❌ Engine ID not found. Exiting...")
    sys.exit(1)

print(f"Engine ID: {ENGINE_ID}")

# -------------------------------------------------------
# STEP 2: CREATE RANDOM USER WITH AES
# -------------------------------------------------------
USERNAME = random_user()
print(f"\nGenerated Username: {USERNAME}")

send(sh, "configure terminal")

cmd1 = f"snmp-server user {USERNAME} engine-id {ENGINE_ID} sha hfcl@12345 priv aes hfcl@123456789"
_, ok1 = send(sh, cmd1)

cmd2 = f"snmp-server security-to-group model v3 name {USERNAME} group default_rw_group"
_, ok2 = send(sh, cmd2)

cmd3 = "snmp-server access default_rw_group model v3 level priv read default_view write default_view"
_, ok3 = send(sh, cmd3)

send(sh, "end")

mark_result("SNMP User Config", ok1 and ok2 and ok3)

# -------------------------------------------------------
# STEP 3: VERIFY USER
# -------------------------------------------------------
out1, ok4 = send(sh, "show snmp")
out2, ok5 = send(sh, "show snmp user")

# Check username presence
verify = USERNAME in out1 and USERNAME in out2

mark_result("SNMP User Verification", verify and ok4 and ok5)

# -------------------------------------------------------
# FINAL CLEANUP
# -------------------------------------------------------
cleanup(sh, USERNAME, ENGINE_ID)

# -------------------------------------------------------
# SUMMARY
# -------------------------------------------------------
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

final = True
for step, status in results:
    print(f"{step:30} : {'PASS' if status else 'FAIL'}")
    if not status:
        final = False

print("="*70)
print("FINAL RESULT :", "✅ PASS" if final else "❌ FAIL")
print("="*70)

sw.close()
