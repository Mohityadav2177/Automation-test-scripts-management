import paramiko
import socket
import sys
import time
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# -------------------------------------------------------
# Usage
# -------------------------------------------------------
if len(sys.argv) != 4:
    print("Usage: python3 hfcl_sw_029.py <ip> <username> <password>")
    sys.exit(1)

ip       = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

HTTP_URL  = f"http://{ip}"
HTTPS_URL = f"https://{ip}"

# Suppress SSL warnings
if REQUESTS_AVAILABLE:
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

print("=" * 60)
print("TEST CASE : HFCL-SW-029")
print("TEST NAME : Management")
print("OBJECTIVE : Verify ip http secure-redirect config and unconfig")
print("=" * 60)
print(f"Target    : {ip}:22")
print(f"Username  : {username}")
print(f"HTTP URL  : {HTTP_URL}")
print(f"HTTPS URL : {HTTPS_URL}")
print("=" * 60)

# -------------------------------------------------------
# Step result tracker
# -------------------------------------------------------
step_results = []

def record(step_num, description, passed, note=""):
    status = "PASS" if passed else "FAIL"
    step_results.append((step_num, description, status, note))

# -------------------------------------------------------
# SSH connect
# -------------------------------------------------------
def ssh_connect():
    print(f"\nConnecting to {ip} via SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ip, port=22, username=username, password=password,
            timeout=30, look_for_keys=False, allow_agent=False
        )
    except paramiko.AuthenticationException:
        print("❌ SSH Authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ SSH connection failed: {e}")
        sys.exit(1)

    shell = client.invoke_shell()
    time.sleep(2)
    while shell.recv_ready():
        shell.recv(65535)
    shell.send("terminal length 0\n")
    time.sleep(1)
    while shell.recv_ready():
        shell.recv(65535)

    print("✅ SSH session established\n")
    return client, shell

def send_command(shell, cmd, timeout=20):
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

# -------------------------------------------------------
# HTTP redirect check
# Check if HTTP redirects to HTTPS
# -------------------------------------------------------
def check_http_redirect():
    """
    Access HTTP URL and check if it redirects to HTTPS.
    Returns (redirected: bool, reason: str)
    """
    if REQUESTS_AVAILABLE:
        try:
            # allow_redirects=True so we follow the redirect
            resp = requests.get(
                HTTP_URL,
                verify=False,
                timeout=10,
                allow_redirects=True
            )
            final_url = resp.url
            # Check if final URL is HTTPS
            if final_url.startswith("https://"):
                return True, f"Redirected to {final_url} (HTTP {resp.status_code})"
            else:
                return False, f"No redirect — stayed at {final_url} (HTTP {resp.status_code})"

        except requests.exceptions.ConnectionError:
            return False, "Connection refused — HTTP port is closed"
        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except Exception as e:
            return False, f"Unreachable — {type(e).__name__}"
    else:
        # Fallback: just check if port 80 is open
        try:
            sock = socket.create_connection((ip, 80), timeout=10)
            sock.close()
            return None, "TCP port 80 is OPEN (install requests to check redirect)"
        except Exception:
            return False, "TCP port 80 is CLOSED"

def check_http_no_redirect():
    """
    Access HTTP URL and confirm it does NOT redirect to HTTPS.
    Returns (no_redirect: bool, reason: str)
    """
    if REQUESTS_AVAILABLE:
        try:
            # allow_redirects=False — we want to catch the redirect header directly
            resp = requests.get(
                HTTP_URL,
                verify=False,
                timeout=10,
                allow_redirects=False
            )
            location = resp.headers.get("Location", "")
            if location.startswith("https://") or resp.status_code in (301, 302, 307, 308):
                return False, f"Still redirecting to HTTPS — Location: {location} (HTTP {resp.status_code})"
            else:
                return True, f"No redirect — served HTTP directly (HTTP {resp.status_code})"

        except requests.exceptions.ConnectionError:
            return True, "Connection refused — HTTP redirect is no longer active"
        except requests.exceptions.Timeout:
            return False, "Connection timed out"
        except Exception as e:
            return False, f"Unreachable — {type(e).__name__}"
    else:
        try:
            sock = socket.create_connection((ip, 80), timeout=10)
            sock.close()
            return None, "TCP port 80 OPEN (install requests to verify no-redirect)"
        except Exception:
            return True, "TCP port 80 is CLOSED — redirect not active"

