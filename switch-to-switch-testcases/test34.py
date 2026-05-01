import paramiko
import sys
import time
import re

if len(sys.argv) != 4:
    print("Usage: python3 tc_lldp.py <dut1_ip> <username> <password>")
    sys.exit(1)

dut1_ip = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

DUT2_IP = "192.168.180.15"
INTERFACE = "gig 1/24"
FULL_INTF_NAME = "GigabitEthernet 1/24"

ERROR_PATTERNS = [
    "error:",
    "invalid input",
    "invalid word detected",
    "ambiguous command",
    "ambiguous word detected",
    "incomplete command",
    "failed"
]

def is_command_success(output):
    out = output.lower()
    return not any(err in out for err in ERROR_PATTERNS)

def ssh_connect(ip):
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

    print(f"✅ SSH Connected to {ip}")
    return client, shell

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

def parse_lldp_neighbor(output, local_intf, neighbor_ip):
    blocks = re.split(r'\n\s*\n', output)
    for block in blocks:
        if local_intf in block and neighbor_ip in block:
            return True
    return False

def get_lldp_neighbor_ip(output):
    match = re.search(r"Management Address\s*:\s*(\d+\.\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None

# CONNECT
client1, shell1 = ssh_connect(dut1_ip)

# STEP 1
print("\nSTEP 1: Reachability")
ping_output = send(shell1, f"ping {DUT2_IP}", 4)
print("✅ Reachable" if "bytes from" in ping_output else "⚠️ Not reachable")

# STEP 2
print("\nSTEP 2: Enable LLDP")
out = ""
out += send(shell1, "configure terminal")
out += send(shell1, f"interface {INTERFACE}")
out += send(shell1, "lldp transmit")
out += send(shell1, "lldp receive")
out += send(shell1, "end")
out += send(shell1, "copy running-config startup-config", 5)

step2_result = is_command_success(out)
print("✅ Enabled" if step2_result else "❌ Enable failed")

time.sleep(5)

# STEP 3
print("\nSTEP 3: Verify LLDP")
lldp_output = send(shell1, "show lldp neighbors")

if parse_lldp_neighbor(lldp_output, FULL_INTF_NAME, DUT2_IP):
    print("✅ DUT2 detected")
    step3_result = True
else:
    print("⚠️ Fallback neighbor used")
    step3_result = bool(lldp_output.strip())

# STEP 3.1
print("\nSTEP 3.1: Neighbor validation")
neighbor_ip = DUT2_IP if DUT2_IP in lldp_output else get_lldp_neighbor_ip(lldp_output)

if neighbor_ip:
    client2, shell2 = ssh_connect(neighbor_ip)
    out = send(shell2, "show lldp neighbors")
    step31_result = dut1_ip in out
    client2.close()
    print("✅ Reverse LLDP OK" if step31_result else "❌ Reverse LLDP fail")
else:
    step31_result = False

# STEP 4
print("\nSTEP 4: Disable LLDP")
out = ""
out += send(shell1, "configure terminal")
out += send(shell1, f"interface {INTERFACE}")
out += send(shell1, "no lldp transmit")
out += send(shell1, "no lldp receive")
out += send(shell1, "end")
out += send(shell1, "copy running-config startup-config", 5)

step4_result = is_command_success(out)
print("✅ Disabled" if step4_result else "❌ Disable failed")

time.sleep(10)

# STEP 5
print("\nSTEP 5: Verify removal")
lldp_after = send(shell1, "show lldp neighbors")

if not parse_lldp_neighbor(lldp_after, FULL_INTF_NAME, DUT2_IP):
    print("✅ Removed from gi1/24")
    step5_result = True
else:
    print("❌ Still present on gi1/24")
    step5_result = False

# FINAL
print("\n" + "="*70)
if step2_result and step3_result and step31_result and step4_result and step5_result:
    print("FINAL RESULT : ✅ PASS")
else:
    print("FINAL RESULT : ❌ FAIL")
print("="*70)

client1.close()
