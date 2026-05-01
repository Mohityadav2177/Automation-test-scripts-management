#!/usr/bin/env python3

"""
TEST-HFCL-SW-TFTP-01  —  Management: TFTP Backup & Restore Verification
======================================================================

Test Name      : Management

Test Objective :
Verify configuration backup and restore by transferring configuration
file from switch to TFTP server and restoring it back to the device.

Test Configuration:
  TFTP Server IP : 192.168.180.69
  File Name      : startup-config

Procedure:

  PHASE 1 : Copy configuration from switch → TFTP server
            switch# copy running-config tftp://192.168.180.69/startup-config
            Expected: File successfully transferred to TFTP server

  PHASE 2 : Copy configuration from TFTP server → switch
            switch# copy tftp://192.168.180.69/startup-config flash:startup-config
            Expected: File successfully copied to flash

  PHASE 3 : Verify file in flash
            switch# dir
            Expected: startup-config file should be present

  PHASE 4 : Negative test (wrong TFTP details)
            switch# copy running-config tftp://192.168.180.99/startup-config
            Expected: Copy operation should fail

Expected Result:
  - Copy operation should succeed with correct TFTP details ✅
  - Copy operation should fail with incorrect details ❌

Usage:
  python3 tftp_test.py <switch_ip> <admin_user> <admin_pass>
  python3 tftp_test.py 192.168.180.110 admin admin
"""

import sys
import time
import paramiko


# ============================================================
# CONFIGURATION
# ============================================================

SWITCH_IP   = "192.168.180.110"
ADMIN_USER  = "admin"
ADMIN_PASS  = "admin"

TFTP_SERVER = "192.168.180.69"
WRONG_TFTP  = "192.168.180.99"
FILE_NAME   = "startup-config"


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

def result(label, status):
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon}  {label:<55} {status}")

def raw(output):
    for line in output.splitlines():
        if line.strip():
            print(f"  |  {line.strip()}")


# ============================================================
# SSH
# ============================================================

def open_ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SWITCH_IP, username=ADMIN_USER, password=ADMIN_PASS)
    shell = client.invoke_shell()
    time.sleep(1)
    return client, shell


def send_cmd(shell, cmd, wait=5):
    shell.send(cmd + "\n")
    time.sleep(wait)
    out = ""
    while shell.recv_ready():
        out += shell.recv(4096).decode(errors="ignore")
    return out


# ============================================================
# MAIN TEST
# ============================================================

def run_test():

    results = {}

    section("CONNECT — SSH TO SWITCH")
    client, shell = open_ssh()
    print("✅ Connected to switch")

    # ================= PHASE 1 =================
    section("PHASE 1 — Switch → TFTP Server")

    step(1, "Copy running-config to TFTP server")

    cmd1 = f"copy running-config tftp://{TFTP_SERVER}/{FILE_NAME}"
    out1 = send_cmd(shell, cmd1, 6)

    raw(out1)

    if "saving" in out1.lower() or "bytes" in out1.lower():
        results["backup"] = "PASS"
    else:
        results["backup"] = "FAIL"

    result("Backup to TFTP server", results["backup"])


    # ================= PHASE 2 =================
    section("PHASE 2 — TFTP Server → Switch")

    step(2, "Copy file from TFTP to flash")

    cmd2 = f"copy tftp://{TFTP_SERVER}/{FILE_NAME} flash:{FILE_NAME}"
    out2 = send_cmd(shell, cmd2, 6)

    raw(out2)

    if "saving" in out2.lower():
        results["restore"] = "PASS"
    else:
        results["restore"] = "FAIL"

    result("Restore from TFTP", results["restore"])


    # ================= PHASE 3 =================
    section("PHASE 3 — Verify File in Flash")

    step(3, "dir")

    out3 = send_cmd(shell, "dir", 4)
    raw(out3)

    if FILE_NAME in out3:
        results["verify"] = "PASS"
    else:
        results["verify"] = "FAIL"

    result("Verify startup-config present", results["verify"])


    # ================= PHASE 4 =================
    section("PHASE 4 — Negative Test")

    step(4, "Copy using wrong TFTP IP")

    cmd4 = f"copy running-config tftp://{WRONG_TFTP}/{FILE_NAME}"
    out4 = send_cmd(shell, cmd4, 60)

    raw(out4)

    if "error" in out4.lower() or "fail" in out4.lower() or "timeout" in out4.lower():
        results["negative"] = "PASS"
    else:
        results["negative"] = "FAIL"

    result("Negative test (wrong TFTP)", results["negative"])


    client.close()

    # ================= SUMMARY =================
    section("TEST SUMMARY")

    for k, v in results.items():
        result(k, v)

    if all(v == "PASS" for v in results.values()):
        print("\n🎉 ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) >= 4:
        SWITCH_IP  = sys.argv[1]
        ADMIN_USER = sys.argv[2]
        ADMIN_PASS = sys.argv[3]

    run_test()