def print_redirect_result(redirected, reason, expect_redirect):
    print("\n--- HTTP REDIRECT RESULT ---")
    print(f"URL      : {HTTP_URL}")
    print(f"Status   : {'REDIRECTS to HTTPS' if redirected else 'NO redirect to HTTPS'}")
    print(f"Details  : {reason}")
    print(f"Expected : {'REDIRECT to HTTPS' if expect_redirect else 'NO redirect to HTTPS'}")
    print("----------------------------")

# -------------------------------------------------------
# STEP 1 — SSH Login
# -------------------------------------------------------
print("=================================")
print("STEP 1: SSH Login")
print("=================================")
client, shell = ssh_connect()
print("✅ STEP 1 PASSED")
record(1, "SSH Login", True)

# -------------------------------------------------------
# STEP 2 — Configure ip http, ip http secure-server, ip http secure-redirect
# -------------------------------------------------------
print("\n=================================")
print("STEP 2: Configure ip http + ip http secure-server + ip http secure-redirect")
print("=================================")

send_command(shell, "configure terminal")

out_http   = send_command(shell, "ip http")
print("Command : ip http")
print("\n--- SWITCH OUTPUT ---")
print(out_http.strip() if out_http.strip() else "(no output)")
print("---------------------")

out_ssl    = send_command(shell, "ip http secure-server")
print("Command : ip http secure-server")
print("\n--- SWITCH OUTPUT ---")
print(out_ssl.strip() if out_ssl.strip() else "(no output)")
print("---------------------")

