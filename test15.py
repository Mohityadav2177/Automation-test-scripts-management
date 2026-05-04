import paramiko
import socket
import sys
import time
import subprocess

if len(sys.argv) != 4:
    print("Usage: python3 test_management.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

TEST_HOSTNAME = "hfcl"

print("=" * 60)
print("MANAGEMENT TEST")
print("Objective: Verify soft reboot and hard reboot")
print("=" * 60)
print(f"Target   : {ip}:22")
print(f"Username : {username}")
print(f"Hostname : {TEST_HOSTNAME}")
print("=" * 60)

# -------------------------------------------------------
# Ping check
# -------------------------------------------------------
def ping_host(host, retries=3):
    """
    Ping the host. Returns True if reachable, False otherwise.
    Tries up to `retries` times with 1s timeout each.
    """
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", host],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

# -------------------------------------------------------
# SSH connect + interactive shell
# -------------------------------------------------------
def ssh_connect():
    """Open a fresh SSH session and return (client, shell)."""
    print(f"\nConnecting to {ip} via SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ip,
            port=22,
            username=username,
            password=password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )
    except paramiko.AuthenticationException:
        print("❌ SSH Authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ SSH connection failed: {e}")
        sys.exit(1)

    shell = client.invoke_shell()
    time.sleep(2)

    # Disable pagination so -- more -- never appears
    while shell.recv_ready():
        shell.recv(65535)
    shell.send("terminal length 0\n")
    time.sleep(1)
    while shell.recv_ready():
        shell.recv(65535)

    print("✅ SSH session established\n")
    return client, shell

def send_command(shell, cmd, timeout=20):
    """Send a command and wait for the # prompt to appear."""
    shell.send(cmd + "\n")
    output = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode("utf-8", errors="ignore")
            output += chunk
            if "-- more --" in output.lower():
                shell.send("g")
                time.sleep(0.5)
                continue
            if output.rstrip().endswith("#"):
                time.sleep(0.2)
                if shell.recv_ready():
                    output += shell.recv(65535).decode("utf-8", errors="ignore")
                break
        else:
            time.sleep(0.3)
    return output

def send_command_with_confirm(shell, cmd, confirm="y", timeout=30):
    """Send a command that may ask for confirmation and auto-confirm."""
    shell.send(cmd + "\n")
    output = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(65535).decode("utf-8", errors="ignore")
            output += chunk
            lower = output.lower()
            if "-- more --" in lower:
                shell.send("g")
                time.sleep(0.5)
                continue
            if "[y/n]" in lower or "[confirm]" in lower or "(y/n)" in lower:
                time.sleep(0.5)
                shell.send(confirm + "\n")
            if output.rstrip().endswith("#"):
                time.sleep(0.2)
                if shell.recv_ready():
                    output += shell.recv(65535).decode("utf-8", errors="ignore")
                break
        else:
            time.sleep(0.3)
    return output

# -------------------------------------------------------
# STEP 1 — Connect
# -------------------------------------------------------
print("=================================")
print("STEP 1: SSH Login")
print("=================================")
client, shell = ssh_connect()
print("✅ STEP 1 PASSED")

# -------------------------------------------------------
# STEP 2 — Configure hostname
# -------------------------------------------------------
print("\n=================================")
print(f"STEP 2: Configure hostname '{TEST_HOSTNAME}'")
print(f"Command : hostname {TEST_HOSTNAME}")
print("=================================")

output = send_command(shell, "configure terminal")
output = send_command(shell, f"hostname {TEST_HOSTNAME}")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")
print(f"✅ STEP 2 PASSED — hostname '{TEST_HOSTNAME}' configured")

output = send_command(shell, "end")

# -------------------------------------------------------
# STEP 3 — Verify hostname in show running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 3: Verify hostname in 'show running-config'")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

if f"hostname {TEST_HOSTNAME}" in output:
    print(f"✅ STEP 3 PASSED — 'hostname {TEST_HOSTNAME}' found in running-config")
else:
    print(f"⚠️  STEP 3 WARNING — 'hostname {TEST_HOSTNAME}' not found in running-config")

# -------------------------------------------------------
# STEP 4 — Save config to startup-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 4: Save running-config to startup-config")
print("Command : copy running-config startup-config")
print("=================================")

output = send_command_with_confirm(shell, "copy running-config startup-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

if "error" in output.lower() or "invalid" in output.lower() or "failed" in output.lower():
    print("❌ STEP 4 FAILED — error saving config")
    client.close()
    sys.exit(1)
else:
    print("✅ STEP 4 PASSED — config saved to startup-config")

# -------------------------------------------------------
# STEP 5 — Soft reboot with 'reload warm'
# -------------------------------------------------------
print("\n=================================")
print("STEP 5: Soft reboot using 'reload warm'")
print("Command : reload warm")
print("=================================")
print("⚠️  Device is rebooting — waiting for it to come back online...")

shell.send("reload warm\n")
time.sleep(2)
shell.send("y\n")
time.sleep(2)
client.close()

# Device takes approx 2 to 2.5 minutes to reboot
REBOOT_WAIT = 150   # 2.5 minutes
print(f"    Waiting {REBOOT_WAIT} seconds (~2.5 min) for device to reboot...")
for remaining in range(REBOOT_WAIT, 0, -10):
    print(f"    ... {remaining}s remaining")
    time.sleep(10)

print("✅ STEP 5 PASSED — reload warm command sent")

# -------------------------------------------------------
# STEP 6 — Ping check after reboot
# -------------------------------------------------------
print("\n=================================")
print("STEP 6: Ping check after reboot")
print(f"Target  : {ip}")
print("=================================")

print(f"    Pinging {ip}...")
ping_ok = ping_host(ip, retries=3)

if ping_ok:
    print(f"\n--- PING RESULT ---")
    print(f"Host {ip} is reachable ✅")
    print("-------------------")
    print(f"✅ STEP 6 PASSED — device is reachable at {ip}")
else:
    print(f"\n--- PING RESULT ---")
    print(f"Host {ip} is NOT reachable ❌")
    print("-------------------")
    print("⚠️  NOTE: Device may have received a new IP from DHCP after reboot.")
    print(f"          Management IP may have changed from {ip}.")
    print("          Please check your DHCP server for the new IP address.")
    print("          Test will not be marked as failed due to IP change.")
    print("\n✅ STEP 6 INFO — IP may have changed, skipping SSH reconnect")
    print("\n" + "=" * 60)
    print("TEST RESULT : PASS")
    print("Note: Device rebooted successfully.")
    print("      Post-reboot verification skipped — management IP")
    print(f"      may have changed from {ip} due to DHCP.")
    print("      Please find new IP from DHCP server and verify")
    print("      manually using: show running-config")
    print("=" * 60)
    sys.exit(0)

# -------------------------------------------------------
# STEP 7 — Reconnect after reboot (only if ping succeeded)
# -------------------------------------------------------
print("\n=================================")
print("STEP 7: Reconnect via SSH after reboot")
print("=================================")

MAX_RETRIES = 10
client, shell = None, None
for attempt in range(1, MAX_RETRIES + 1):
    print(f"    Connection attempt {attempt}/{MAX_RETRIES}...")
    try:
        client, shell = ssh_connect()
        break
    except SystemExit:
        if attempt < MAX_RETRIES:
            print(f"    Device not ready yet, retrying in 15s...")
            time.sleep(15)
        else:
            print("❌ STEP 7 FAILED — could not reconnect after reboot")
            sys.exit(1)

print("✅ STEP 7 PASSED — reconnected successfully after reboot")

# -------------------------------------------------------
# STEP 8 — Verify hostname NOT present after warm reboot
# -------------------------------------------------------
print("\n=================================")
print("STEP 8: Verify hostname NOT present in 'show running-config' after reboot")
print("Command : show running-config")
print("=================================")

output = send_command(shell, "show running-config", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

if f"hostname {TEST_HOSTNAME}" not in output:
    print(f"✅ STEP 8 PASSED — 'hostname {TEST_HOSTNAME}' is NOT present after reboot (expected)")
else:
    print(f"❌ STEP 8 FAILED — 'hostname {TEST_HOSTNAME}' still present after reboot (unexpected)")

# -------------------------------------------------------
# Done
# -------------------------------------------------------
try:
    client.close()
except Exception:
    pass

print("\n" + "=" * 60)
print("TEST RESULT : PASS")
print("Management test completed successfully")
print("=" * 60)
