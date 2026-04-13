#!/usr/bin/env python3
"""GivAssist addon server — serves wizard + scan API via HA Supervisor."""
import http.server
import json
import os
import urllib.request

PORT = int(os.environ.get("INGRESS_PORT", 8099))
DIR = "/app"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

os.chdir(DIR)


def scan_via_supervisor():
    """Use HA Supervisor API to scan for inverters.
    The Supervisor runs on the host network and can reach local devices."""
    results = {"success": False, "inverters": [], "method": "supervisor", "subnet": "unknown"}

    if not SUPERVISOR_TOKEN:
        results["error"] = "No supervisor token — not running as addon"
        return results

    try:
        # Get network info from Supervisor
        req = urllib.request.Request(
            "http://supervisor/network/info",
            headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())

        # Extract the local IP and subnet
        interfaces = data.get("data", {}).get("interfaces", [])
        local_ip = None
        for iface in interfaces:
            if iface.get("enabled") and iface.get("ipv4", {}).get("address"):
                addrs = iface["ipv4"]["address"]
                if addrs:
                    local_ip = addrs[0].split("/")[0]
                    break

        if not local_ip:
            results["error"] = "Could not determine local IP"
            return results

        parts = local_ip.split(".")
        subnet = ".".join(parts[:3])
        results["subnet"] = subnet
        results["localIp"] = local_ip

        # Now scan port 8899 using the Supervisor's network access
        # We'll use HA's API to create a temporary shell command
        import socket
        import threading

        found = []
        lock = threading.Lock()

        def check_ip(ip):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex((ip, 8899))
                s.close()
                if result == 0:
                    # Try to read serial via Modbus
                    serial = read_modbus(ip)
                    with lock:
                        found.append({
                            "ip": ip,
                            "serial": serial.upper() if serial else "",
                            "batterySerial": "",
                            "model": "GivEnergy Inverter",
                            "method": "network_scan",
                        })
            except Exception:
                pass

        threads = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            t = threading.Thread(target=check_ip, args=(ip,))
            t.start()
            threads.append(t)
            if len(threads) >= 50:
                for t in threads:
                    t.join(timeout=2)
                threads = [t for t in threads if t.is_alive()]

        for t in threads:
            t.join(timeout=2)

        results["inverters"] = found
        results["success"] = len(found) > 0
        results["scannedCount"] = 254

    except Exception as e:
        results["error"] = str(e)

    return results


def read_modbus(ip, port=8899, timeout=2.0):
    """Try to read inverter serial via Modbus TCP."""
    try:
        import struct
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        request = struct.pack(">HHHBBHH", 1, 0, 6, 0, 3, 0, 6)
        s.send(request)
        response = s.recv(256)
        s.close()
        if len(response) > 9:
            data = response[9:]
            serial = ""
            for i in range(0, min(len(data), 12), 2):
                if i + 1 < len(data):
                    c1, c2 = data[i], data[i + 1]
                    if 32 <= c1 < 127: serial += chr(c1)
                    if 32 <= c2 < 127: serial += chr(c2)
            return serial.strip() if serial.strip() else None
        return None
    except Exception:
        return None


import socket  # Need this at module level for read_modbus

# Pre-scan at startup
print("GivAssist: Scanning network for inverters...", flush=True)
CACHED_SCAN = scan_via_supervisor()
print(f"GivAssist: Subnet {CACHED_SCAN.get('subnet', '?')}, found {len(CACHED_SCAN.get('inverters', []))} inverter(s)", flush=True)
for inv in CACHED_SCAN.get("inverters", []):
    print(f"  -> {inv['ip']} (serial: {inv.get('serial', '?')})", flush=True)
if CACHED_SCAN.get("error"):
    print(f"GivAssist: Scan note: {CACHED_SCAN['error']}", flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path.endswith("/api/scan"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(CACHED_SCAN).encode())
            return

        if path.endswith("/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            info = {
                "status": "ok",
                "port": PORT,
                "subnet": CACHED_SCAN.get("subnet"),
                "inverters_found": len(CACHED_SCAN.get("inverters", [])),
                "has_supervisor": bool(SUPERVISOR_TOKEN),
            }
            self.wfile.write(json.dumps(info).encode())
            return

        # SPA fallback
        translated = self.translate_path(self.path)
        if not os.path.exists(translated) or os.path.isdir(translated):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass


print(f"GivAssist Wizard listening on port {PORT}", flush=True)
http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