out_redir  = send_command(shell, "ip http secure-redirect")
print("Command : ip http secure-redirect")
print("\n--- SWITCH OUTPUT ---")
print(out_redir.strip() if out_redir.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = not any(
    "error" in o.lower() or "invalid" in o.lower()
    for o in [out_http, out_ssl, out_redir]
)
print(f"{'✅' if passed else '❌'} STEP 2 {'PASSED' if passed else 'FAILED'} — HTTP, secure-server and secure-redirect configured")
record(2, "Configure ip http + secure-server + secure-redirect", passed)

# -------------------------------------------------------
# STEP 3 — Verify with show running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 3: Verify configuration in running-config")
print("Command : show running-config | include secure")
print("=================================")

output = send_command(shell, "show running-config | include secure", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

has_ssl    = "ip http secure-server"   in output
has_redir  = "ip http secure-redirect" in output
passed     = has_ssl and has_redir
print(f"  secure-server   : {'✅ present' if has_ssl   else '❌ missing'}")
print(f"  secure-redirect : {'✅ present' if has_redir else '❌ missing'}")
print(f"{'✅' if passed else '❌'} STEP 3 {'PASSED' if passed else 'FAILED'} — running-config verified")
record(3, "Verify secure-server + secure-redirect in running-config", passed)

# -------------------------------------------------------
# STEP 4 — Verify show ip http
# -------------------------------------------------------
print("\n=================================")
print("STEP 4: Verify status with show ip http")
print("Command : show ip http")
print("=================================")

output = send_command(shell, "show ip http")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "enabled" in output.lower() or "redirect" in output.lower()
print(f"{'✅' if passed else '⚠️ '} STEP 4 {'PASSED' if passed else 'WARNING'} — HTTP/HTTPS status verified")
record(4, "show ip http — secure-redirect enabled", passed)

# -------------------------------------------------------
# STEP 5 — Check HTTP redirects to HTTPS
# -------------------------------------------------------
print("\n=================================")
print("STEP 5: Check HTTP redirects to HTTPS")
print(f"URL     : {HTTP_URL}")
print("=================================")

time.sleep(2)
redirected, reason = check_http_redirect()
print_redirect_result(redirected, reason, expect_redirect=True)

passed = bool(redirected)
print(f"{'✅' if passed else '❌'} STEP 5 {'PASSED' if passed else 'FAILED'} — HTTP {'redirects to HTTPS' if passed else 'does NOT redirect to HTTPS'}")
record(5, f"HTTP redirects to HTTPS (expect REDIRECT)", passed, reason)

# -------------------------------------------------------
# STEP 6 — Remove ip http secure-redirect
# -------------------------------------------------------
print("\n=================================")
print("STEP 6: Remove secure-redirect")
print("Command : no ip http secure-redirect")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, "no ip http secure-redirect")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 6 {'PASSED' if passed else 'FAILED'} — no ip http secure-redirect configured")
record(6, "Remove ip http secure-redirect", passed)

# -------------------------------------------------------
# STEP 7 — Verify removed from running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 7: Verify secure-redirect removed from running-config")
print("Command : show running-config | include secure")
print("=================================")

output = send_command(shell, "show running-config | include secure", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output — redirect entry removed ✅)")
print("---------------------")

passed = "ip http secure-redirect" not in output
print(f"{'✅' if passed else '❌'} STEP 7 {'PASSED' if passed else 'FAILED'} — secure-redirect {'absent' if passed else 'still present'} in running-config")
record(7, "Verify secure-redirect removed from running-config", passed)

# -------------------------------------------------------
# STEP 8 — Check HTTP does NOT redirect to HTTPS
# -------------------------------------------------------
print("\n=================================")
print("STEP 8: Check HTTP does NOT redirect to HTTPS")
print(f"URL     : {HTTP_URL}")
print("=================================")

time.sleep(3)
no_redirect, reason = check_http_no_redirect()
print_redirect_result(not no_redirect, reason, expect_redirect=False)

passed = bool(no_redirect)
print(f"{'✅' if passed else '❌'} STEP 8 {'PASSED' if passed else 'FAILED'} — HTTP {'no longer redirects' if passed else 'still redirecting'} to HTTPS")
record(8, "HTTP does NOT redirect to HTTPS (expect NO REDIRECT)", passed, reason)

# -------------------------------------------------------
# STEP 9 — Verify show ip http (redirect disabled)
# -------------------------------------------------------
print("\n=================================")
print("STEP 9: Verify status with show ip http (redirect should be disabled)")
print("Command : show ip http")
print("=================================")

output = send_command(shell, "show ip http")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "redirect" not in output.lower() or "disabled" in output.lower()
print(f"{'✅' if passed else '⚠️ '} STEP 9 {'PASSED' if passed else 'WARNING'} — secure-redirect {'disabled' if passed else 'status unclear'}")
record(9, "show ip http — secure-redirect disabled", passed)

# -------------------------------------------------------
# STEP 10 — Restore ip http secure-redirect
# -------------------------------------------------------
print("\n=================================")
print("STEP 10: Restore secure-redirect configuration")
print("Command : ip http secure-redirect")
print("=================================")

send_command(shell, "configure terminal")
output = send_command(shell, "ip http secure-redirect")

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

send_command(shell, "end")

passed = "error" not in output.lower() and "invalid" not in output.lower()
print(f"{'✅' if passed else '❌'} STEP 10 {'PASSED' if passed else 'FAILED'} — ip http secure-redirect restored")
record(10, "Restore ip http secure-redirect", passed)

# -------------------------------------------------------
# STEP 11 — Verify restored in running-config
# -------------------------------------------------------
print("\n=================================")
print("STEP 11: Verify secure-redirect restored in running-config")
print("Command : show running-config | include secure")
print("=================================")

output = send_command(shell, "show running-config | include secure", timeout=30)

print("\n--- SWITCH OUTPUT ---")
print(output.strip() if output.strip() else "(no output)")
print("---------------------")

passed = "ip http secure-redirect" in output
print(f"{'✅' if passed else '⚠️ '} STEP 11 {'PASSED' if passed else 'WARNING'} — secure-redirect {'restored' if passed else 'not found'} in running-config")
record(11, "Verify secure-redirect restored in running-config", passed)

# -------------------------------------------------------
# Close connection
# -------------------------------------------------------
try:
    client.close()
except Exception:
    pass

# -------------------------------------------------------
# FINAL SUMMARY
# -------------------------------------------------------
print("\n")
print("=" * 60)
print("TEST CASE  : HFCL-SW-029")
print("FINAL STEP SUMMARY")
print("=" * 60)
print(f"{'STEP':<6} {'DESCRIPTION':<48} {'RESULT'}")
print("-" * 60)

all_passed = True
for step_num, desc, status, note in step_results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"{icon} {str(step_num):<4} {desc:<48} {status}")
    if note:
        print(f"       {'':4} Note: {note}")
    if status == "FAIL":
        all_passed = False

print("-" * 60)
print(f"\nOVERALL RESULT : {'✅ PASS' if all_passed else '❌ FAIL'}")
print("=" * 60)
