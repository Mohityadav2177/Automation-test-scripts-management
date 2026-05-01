import paramiko
import sys
import time

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 5:
    print("Usage: python3 syslog_test.py <switch_ip> <user> <pass> <server_pass>")
    sys.exit(1)

SWITCH_IP = sys.argv[1]
USER      = sys.argv[2]
PASS      = sys.argv[3]
SRV_PASS  = sys.argv[4]

SERVER_IP = "192.168.180.69"
INTERFACE = "GigabitEthernet 1/23"

results = []

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
    return out

# -------------------------------------------------------
# RESULT MARKING
# -------------------------------------------------------
def mark(step, status):
    results.append((step, status))
    print(f"{step} : {'✅ PASS' if status else '❌ FAIL'}")

# -------------------------------------------------------
# CONNECT SWITCH + SERVER
# -------------------------------------------------------
sw, sh = connect(SWITCH_IP, USER, PASS)
send(sh, "terminal length 0")

srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect(SERVER_IP, username="hfcl", password=SRV_PASS)

print(f"✅ Connected Switch {SWITCH_IP}")
print(f"✅ Connected Server {SERVER_IP}")

# -------------------------------------------------------
# RUN SERVER COMMAND
# -------------------------------------------------------
def run_srv(cmd):
    stdin, stdout, stderr = srv.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if err:
        print("ERR:", err)
    return out

# -------------------------------------------------------
# SYSLOG CAPTURE (REAL-TIME)
# -------------------------------------------------------
def capture_syslog(duration=8):

    print(f"\n[SERVER] Capturing syslog for {duration} sec...")

    cmd = f"sudo -S timeout {duration} tail -f /var/log/syslog"

    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)
    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    output = stdout.read().decode(errors="ignore")

    print("\n[SYSLOG OUTPUT]")
    print(output)

    return output

# -------------------------------------------------------
# STEP 1: CONFIGURE SYSLOG
# -------------------------------------------------------
print("\nSTEP 1: CONFIGURE SYSLOG")

send(sh, "configure terminal")
send(sh, "logging on")
send(sh, f"logging host id 1 {SERVER_IP}")
send(sh, "logging level informational")
send(sh, "end")

mark("Syslog Config", True)

# -------------------------------------------------------
# STEP 2: SHUTDOWN TEST
# -------------------------------------------------------
print("\nSTEP 2: SHUTDOWN TEST")

# Start capture BEFORE event
logs = capture_syslog(duration=8)

send(sh, "configure terminal")
send(sh, f"interface {INTERFACE}")
send(sh, "shutdown")
send(sh, "end")

time.sleep(2)

# Start capture BEFORE event
logs = capture_syslog(duration=10)



shutdown_ok = (
    "down" in logs.lower() and INTERFACE.lower() in logs.lower()
)

mark("Remote Syslog - Shutdown", shutdown_ok)

# -------------------------------------------------------
# STEP 3: NO SHUT TEST
# -------------------------------------------------------
print("\nSTEP 3: NO SHUT TEST")

#logs = capture_syslog(duration=8)

send(sh, "configure terminal")
send(sh, f"interface {INTERFACE}")
send(sh, "no shutdown")
send(sh, "end")

time.sleep(2)

# Start capture AFTER event
logs = capture_syslog(duration=10)



noshut_ok = (
    "up" in logs.lower() and INTERFACE.lower() in logs.lower()
)

mark("Remote Syslog - No Shut", noshut_ok)

# -------------------------------------------------------
# STEP 4: REMOVE SYSLOG SERVER
# -------------------------------------------------------
print("\nSTEP 4: REMOVE SYSLOG CONFIG")

send(sh, "configure terminal")
send(sh, f"no logging host id 1 {SERVER_IP}")
send(sh, "end")

mark("Syslog Remove", True)

# -------------------------------------------------------
# FINAL RESULT
# -------------------------------------------------------
print("\n" + "="*60)
print("FINAL RESULT SUMMARY")
print("="*60)

for step, status in results:
    print(f"{step:<35} : {'PASS' if status else 'FAIL'}")

if all(status for _, status in results):
    print("\nFINAL RESULT : ✅ PASS")
else:
    print("\nFINAL RESULT : ❌ FAIL")

print("="*60)

sw.close()
srv.close()

