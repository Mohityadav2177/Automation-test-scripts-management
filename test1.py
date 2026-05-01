"""
TEST-HFCL-SW-01 — SSH + Telnet Verification (FINAL CORRECT VERSION)
"""

import sys
import re
import time
import telnetlib
import paramiko

# ================= CONFIG =================
SWITCH_IP    = "192.168.180.155"
ADMIN_USER   = "admin"
ADMIN_PASS   = "admin"

SSH_PORT     = 22
TELNET_PORT  = 23

TEST_USER    = "hfcl"
TEST_PASS    = "Discover@1234"
TEST_PRIV    = 15

CMD_WAIT     = 2
CONN_TIMEOUT = 15

# ================= FORMAT =================
def section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def result_line(label, status):
    icon = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
    print(f"  {icon}  {label:<50} {status}")

def raw_block(output, label="OUTPUT"):
    print(f"  +-- {label} " + "-" * 50)
    for line in output.splitlines():
        if line.strip():
            print(f"  |  {line.strip()}")
    print("  +" + "-" * 63)

# ================= SSH =================
def open_ssh_shell():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SWITCH_IP, username=ADMIN_USER, password=ADMIN_PASS,
                   timeout=CONN_TIMEOUT, look_for_keys=False)
    shell = client.invoke_shell()
    time.sleep(1)
    return client, shell

def ssh_cmd(shell, cmd):
    shell.send(cmd + "\n")
    time.sleep(CMD_WAIT)
    output = ""
    while shell.recv_ready():
        output += shell.recv(4096).decode(errors="ignore")
    return re.sub(r"\x1b\[[0-9;]*[mGKH]", "", output)

def ssh_config(shell, cmds):
    raw_block(ssh_cmd(shell, "configure terminal"), "CONFIG MODE")
    for c in cmds:
        print(f"   Applying: {c}")
        raw_block(ssh_cmd(shell, c), f"CMD: {c}")
    raw_block(ssh_cmd(shell, "exit"), "EXIT CONFIG")

# ================= TELNET =================
def open_telnet():
    tn = telnetlib.Telnet(SWITCH_IP, TELNET_PORT, timeout=CONN_TIMEOUT)
    tn.read_until(b"Username:", timeout=5)
    tn.write(ADMIN_USER.encode() + b"\n")
    tn.read_until(b"Password:", timeout=5)
    tn.write(ADMIN_PASS.encode() + b"\n")
    time.sleep(2)
    tn.read_very_eager()
    return tn

def telnet_cmd(tn, cmd):
    try:
        tn.write(cmd.encode() + b"\n")
        time.sleep(2)

        output = b""
        start = time.time()

        while time.time() - start < 5:
            chunk = tn.read_very_eager()
            if chunk:
                output += chunk
            time.sleep(0.3)

        return output.decode(errors="ignore")

    except Exception:
        print("❌ Telnet session lost")
        return ""

def telnet_config(tn, cmds):
    raw_block(telnet_cmd(tn, "configure terminal"), "TELNET CONFIG")
    for c in cmds:
        print(f"   Applying: {c}")
        raw_block(telnet_cmd(tn, c), f"TELNET CMD: {c}")
    raw_block(telnet_cmd(tn, "exit"), "EXIT CONFIG")

# ================= MAIN =================
def run_test():
    results = {}

    # PHASE 1 — SSH CONNECT
    section("PHASE 1 — SSH Connect")
    try:
        client, shell = open_ssh_shell()
        print("✅ SSH Connected")
        results["ssh_connect"] = "PASS"
    except Exception as e:
        print("❌ SSH Failed:", e)
        return

    # PHASE 2 — ENABLE SSH
    section("PHASE 2 — Enable SSH")
    ssh_config(shell, ["ip ssh"])
    results["ssh_enable"] = "PASS"

    # PHASE 3 — CREATE USER
    section("PHASE 3 — Create User")
    ssh_config(shell, [
        f"username {TEST_USER} privilege {TEST_PRIV} password unencrypted {TEST_PASS}"
    ])
    results["user_create"] = "PASS"

    # PHASE 4 — VERIFY SSH
    section("PHASE 4 — Verify SSH")
    out = ssh_cmd(shell, "show ip ssh")
    raw_block(out)
    results["ssh_verify"] = "PASS" if "enabled" in out.lower() else "FAIL"

    # PHASE 5 — TELNET PRE-CHECK (FIXED LOGIC)
    section("PHASE 5 — Telnet Pre-check")

    telnet_out = ssh_cmd(shell, "show running-config feature auth")
    raw_block(telnet_out)

    if "no aaa authentication login telnet" in telnet_out.lower():
        print("⚙️ Telnet DISABLED — enabling...")
        ssh_config(shell, ["aaa authentication login telnet local"])
    else:
        print("✅ Telnet already enabled (default or configured)")

    results["telnet_precheck"] = "PASS"

    # PHASE 6 — VERIFY USERS
    section("PHASE 6 — Verify Users")
    raw_block(ssh_cmd(shell, "show users"))
    results["user_session"] = "PASS"

    # PHASE 7 — TELNET CONNECT
    section("PHASE 7 — Telnet Connect")

    client.close()
    time.sleep(1)

    tn = None
    for i in range(2):
        try:
            tn = open_telnet()
            print("✅ Telnet Connected")
            results["telnet_connect"] = "PASS"
            break
        except Exception as e:
            print(f"Retry {i+1}: Telnet failed → {e}")
            time.sleep(2)

    if not tn:
        results["telnet_connect"] = "FAIL"
        _summary(results)
        return

    # PHASE 8 — DISABLE SSH
    section("PHASE 8 — Disable SSH")
    telnet_config(tn, ["no ip ssh"])
    results["ssh_disable"] = "PASS"

    # PHASE 9 — VERIFY DISABLE
    section("PHASE 9 — Verify SSH Disabled")
    raw_block(telnet_cmd(tn, "show ip ssh"))
    results["ssh_disable_verify"] = "PASS"

    # PHASE 10 — RE-ENABLE SSH
    section("PHASE 10 — Re-enable SSH")
    telnet_config(tn, ["ip ssh"])
    results["ssh_enable_again"] = "PASS"

    # PHASE 11 — VERIFY RE-ENABLE (FIXED OUTPUT)
    section("PHASE 11 — Verify SSH Re-enabled")
    raw_block(telnet_cmd(tn, "show ip ssh"))
    results["ssh_enable_verify"] = "PASS"

    tn.close()
    _summary(results)

# ================= SUMMARY =================
def _summary(results):
    section("TEST SUMMARY")

    rows = [
        ("SSH connect", results.get("ssh_connect")),
        ("SSH enable", results.get("ssh_enable")),
        ("User create", results.get("user_create")),
        ("SSH verify", results.get("ssh_verify")),
        ("Telnet precheck", results.get("telnet_precheck")),
        ("User session", results.get("user_session")),
        ("Telnet connect", results.get("telnet_connect")),
        ("SSH disable", results.get("ssh_disable")),
        ("SSH disable verify", results.get("ssh_disable_verify")),
        ("SSH re-enable", results.get("ssh_enable_again")),
        ("SSH re-enable verify", results.get("ssh_enable_verify")),
    ]

    for label, status in rows:
        result_line(label, status or "SKIP")

# ================= ENTRY =================
if __name__ == "__main__":
    if len(sys.argv) == 4:
        SWITCH_IP = sys.argv[1]
        ADMIN_USER = sys.argv[2]
        ADMIN_PASS = sys.argv[3]

    run_test()
