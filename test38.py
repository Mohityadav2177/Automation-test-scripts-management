import paramiko
import sys
import time
import re
import random
import string

# ===========================================================
# CONFIG (can override via CLI)
# ===========================================================
SWITCH_IP  = "192.168.180.136"
USERNAME   = "admin"
PASSWORD   = "admin"
SSH_PORT   = 22


# ===========================================================
# HELPERS
# ===========================================================
def rand_pass():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


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
    try:
        shell.send(cmd + "\n")
        time.sleep(wait)

        output = ""
        while shell.recv_ready():
            output += shell.recv(65535).decode(errors="ignore")

        return output
    except Exception as e:
        return f"ERROR: {e}"


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

    step(1, "Connecting to switch")
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

    step(2, "Running 'show snmp'")
    output = send_cmd(shell, "show snmp")
    print(output)

    match = re.search(r"Engine\s*ID\s*:\s*([0-9a-fA-F]+)", output, re.IGNORECASE)

    if not match:
        match = re.search(r"Local\s*Engine\s*ID\s*:\s*([0-9a-fA-F]+)", output, re.IGNORECASE)

    if match:
        engine_id = match.group(1)
        print(f"✅ Engine ID Found: {engine_id}")
        results["engine_id"] = "PASS"
    else:
        print("❌ Engine ID not found")
        print("DEBUG:", repr(output))
        results["engine_id"] = "FAIL"
        client.close()
        return False

    # -------------------------------------------------------
    # PHASE 3 — CONFIGURE USERS
    # -------------------------------------------------------
    section("PHASE 3 — Configure SNMP Users")

    users = [
        ("user_md5_des", "md5", "des"),
        ("user_sha_aes", "sha", "aes"),
        ("user_md5_aes", "md5", "aes"),
        ("user_sha_des", "sha", "des"),
    ]

    user_cmds = []

    send_cmd(shell, "configure terminal")

    for user, auth, priv in users:
        auth_pass = rand_pass()
        priv_pass = rand_pass()

        cmd = f"snmp-server user {user} engine-id {engine_id} {auth} {auth_pass} priv {priv} {priv_pass}"
        user_cmds.append(user)

        print(f"\n→ {cmd}")
        print(send_cmd(shell, cmd))

    send_cmd(shell, "end")
    print("\n✅ SNMP Users configured")

    # -------------------------------------------------------
    # PHASE 4 — VERIFY CONFIG
    # -------------------------------------------------------
    section("PHASE 4 — Verification")

    step(4, "Verify running-config")
    run_out = send_cmd(shell, "show  running-config feature snmp")
    print(run_out)

    step(5, "Verify SNMP users")
    user_out = send_cmd(shell, "show snmp user")
    print(user_out)

    all_present = all(user in user_out for user in user_cmds)

    if all_present:
        print("✅ All SNMP users present")
        results["snmp_create"] = "PASS"
    else:
        print("❌ Some SNMP users missing")
        results["snmp_create"] = "FAIL"

    # -------------------------------------------------------
    # PHASE 5 — REMOVE USERS
    # -------------------------------------------------------
    section("PHASE 5 — Unconfigure SNMP Users")

    send_cmd(shell, "configure terminal")

    for user in user_cmds:
        cmd = f"no snmp-server user {user} engine-id {engine_id}"
        print(f"\n→ {cmd}")
        print(send_cmd(shell, cmd))

    send_cmd(shell, "end")

    print("\n✅ SNMP Users removed")

    # -------------------------------------------------------
    # PHASE 6 — VERIFY REMOVAL
    # -------------------------------------------------------
    section("PHASE 6 — Verify Removal")

    step(6, "Check SNMP users again")
    user_out2 = send_cmd(shell, "show snmp user")
    print(user_out2)

    run_out2 = send_cmd(shell, "show  running-config feature snmp")
    print(run_out2)

    all_removed = all(user not in user_out2 and user not in run_out2 for user in user_cmds)

    if all_removed:
        print("✅ SNMP Users successfully removed")
        results["snmp_delete"] = "PASS"
    else:
        print("❌ SNMP Users still present")
        results["snmp_delete"] = "FAIL"

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
        print("\n🎯 TEST CASE 38 PASSED")
    else:
        print("\n❌ TEST CASE 38 FAILED")

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
