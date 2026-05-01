import paramiko
import sys
import time
import re

# -------------------------------------------------------
# USAGE
# -------------------------------------------------------
if len(sys.argv) != 6:
    print("Usage: python3 demo_snmp_full.py <switch_ip> <user> <pass> <server_user> <server_pass>")
    sys.exit(1)

SWITCH_IP = sys.argv[1]
USER      = sys.argv[2]
PASS      = sys.argv[3]
SRV_USER  = sys.argv[4]
SRV_PASS  = sys.argv[5]

SERVER_IP = "192.168.180.69"
INTERFACE = "GigabitEthernet 1/23"
OID_SYS   = "1.3.6.1.2.1.1"
OID_NAME  = "1.3.6.1.2.1.1.5.0"
OID_IF    = "1.3.6.1.2.1.2.2.1.7.1000023"

print("="*70)
print("TEST CASE : SNMP FULL VALIDATION (ALL OPERATIONS + TRAPS)")
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

def send(sh, cmd, wait=0.5):
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

def clear_buffer(sh):
    while sh.recv_ready():
        sh.recv(65535)



# -------------------------------------------------------
# CLEAN SNMP CONFIG
# -------------------------------------------------------
def clear_snmp_config(sh , ENGINE_ID):

    print("\n[CLEANUP] Clearing SNMP configuration")

    send(sh, "configure terminal")
    send(sh, "no snmp-server host testing")
    send(sh, "no snmp-server community public ip-range 192.168.180.0 255.255.255.0")
    send(sh, "no snmp-server user hfcl engine-id {ENGINE_ID}")
    send(sh, "no snmp-server security-to-group model v3 name hfcl group default_rw_group")

    send(sh, "no snmp-server access default_ro_group model any level noauth read default_view write default_view")
    send(sh, "no snmp-server access default_ro_group model v3 level priv read default_view write default_view")

    traps = [
        "linkUp","newRoot","linkDown","coldStart","warmStart",
        "risingAlarm","fallingAlarm","topologyChange","entConfigChange",
        "psecTrapInterfaces","lldpRemTablesChange","psecTrapGlobalsMain",
        "ipTrapInterfacesLink","authenticationFailure"
    ]

    for t in traps:
        send(sh, f"no snmp trap {t}")

    send(sh, "end")





# -------------------------------------------------------
# CONNECT SWITCH + SERVER
# -------------------------------------------------------
sw, sh = connect(SWITCH_IP, USER, PASS)
send(sh, "terminal length 0", wait=1)
srv = paramiko.SSHClient()
srv.set_missing_host_key_policy(paramiko.AutoAddPolicy())
srv.connect(SERVER_IP, username=SRV_USER, password=SRV_PASS)

print(f"✅ Connected Switch {SWITCH_IP}")
print(f"✅ Connected Server {SERVER_IP}")

# -------------------------------------------------------
# FETCH ENGINE ID
# -------------------------------------------------------
out = send(sh, "show snmp")
engine = re.search(r"Engine ID\s*:\s*(\S+)", out)
ENGINE_ID = engine.group(1) if engine else "80000df9030006ae9d13ce"

print(f"✅ Engine ID: {ENGINE_ID}")

# -------------------------------------------------------
# RUN COMMAND ON SERVER
# -------------------------------------------------------
def run_srv(cmd):
    print(f"\n[SERVER] {cmd}")
    stdin, stdout, stderr = srv.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out.strip())
    if err:
        print("ERR:", err.strip())
    return out

# -------------------------------------------------------
# TCPDUMP CAPTURE (FIXED - NO HANG)
# -------------------------------------------------------
def capture_trap(duration=10):

    cmd = "sudo -S timeout {} tcpdump -i ens160 udp port 162 -nn -l".format(duration)

    stdin, stdout, stderr = srv.exec_command(cmd, get_pty=True)

    stdin.write(SRV_PASS + "\n")
    stdin.flush()

    output = stdout.read().decode(errors="ignore")
    print("\n[TCPDUMP OUTPUT]")
    print(output)

    return output.count("Trap(")




"""

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
"""
# -------------------------------------------------------
# STEP 1: BASE CONFIG
# -------------------------------------------------------
print("\nSTEP 1: SNMP BASE CONFIG")
clear_buffer(sh)
send(sh, "configure terminal")
send(sh, "snmp-server community public ip-range 192.168.180.0 255.255.255.0 public")
send(sh, f"snmp-server user hfcl engine-id {ENGINE_ID} md5 hfcl@123 priv des hfcl@123")
send(sh, "snmp-server security-to-group model v3 name hfcl group default_rw_group")
send(sh, "snmp-server access default_ro_group model any level noauth read default_view write default_view")
send(sh, "snmp-server access default_ro_group model v3 level priv read default_view write default_view")

