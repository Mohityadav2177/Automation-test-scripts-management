import paramiko
import sys
import time
import re

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 5:
    print("Usage: python3 demo33.py <switch_ip> <user> <pass> <server_pass>")
    sys.exit(1)

SWITCH_IP = sys.argv[1]
USER      = sys.argv[2]
PASS      = sys.argv[3]
SRV_PASS  = sys.argv[4]

SERVER_IP = "192.168.180.69"
SERVER_IF = "ens160"

TEST_IP_SWITCH = "192.168.100.1"
TEST_IP_SERVER = "192.168.100.10"

INTERFACE_VLAN = "1"

print("="*70)
print("TEST CASE : GARP VALIDATION USING SERVER TRIGGER")
print("="*70)

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
# SERVER COMMAND
# -------------------------------------------------------
def run_srv(cmd):
    print(f"\n[SERVER] {cmd}")
    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)
    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    out = stdout.read().decode()
    err = stderr.read().decode()

    print(out.strip())
    if err:
        print("ERR:", err.strip())

    return out

# -------------------------------------------------------
# TCPDUMP CAPTURE
# -------------------------------------------------------
def capture_garp(duration=10):

    cmd = f"sudo -S timeout {duration} tcpdump -i {SERVER_IF} arp -nn -l"

    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)
    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    output = stdout.read().decode(errors="ignore")

    print("\n[TCPDUMP OUTPUT]")
    print(output)

    return output

# -------------------------------------------------------
# CHECK GARP
# -------------------------------------------------------
def check_garp(output, ip):
    count = 0
    for line in output.split("\n"):
        if f"who-has {ip}" in line and f"tell {ip}" in line:
            count += 1
    return count

# -------------------------------------------------------
# CONNECT
# -------------------------------------------------------
sw, sh = connect(SWITCH_IP, USER, PASS)
send(sh, "terminal length 0")

srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect(SERVER_IP, username="hfcl", password=SRV_PASS)

print(f"✅ Connected Switch {SWITCH_IP}")
print(f"✅ Connected Server {SERVER_IP}")

# -------------------------------------------------------
# STEP 1: SWITCH CONFIG
# -------------------------------------------------------
print("\nSTEP 1: SWITCH CONFIG")

send(sh, "configure terminal")
send(sh, f"interface vlan {INTERFACE_VLAN}")
send(sh, f"ip address {TEST_IP_SWITCH} 255.255.255.0 secondary")
send(sh, "end")

# -------------------------------------------------------
# STEP 2: SERVER CONFIG
# -------------------------------------------------------
print("\nSTEP 2: SERVER CONFIG")

run_srv(f"sudo ip addr del {TEST_IP_SERVER}/24 dev {SERVER_IF} || true")
run_srv(f"sudo ip addr add {TEST_IP_SERVER}/24 dev {SERVER_IF}")

run_srv(f"sudo ip a | grep {TEST_IP_SERVER}")

# -------------------------------------------------------
# STEP 3: EXECUTION
# -------------------------------------------------------
print("\nSTEP 3: EXECUTION")

print("\nStarting tcpdump capture...")

# Run capture in parallel (background via timeout)
capture_cmd = f"sudo -S timeout 10 tcpdump -i {SERVER_IF} arp -nn -l"
stdin, stdout, stderr = srv.exec_command(capture_cmd, get_pty=True)
stdin.write(SRV_PASS + "\n")
stdin.flush()

time.sleep(2)

print("\nTriggering GARP from server...")
run_srv(f"arping -U {TEST_IP_SERVER} -I {SERVER_IF} -c 3")

output = stdout.read().decode(errors="ignore")

print("\n[TCPDUMP OUTPUT]")
print(output)

# -------------------------------------------------------
# VALIDATION
# -------------------------------------------------------
garp_count = check_garp(output, TEST_IP_SERVER)

print(f"\nGARP Packets Found: {garp_count}")

# -------------------------------------------------------
# STEP 4: CLEANUP
# -------------------------------------------------------
print("\nSTEP 4: CLEANUP")

run_srv(f"sudo ip addr del {TEST_IP_SERVER}/24 dev {SERVER_IF} || true")

send(sh, "configure terminal")
send(sh, f"interface vlan {INTERFACE_VLAN}")
send(sh, f"no ip address {TEST_IP_SWITCH} 255.255.255.0 secondary")
send(sh, "end")

# -------------------------------------------------------
# FINAL RESULT
# -------------------------------------------------------
print("\n" + "="*70)

if garp_count > 0:
    print("FINAL RESULT : ✅ PASS (GARP Detected)")
else:
    print("FINAL RESULT : ❌ FAIL (GARP Not Detected)")

print("="*70)

sw.close()
srv.close()
