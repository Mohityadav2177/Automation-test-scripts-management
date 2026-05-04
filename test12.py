#!/usr/bin/env python3

"""
TEST-HFCL-SW-PING  —  Management: ICMP Ping Reachability Verification
======================================================================
Test Name      : Management
Test Objective : Verify ping for reachable and not reachable targets.

Test Configuration:
  Ping 192.168.180.69  from switch → server  (reachable)
  Ping 10.10.10.10     from switch → fake IP (not reachable)

Procedure:
  PHASE 1 : Ping reachable target from switch
            switch# ping 192.168.180.69
            Expected: success response (bytes received / % success)

  PHASE 2 : Ping unreachable target from switch
            switch# ping 10.10.10.10
            Expected: failure response (timeout / unreachable)

  PHASE 3 : Ping switch from server (reachable)
            server$ ping -c 4 192.168.180.110
            Expected: success response

  PHASE 4 : Ping unreachable target from server
            server$ ping -c 4 10.10.10.10
            Expected: failure response

Expected Result:
  - Reachable device   → successful ICMP response
  - Unreachable device → unsuccessful ICMP response (timeout/unreachable)

Usage:
  python3 ping_test.py <switch_ip> <admin_user> <admin_pass> [server_ip] [unreachable_ip]
  python3 ping_test.py 192.168.180.110 admin admin 192.168.180.69 10.10.10.10
"""

import sys
import re
import time
import subprocess
import paramiko


# ============================================================
# Configuration
# ============================================================

SWITCH_IP        = "192.168.180.110"
ADMIN_USER       = "admin"
ADMIN_PASS       = "admin"
SSH_PORT         = 22

REACHABLE_IP     = "192.168.180.69"
UNREACHABLE_IP   = "10.10.10.10"

CMD_WAIT         = 8
PING_COUNT       = 4


# ============================================================
# Formatting helpers
# ============================================================

def section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def step(n, desc):
    print(f"\n[Step {n}] {desc}")
    print("-" * 65)

def result_line(label, status):
    icon = "✅" if status == "PASS" else ("⚠️ " if status == "WARN" else "❌")
    print(f"  {icon}  {label:<54} {status}")

def raw_block(output, label="RAW OUTPUT"):
    clean = re.sub(r"\x1b\[[0-9;]*[mGKH]", "", str(output)).strip()
    print(f"  +-- {label} " + "-" * max(0, 55 - len(label)))
    for line in clean.splitlines():
        if line.strip():
            print(f"  |  {line.strip()}")
    print("  +" + "-" * 63)


# ============================================================
# SSH helpers
# ============================================================

def open_ssh_shell(hostname, username, password, port=22,
                   retries=3, delay=3):
    for attempt in range(1, retries + 1):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname, port=port,
                username=username, password=password,
                timeout=15, look_for_keys=False, allow_agent=False
            )
            shell = client.invoke_shell()
            time.sleep(0.5)
            _drain(shell)
            return client, shell
        except Exception as e:
            client.close()
            if attempt < retries:
                print(f"   ⏳ SSH attempt {attempt} failed ({e}), retrying...")
                time.sleep(delay)
            else:
                raise


def _drain(shell):
    time.sleep(0.2)
    while shell.recv_ready():
        shell.recv(4096)


def ssh_cmd(shell, cmd, timeout=CMD_WAIT):
    shell.send(cmd + "\n")
    time.sleep(timeout)

    output = ""
    while shell.recv_ready():
        output += shell.recv(4096).decode(errors="ignore")

    return output


# ============================================================
# FIXED SWITCH CLASSIFIER (MAIN BUG FIX HERE)
# ============================================================

def classify_switch_ping(output, expect_reachable):
    lower = output.lower()

    # SUCCESS patterns
    success = any(x in lower for x in [
        "success rate is 100",
        "bytes from",
        "!!!!!",
        "0% packet loss"
    ])

    # FAILURE patterns
    failure = any(x in lower for x in [
        "success rate is 0",
        "100% packet loss",
        "unreachable",
        "timeout",
        "timed out",
        "no route"
    ])

    # SYMBOL BASED DETECTION (VERY IMPORTANT)
    exclam = output.count("!")
    dots   = output.count(".")

    if exclam > 0 and dots == 0:
        success = True
    elif dots > 0 and exclam == 0:
        failure = True

    # FINAL DECISION
    if expect_reachable:
        if success:
            return "PASS", "Ping success"
        elif failure:
            return "FAIL", "Ping failed"
        else:
            return "WARN", "Unknown output"
    else:
        if failure:
            return "PASS", "Correctly unreachable"
        elif success:
            return "FAIL", "Unexpected success"
        else:
            return "WARN", "Unknown output"