traps = [
"linkUp","newRoot","linkDown","coldStart","warmStart",
"risingAlarm","fallingAlarm","topologyChange","entConfigChange",
"psecTrapInterfaces","lldpRemTablesChange","psecTrapGlobalsMain",
"ipTrapInterfacesLink","authenticationFailure"
]

for t in traps:
    send(sh, f"snmp trap {t}")

send(sh, "end")

# -------------------------------------------------------
# STEP 2: SNMP OPERATIONS
# -------------------------------------------------------
print("\nSTEP 2: SNMP OPERATIONS")

# WALK
run_srv(f"snmpwalk -v1 -c public {SWITCH_IP} {OID_SYS}")
run_srv(f"snmpwalk -v2c -c public {SWITCH_IP} {OID_SYS}")
run_srv(f"snmpwalk -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} {SWITCH_IP} {OID_SYS}")

# GET
run_srv(f"snmpget -v2c -c public {SWITCH_IP} {OID_NAME}")
run_srv(f"snmpget -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} {SWITCH_IP} {OID_NAME}")

# GETNEXT
run_srv(f"snmpgetnext -v2c -c public {SWITCH_IP} {OID_SYS}")
run_srv(f"snmpgetnext -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} {SWITCH_IP} {OID_SYS}")

# BULKGET
run_srv(f"snmpbulkget -v2c -c public -Cn0 -Cr10 {SWITCH_IP} 1.3.6.1.2.1.2.2.1.2")
run_srv(f"snmpbulkget -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} -Cn0 -Cr10 {SWITCH_IP} 1.3.6.1.2.1.2.2.1.2")

# -------------------------------------------------------
# STEP 3: SNMP SET VALIDATION
# -------------------------------------------------------
print("\nSTEP 3: SNMP SET VALIDATION")

print("\nInterface BEFORE:")
send(sh, f"show interface {INTERFACE} status")

# v2c SET
run_srv(f"snmpset -v2c -c public {SWITCH_IP} {OID_IF} i 2")
time.sleep(3)

print("\nInterface AFTER SHUT:")
send(sh, f"show interface {INTERFACE} status" , wait=2)

run_srv(f"snmpset -v2c -c public {SWITCH_IP} {OID_IF} i 1")
time.sleep(3)

print("\nInterface AFTER NO SHUT:")
send(sh, f"show interface {INTERFACE} status" , wait=6)

# v3 SET

print("\nInterface BEFORE:")
send(sh, f"show interface {INTERFACE} status")

run_srv(f"snmpset -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} {SWITCH_IP} {OID_IF} i 2")
time.sleep(3)


print("\nInterface AFTER SHUT:")
send(sh, f"show interface {INTERFACE} status" , wait=2)

run_srv(f"snmpset -v3 -u hfcl -l authPriv -a MD5 -A hfcl@123 -x DES -X hfcl@123 -e {ENGINE_ID} {SWITCH_IP} {OID_IF} i 1")
time.sleep(3)


print("\nInterface AFTER NO SHUT:")
send(sh, f"show interface {INTERFACE} status" , wait=6)
time.sleep(3)
# -------------------------------------------------------
# STEP 4: TRAP TEST
# -------------------------------------------------------
def trap_test(version):

    print(f"\n===== TRAP TEST {version.upper()} =====")

    send(sh, "configure terminal")
    send(sh, "snmp-server host testing")
    send(sh, "no shutdown")

    if version == "v1":
        send(sh, f"host {SERVER_IP} 162 traps")
        send(sh, "version v1 public")

    elif version == "v2":
        send(sh, f"host {SERVER_IP} 162 informs")

    elif version == "v3":
        send(sh, f"host {SERVER_IP} 162 traps")
        send(sh, f"version v3 engineID {ENGINE_ID} hfcl")

    send(sh, "end")

    print("\nTriggering interface flap...")
    send(sh, "configure terminal")
    send(sh, f"interface {INTERFACE}")
    send(sh, "shutdown")
    time.sleep(2)
    send(sh, "no shutdown")
    send(sh, "end")

    pkts = capture_trap()

    print(f"Captured traps: {pkts}")

    return pkts > 0

r1 = trap_test("v1")
r2 = trap_test("v2")
r3 = trap_test("v3")



# -------------------------------------------------------
# POST CLEAN INTERFACE
# -------------------------------------------------------
print("\n[CLEANUP] Restoring interface")
send(sh, "configure terminal")
send(sh, f"interface {INTERFACE}")
send(sh, "no shutdown")
send(sh, "end")

# -------------------------------------------------------
# FINAL CLEAN
# -------------------------------------------------------
clear_snmp_config(sh , ENGINE_ID)


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
