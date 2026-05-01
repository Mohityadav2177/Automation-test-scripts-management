import paramiko
import sys
import time
import random
import string
import re


# ===========================================================
# CONFIG
# ===========================================================
SWITCH_IP  = "192.168.180.136"
USERNAME   = "admin"
PASSWORD   = "admin"
SSH_PORT   = 22


# ===========================================================
# HELPERS
# ===========================================================
def rand_str(n=6):
    return ''.join(random.choices(string.ascii_lowercase, k=n))


def rand_pass(n=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def open_ssh_shell(host, user, pwd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(
        host,
        port=SSH_PORT,
        username=user,
        password=pwd,
        timeout=10,
        look_for_keys=False,
        allow_agent=False
    )

    shell = client.invoke_shell()
    time.sleep(1)

    while shell.recv_ready():
        shell.recv(65535)

    return client, shell


def send_cmd(shell, cmd, wait=1.5):
    shell.send(cmd + "\n")
    time.sleep(wait)

    output = ""
    while shell.recv_ready():
        output += shell.recv(65535).decode(errors="ignore")

    return output


def section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def step(n, msg):
    print(f"\n[Step {n}] {msg}")
    print("-" * 60)


# ===========================================================
# MAIN TEST
# ===========================================================
def run_test():
    results = {}

    # -------------------------------------------------------
    # PHASE 1 — CONNECT
    # -------------------------------------------------------
    section("PHASE 1 — SSH CONNECT")

    try:
        client, shell = open_ssh_shell(SWITCH_IP, USERNAME, PASSWORD)
        print("✅ Connected")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    send_cmd(shell, "terminal length 0")

    # -------------------------------------------------------
    # PHASE 2 — FETCH ENGINE ID
    # -------------------------------------------------------
    section("PHASE 2 — Fetch Engine ID")

    output = send_cmd(shell, "show snmp")
    print(output)

    match = re.search(r"Engine\s*ID\s*:\s*([0-9a-fA-F]+)", output, re.IGNORECASE)

    if not match:
        match = re.search(r"Local\s*Engine\s*ID\s*:\s*([0-9a-fA-F]+)", output, re.IGNORECASE)

    if match:
        engine_id = match.group(1)
        print(f"✅ Engine ID: {engine_id}")
        results["engine_id"] = "PASS"
    else:
        print("❌ Engine ID not found")
        results["engine_id"] = "FAIL"
        client.close()
        return False

    # -------------------------------------------------------
    # PHASE 3 — RANDOM DATA
    # -------------------------------------------------------
    section("PHASE 3 — Generate Random Data")

    SNMP_USER = "user_" + rand_str()
    COMMUNITY = "comm_" + rand_str()
    GROUP     = "grp_" + rand_str()

    auth_pass = rand_pass()
    priv_pass = rand_pass()

    print(f"User      : {SNMP_USER}")
    print(f"Community : {COMMUNITY}")
    print(f"Group     : {GROUP}")

    # -------------------------------------------------------
    # PHASE 4 — CONFIG USER + COMMUNITY
    # -------------------------------------------------------
    section("PHASE 4 — Configure SNMP User & Community")

    send_cmd(shell, "configure terminal")

    user_cmds = [
        f"snmp-server user {SNMP_USER} engine-id {engine_id} md5 {auth_pass} priv des {priv_pass}",
        f"snmp-server user {SNMP_USER} engine-id {engine_id} sha {auth_pass} priv aes {priv_pass}",
        f"snmp-server user {SNMP_USER} engine-id {engine_id} md5 {auth_pass} priv aes {priv_pass}",
        f"snmp-server user {SNMP_USER} engine-id {engine_id} sha {auth_pass} priv des {priv_pass}",
    ]

    for cmd in user_cmds:
        print(f"\n→ {cmd}")
        print(send_cmd(shell, cmd))

    comm_cmd = f"snmp-server community {COMMUNITY} ip-range 10.10.10.0 255.255.255.0 {auth_pass}"
    print(f"\n→ {comm_cmd}")
    print(send_cmd(shell, comm_cmd))

    send_cmd(shell, "end")
    print("\n✅ User & Community configured")

    # -------------------------------------------------------
    # PHASE 5 — CONFIG GROUP
    # -------------------------------------------------------
    section("PHASE 5 — Configure security-to-group")

    send_cmd(shell, "configure terminal")

    grp_cmds = [
        f"snmp-server security-to-group model v1 name {COMMUNITY} group {GROUP}",
        f"snmp-server security-to-group model v2c name {COMMUNITY} group {GROUP}",
        f"snmp-server security-to-group model v3 name {SNMP_USER} group {GROUP}",
    ]

    for cmd in grp_cmds:
        print(f"\n→ {cmd}")
        print(send_cmd(shell, cmd))

    send_cmd(shell, "end")

    # -------------------------------------------------------
    # PHASE 6 — VERIFY
    # -------------------------------------------------------
    section("PHASE 6 — Verification")

    grp_out = send_cmd(shell, "show snmp security-to-group")
    run_out = send_cmd(shell, "show running-config feature snmp")

    print(grp_out)
    print(run_out)

    if GROUP in grp_out and GROUP in run_out:
        print("✅ Group mapping present")
        results["group_create"] = "PASS"
    else:
        print("❌ Group mapping missing")
        results["group_create"] = "FAIL"

    # -------------------------------------------------------
    # PHASE 7 — REMOVE GROUP
    # -------------------------------------------------------
    section("PHASE 7 — Remove Group Mapping")

    send_cmd(shell, "configure terminal")

    for cmd in grp_cmds:
        del_cmd = "no " + cmd
        print(f"\n→ {del_cmd}")
        print(send_cmd(shell, del_cmd))

    send_cmd(shell, "end")

    # -------------------------------------------------------
    # PHASE 8 — VERIFY REMOVAL
    # -------------------------------------------------------
    section("PHASE 8 — Verify Removal")

    grp_out2 = send_cmd(shell, "show snmp security-to-group")
    run_out2 = send_cmd(shell, "show running-config feature snmp")

    print(grp_out2)
    print(run_out2)

    if GROUP not in grp_out2 and GROUP not in run_out2:
        print("✅ Group removed successfully")
        results["group_delete"] = "PASS"
    else:
        print("❌ Group still present")
        results["group_delete"] = "FAIL"

    client.close()

    # -------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------
    section("TEST SUMMARY")

    all_pass = True
    for k, v in results.items():
        icon = "✅" if v == "PASS" else "❌"
        print(f"{icon} {k} : {v}")
        if v == "FAIL":
            all_pass = False

    if all_pass:
        print("\n🎯 TEST CASE 40 PASSED")
    else:
        print("\n❌ TEST CASE 40 FAILED")

    return all_pass


# ===========================================================
# ENTRY
# ===========================================================
if __name__ == "__main__":

    if len(sys.argv) == 4:
        SWITCH_IP = sys.argv[1]
        USERNAME  = sys.argv[2]
        PASSWORD  = sys.argv[3]

    success = run_test()
    sys.exit(0 if success else 1)
