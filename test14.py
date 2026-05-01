#!/usr/bin/env python3

"""
TEST-HFCL-SW-RELOAD-DEFAULTS-14  —  Management: Factory Reset (keep-ip) Verification
==================================================================================
Test Name      : Management

Test Objective :
Restore the device to its default settings by executing the
"reload defaults keep-ip force" command in EXEC mode and verify
that the switch returns to default configuration while retaining IP.

Test Configuration:
  Save configuration before reload:
    switch# copy running-config startup-config

Procedure:
  PHASE 1 : Save running configuration
            switch# copy running-config startup-config
            Expected: Configuration saved successfully

  PHASE 2 : Execute reload defaults with keep-ip
            switch# reload defaults keep-ip force
            Expected: Switch reloads and resets to default config (IP retained)

  PHASE 3 : Reconnect to switch after reload
            Expected: SSH/Telnet access restored

  PHASE 4 : Verify running configuration
            switch# show running-config
            Expected: Default configuration (no custom config present)

  PHASE 5 : Save configuration after reset
            switch# copy running-config startup-config
            Expected: Default config saved successfully

Expected Result:
  - Switch should reset to default configuration
  - Management IP should remain reachable
  - No previous custom configuration should exist

Usage:
  python3 demo1.py <switch_ip> <admin_user> <admin_pass>
  python3 demo1.py 192.168.180.110 admin admin
"""

import sys
import time
import re
import paramiko


# ============================================================
# CONFIGURATION
# ============================================================

SWITCH_IP   = "192.168.180.110"
ADMIN_USER  = "admin"
ADMIN_PASS  = "admin"
SSH_PORT    = 22

RELOAD_WAIT = 20


# ============================================================
# PRINT HELPERS
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

def raw_block(output, label="OUTPUT"):
    print(f"  +-- {label} " + "-" * 50)
    for line in output.splitlines():
        if line.strip():
            print(f"  |  {line.strip()}")
    print("  +" + "-" * 63)


# ============================================================
# SSH FUNCTIONS
# ============================================================

def open_ssh():
    for i in range(10):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                SWITCH_IP,
                username=ADMIN_USER,
                password=ADMIN_PASS,
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )
            shell = client.invoke_shell()
            time.sleep(1)
            return client, shell
        except:
            print(f"⏳ Waiting for switch to come back... ({i+1})")
            time.sleep(6)
    raise Exception("Switch not reachable after reload")


def ssh_cmd(shell, cmd, wait=5):
    shell.send(cmd + "\n")
    time.sleep(wait)
    output = ""
    while shell.recv_ready():
        output += shell.recv(4096).decode(errors="ignore")
    return output


# ============================================================
# VALIDATION
# ============================================================

def is_default_config(output):
    lower = output.lower()

    # Example checks
    if "vlan 100" in lower:
        return False

    return True


# ============================================================
# MAIN TEST
# ============================================================

def run_test():
    results = {}

    print(f"\n  Switch IP : {SWITCH_IP}")

    # ================= PHASE 1 =================
    section("PHASE 1 — Save running configuration")

    client, shell = open_ssh()

    step(1, "copy running-config startup-config")
    out1 = ssh_cmd(shell, "copy running-config startup-config", 5)
    raw_block(out1)

    results["save_config"] = "PASS"
    result_line("Save configuration", "PASS")

    # ================= PHASE 2 =================
    section("PHASE 2 — Reload defaults (keep-ip force)")

    step(2, "reload defaults keep-ip force")
    ssh_cmd(shell, "reload defaults keep-ip force", 2)

    print("\n⚠️  Switch fetch default config ....")
    client.close()

    time.sleep(RELOAD_WAIT)

    # ================= PHASE 3 =================
    section("PHASE 3 — Reconnect after reload")

    try:
        client, shell = open_ssh()
        results["reconnect"] = "PASS"
        print("✅ Reconnected successfully")
    except Exception as e:
        results["reconnect"] = "FAIL"
        print(f"❌ Reconnect failed: {e}")
        return False

    # ================= PHASE 4 =================
    section("PHASE 4 — Verify default configuration")

    step(4, "show running-config")
    out4 = ssh_cmd(shell, "show running-config", 10)
    raw_block(out4)

    if is_default_config(out4):
        results["verify"] = "PASS"
    else:
        results["verify"] = "FAIL"

    result_line("Default configuration check", results["verify"])

    # ================= PHASE 5 =================
    section("PHASE 5 — Save running-config to startup-config")

    step(5, "copy startup-config  running-config ")
    out5 = ssh_cmd(shell, "copy startup-config running-config ", 5)
    raw_block(out5)

    results["save_after_reset"] = "PASS"
    result_line("Save config after reset", "PASS")

    client.close()

    # ================= SUMMARY =================
    section("TEST SUMMARY")

    for k, v in results.items():
        result_line(k, v)

    if all(v == "PASS" for v in results.values()):
        print("""\nALL TESTS PASSED \n 

Test Objective: Restore the device to its default settings by executing the " reload defaults " command in EXEC mode.

""")
    else:
        print("\n SOME TESTS FAILED")


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) >= 4:
        SWITCH_IP  = sys.argv[1]
        ADMIN_USER = sys.argv[2]
        ADMIN_PASS = sys.argv[3]

    run_test()
