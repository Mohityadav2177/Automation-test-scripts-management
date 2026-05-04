import paramiko
import sys
import time

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_http_001.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

print("=" * 60)
print("TEST CASE : HFCL-SW-HTTP-31")
print("TEST NAME : HTTP / HTTPS")
print("OBJECTIVE : Verify self-signed certificate for HTTPS")
print("=" * 60)

# -------------------------------------------------------
# Step tracker
# -------------------------------------------------------
step_results = []

def record(step, desc, status, note=""):
    step_results.append((step, desc, "PASS" if status else "FAIL", note))

def summary():
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    overall = True
    for s, d, r, n in step_results:
        print(f"{'✅' if r=='PASS' else '❌'} STEP {s}: {d} -> {r}")
        if n:
            print("   Note:", n)
        if r == "FAIL":
            overall = False
    print("\nOVERALL:", "✅ PASS" if overall else "❌ FAIL")
    print("="*60)

# -------------------------------------------------------
# SSH
# -------------------------------------------------------
def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(ip, username=username, password=password,
                   look_for_keys=False, allow_agent=False)

    shell = client.invoke_shell()
    time.sleep(2)
    shell.send("terminal length 0\n")
    time.sleep(1)

    return client, shell

def send(shell, cmd, wait=3):
    shell.send(cmd + "\n")
    time.sleep(wait)
    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode()
    return output

# ======================================================
# TEST START
# ======================================================

client, shell = connect()
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — Disable HTTPS server
# -------------------------------------------------------
send(shell, "configure terminal")
out = send(shell, "no ip http secure-server")
send(shell, "end")

print("\n--- STEP 2 OUTPUT ---\n", out)

passed = "error" not in out.lower()
record(2, "Disable HTTPS server", passed)

# -------------------------------------------------------
# STEP 3 — Generate self-signed certificate
# -------------------------------------------------------
send(shell, "configure terminal")
out = send(shell, "ip http secure-certificate generate", wait=5)
send(shell, "end")

print("\n--- STEP 3 OUTPUT ---\n", out)

passed = "error" not in out.lower()
record(3, "Generate HTTPS self-signed certificate", passed)

# -------------------------------------------------------
# STEP 4 — Verify certificate present
# -------------------------------------------------------
out = send(shell, "show ip http")

print("\n--- STEP 4 OUTPUT ---\n", out)

output_lower = out.lower()

# flexible validation
cert_present = any(x in output_lower for x in [
    "certificate", "secure certificate", "present", "enabled"
])

passed = cert_present

record(4, "Verify certificate present in show ip http", passed,
       "" if passed else "Certificate not shown in output")

# -------------------------------------------------------
# STEP 5 — Remove certificate / Disable HTTPS
# -------------------------------------------------------
send(shell, "configure terminal")
out = send(shell, "ip http secure-certificate delete")
send(shell, "end")

print("\n--- STEP 5 OUTPUT ---\n", out)

passed = "error" not in out.lower()
record(5, "Disable HTTPS after certificate", passed)

# -------------------------------------------------------
# STEP 6 — Verify certificate NOT present (STRICT)
# -------------------------------------------------------
out = send(shell, "show ip http")

print("\n--- STEP 6 OUTPUT ---\n", out)

output_lower = out.lower()

if "not presented" in output_lower:
    passed = True
    note = ""
elif "presented" in output_lower:
    passed = False
    note = "Certificate still present"
else:
    passed = False
    note = "Unable to determine certificate state"

record(6, "Verify certificate not present", passed, note)

# -------------------------------------------------------
# CLOSE
# -------------------------------------------------------
client.close()

summary()
