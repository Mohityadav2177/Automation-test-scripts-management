import paramiko
import sys
import time
import re

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 6:
    print("Usage: python3 test41.py <switch_ip> <user> <pass> <server_user> <server_pass>")
    sys.exit(1)

SWITCH_IP = sys.argv[1]
USER      = sys.argv[2]
PASS      = sys.argv[3]
SRV_USER  = sys.argv[4]
SRV_PASS  = sys.argv[5]

SERVER_IP = "192.168.180.69"
INTERFACE = "GigabitEthernet 1/23"

print("="*70)
print("TEST CASE : 41 — SNMP (ALL VERSIONS + ALL TRAPS)")
print("="*70)

# -------------------------------------------------------
# SSH CONNECT
# -------------------------------------------------------
def connect(ip, user, pwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=user, password=pwd, timeout=30)
    shell = client.invoke_shell()
    time.sleep(2)
    shell.recv(65535)
    return client, shell

# -------------------------------------------------------
# SEND COMMAND
# -------------------------------------------------------
def send(shell, cmd, wait=2):
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
# CONNECT SWITCH
# -------------------------------------------------------
sw, sh = connect(SWITCH_IP, USER, PASS)
print(f"✅ Connected to {SWITCH_IP}")

# -------------------------------------------------------
# FETCH ENGINE ID
# -------------------------------------------------------
out = send(sh, "show snmp")

engine = re.search(r"Engine ID\s*:\s*(\S+)", out)
ENGINE_ID = engine.group(1) if engine else "80000df9030006ae9d13ce"

print(f"✅ Engine ID: {ENGINE_ID}")

# -------------------------------------------------------
# CONNECT SERVER
# -------------------------------------------------------
srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect(SERVER_IP, username=SRV_USER, password=SRV_PASS)

print(f"✅ Connected to server {SERVER_IP}")

# -------------------------------------------------------
# TCPDUMP CAPTURE FUNCTION (FIXED)
# -------------------------------------------------------
"""def capture_packets(duration=12):
    cmd = "sudo -S tcpdump -i ens160 udp port 162 -nn -l"

    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)

    # Send password to sudo
    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    count = 0
    start = time.time()

    while time.time() - start < duration:
        line = stdout.readline()

        if line:
            print("[TCPDUMP]", line.strip())

            if "Trap" in line or "SNMP" in line:
                count += 1

    return count"""



def capture_packets(duration=12):

    cmd = "sudo -S tcpdump -i ens160 udp port 162 -nn -l"

    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)

    # Send sudo password
    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    count = 0
    start = time.time()

    while time.time() - start < duration:

        if stdout.channel.recv_ready():
            data = stdout.channel.recv(65535).decode(errors="ignore")

            lines = data.split("\n")

            for line in lines:
                if line.strip():
                    print("[TCPDUMP]", line.strip())

                    if "Trap(" in line:
                        count += 1

        time.sleep(0.5)

    return count
# -------------------------------------------------------
# BASE SNMP CONFIG
# -------------------------------------------------------
print("\nSTEP 2: Base SNMP Config")

send(sh, "configure terminal")
send(sh, "snmp-server community public ip-range 192.168.180.0 255.255.255.0 public")
send(sh, f"snmp-server user hfcl engine-id {ENGINE_ID} md5 hfcl@123 priv des hfcl@123")
send(sh, "end")

# -------------------------------------------------------
# TEST FUNCTION
# -------------------------------------------------------
def test_snmp(version):

    print(f"\n===== SNMP {version.upper()} TEST =====")

    send(sh, "configure terminal")
    send(sh, "snmp-server host testing")
    send(sh, "no shutdown")

    if version == "v1":
        send(sh, f"host {SERVER_IP} 162 traps")
        send(sh, "version v1 public")

    elif version == "v2":
        send(sh, f"host {SERVER_IP} 162 informs")

    elif version == "v3":
        send(sh, f"host {SERVER_IP} 162 informs")
        send(sh, f"version v3 engineID {ENGINE_ID} hfcl")

    traps = [
        "linkUp","newRoot","linkDown","coldStart","warmStart",
        "risingAlarm","fallingAlarm","topologyChange","entConfigChange",
        "psecTrapInterfaces","lldpRemTablesChange","psecTrapGlobalsMain",
        "ipTrapInterfacesLink","authenticationFailure"
    ]

    for t in traps:
        send(sh, f"snmp trap {t}")

    send(sh, "end")

    print("\nTriggering traps (interface flap)...")

    send(sh, "configure terminal")
    send(sh, f"interface {INTERFACE}")
    send(sh, "shutdown")
    time.sleep(3)
    send(sh, "no shutdown")
    send(sh, "end")

    # Capture packets
    packets = capture_packets()

    print(f"\nCaptured packets: {packets}")

    if packets > 0:
        print(f"✅ SNMP {version} PASS")
        return True
    else:
        print(f"❌ SNMP {version} FAIL")
        return False

# -------------------------------------------------------
# RUN TESTS
# -------------------------------------------------------
r1 = test_snmp("v1")
r2 = test_snmp("v2")
r3 = test_snmp("v3")

# -------------------------------------------------------
# FINAL RESULT
# -------------------------------------------------------
print("\n" + "="*70)
if r1 and r2 and r3:
    print("FINAL RESULT : ✅ PASS")
else:
    print("FINAL RESULT : ❌ FAIL")
print("="*70)

sw.close()
srv.close()