# ============================================================
# LOCAL PING CLASSIFIER (FIXED)
# ============================================================

def classify_local_ping(stdout, expect_reachable):
    lower = stdout.lower()

    match = re.search(r"(\d+)%\s+packet loss", lower)
    if not match:
        return "WARN", "Packet loss not found"

    loss = int(match.group(1))

    if expect_reachable:
        if loss == 0:
            return "PASS", "0% loss"
        elif loss < 100:
            return "WARN", f"{loss}% loss"
        else:
            return "FAIL", "100% loss"
    else:
        if loss == 100:
            return "PASS", "Correct unreachable"
        else:
            return "FAIL", f"{loss}% loss (unexpected)"


# ============================================================
# LOCAL PING
# ============================================================

def local_ping(ip):
    result = subprocess.run(
        ["ping", "-c", str(PING_COUNT), ip],
        capture_output=True,
        text=True
    )
    return result.stdout


# ============================================================
# MAIN TEST
# ============================================================

def run_test():
    results = {}

    print(f"\n  Switch IP       : {SWITCH_IP}")
    print(f"  Reachable target: {REACHABLE_IP}")
    print(f"  Unreachable IP  : {UNREACHABLE_IP}")

    # SSH CONNECT
    section("CONNECT — SSH to Switch")

    try:
        client, shell = open_ssh_shell(
            SWITCH_IP, ADMIN_USER, ADMIN_PASS, SSH_PORT
        )
        print(f"✅ SSH connected to {SWITCH_IP}")
    except Exception as e:
        print(f"❌ SSH failed: {e}")
        return False

    # PHASE 1
    section(f"PHASE 1 — Switch → {REACHABLE_IP}")
    step(1, f"ping {REACHABLE_IP}")

    out1 = ssh_cmd(shell, f"ping {REACHABLE_IP}")
    raw_block(out1)

    st1, _ = classify_switch_ping(out1, True)
    results["switch_reachable"] = st1
    result_line("Switch → Server", st1)

    # PHASE 2
    section(f"PHASE 2 — Switch → {UNREACHABLE_IP}")
    step(2, f"ping {UNREACHABLE_IP}")

    out2 = ssh_cmd(shell, f"ping {UNREACHABLE_IP}")
    raw_block(out2)

    st2, _ = classify_switch_ping(out2, False)
    results["switch_unreachable"] = st2
    result_line("Switch → Fake IP", st2)

    client.close()

    # PHASE 3
    section(f"PHASE 3 — Server → {SWITCH_IP}")
    step(3, f"ping {SWITCH_IP}")

    out3 = local_ping(SWITCH_IP)
    raw_block(out3)

    st3, _ = classify_local_ping(out3, True)
    results["server_switch"] = st3
    result_line("Server → Switch", st3)

    # PHASE 4
    section(f"PHASE 4 — Server → {UNREACHABLE_IP}")
    step(4, f"ping {UNREACHABLE_IP}")

    out4 = local_ping(UNREACHABLE_IP)
    raw_block(out4)

    st4, _ = classify_local_ping(out4, False)
    results["server_unreachable"] = st4
    result_line("Server → Fake IP", st4)

    _print_summary(results)

    return all(v == "PASS" for v in results.values())


# ============================================================
# SUMMARY
# ============================================================

def _print_summary(results):
    section("TEST SUMMARY")

    rows = [
        ("Switch → Server", results.get("switch_reachable")),
        ("Switch → Fake IP", results.get("switch_unreachable")),
        ("Server → Switch", results.get("server_switch")),
        ("Server → Fake IP", results.get("server_unreachable")),
    ]

    all_pass = True

    for label, status in rows:
        result_line(label, status)
        if status != "PASS":
            all_pass = False

    print("\n" + "=" * 65)

    if all_pass:
        print("🎉 ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")

    print("=" * 65)


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) >= 4:
        SWITCH_IP  = sys.argv[1]
        ADMIN_USER = sys.argv[2]
        ADMIN_PASS = sys.argv[3]

    if len(sys.argv) >= 5:
        REACHABLE_IP = sys.argv[4]

    if len(sys.argv) >= 6:
        UNREACHABLE_IP = sys.argv[5]

    success = run_test()
    sys.exit(0 if success else 1)
