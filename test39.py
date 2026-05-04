import paramiko
import sys
import time
import random
import string


# ===========================================================
# CONFIG (CLI override supported)
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

    try:
        client, shell = open_ssh_shell(SWITCH_IP, USERNAME, PASSWORD)
        print("✅ Connected to switch")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    send_cmd(shell, "terminal length 0")

    # -------------------------------------------------------
    # PHASE 2 — VERIFY SNMP + RANDOM DATA
    # -------------------------------------------------------
    section("PHASE 2 — Verify SNMP & Prepare Data")

    step(2, "Checking SNMP status")
    snmp_out = send_cmd(shell, "show snmp")
    print(snmp_out)

    if "snmp mode" in snmp_out.lower() and "enabled" in snmp_out.lower():
        print("✅ SNMP is ENABLED")
        results["snmp_status"] = "PASS"
    else:
        print("❌ SNMP not enabled")
        results["snmp_status"] = "FAIL"

    # ✅ Random data
    COMMUNITY = "comm_" + rand_str()
    PASSWORD_SNMP = rand_pass()

    ip1 = random.randint(1, 223)
    ip2 = random.randint(0, 255)
    ip3 = random.randint(0, 255)

    IP_RANGE = f"{ip1}.{ip2}.{ip3}.0"
    MASK = "255.255.255.0"

    print("\nGenerated Data:")
    print(f"Community : {COMMUNITY}")
    print(f"Password  : {PASSWORD_SNMP}")
    print(f"IP Range  : {IP_RANGE}/{MASK}")

    # -------------------------------------------------------
    # PHASE 3 — CONFIGURE SNMP COMMUNITY
    # -------------------------------------------------------
    section("PHASE 3 — Configure SNMP Community")

    send_cmd(shell, "configure terminal")

    cmd1 = f"snmp-server community {COMMUNITY} ip-range {IP_RANGE} {MASK} {PASSWORD_SNMP}"
    cmd2 = f"snmp-server community {COMMUNITY} {PASSWORD_SNMP}"

    print(f"\n→ {cmd1}")
    print(send_cmd(shell, cmd1))

    print(f"\n→ {cmd2}")
    print(send_cmd(shell, cmd2))

    send_cmd(shell, "end")

    print("\n✅ SNMP Community configured")

    # -------------------------------------------------------
    # PHASE 4 — VERIFY CONFIG
    # -------------------------------------------------------
    section("PHASE 4 — Verification")

    step(4, "Check SNMP community")
    comm_out = send_cmd(shell, "show snmp community")
    print(comm_out)

    step(5, "Check running config")
    run_out = send_cmd(shell, "show running-config feature snmp")
    print(run_out)

    if COMMUNITY in comm_out and COMMUNITY in run_out:
        print("✅ SNMP Community present")
        results["snmp_create"] = "PASS"
    else:
        print("❌ SNMP Community missing")
        results["snmp_create"] = "FAIL"

    # -------------------------------------------------------
    # PHASE 5 — REMOVE SNMP COMMUNITY
    # -------------------------------------------------------
    section("PHASE 5 — Remove SNMP Community")

    send_cmd(shell, "configure terminal")

    del_cmd1 = f"no snmp-server community {COMMUNITY} ip-range {IP_RANGE} {MASK} {PASSWORD_SNMP}"
    del_cmd2 = f"no snmp-server community {COMMUNITY} {PASSWORD_SNMP}"

    print(f"\n→ {del_cmd1}")
    print(send_cmd(shell, del_cmd1))

    print(f"\n→ {del_cmd2}")
    print(send_cmd(shell, del_cmd2))

    send_cmd(shell, "end")

    print("\n✅ SNMP Community removed")

    # -------------------------------------------------------
    # PHASE 6 — VERIFY REMOVAL
    # -------------------------------------------------------
    section("PHASE 6 — Verify Removal")

    comm_out2 = send_cmd(shell, "show snmp community")
    run_out2 = send_cmd(shell, "show running-config feature snmp")

    print(comm_out2)
    print(run_out2)

    if COMMUNITY not in comm_out2 and COMMUNITY not in run_out2:
        print("✅ SNMP Community successfully removed")
        results["snmp_delete"] = "PASS"
    else:
        print("❌ SNMP Community still present")
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
        print("\n🎯 TEST CASE 39 PASSED")
    else:
        print("\n❌ TEST CASE 39 FAILED")

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
