#!/usr/bin/env python3
"""GivAssist addon server — serves wizard + provides network scan API."""
import http.server
import json
import os
import socket
import threading

PORT = int(os.environ.get("INGRESS_PORT", 8099))
DIR = "/app"

os.chdir(DIR)


def get_local_subnet():
    """Get the local IP and derive the subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        return ".".join(parts[:3]), local_ip
    except Exception:
        return "192.168.1", "unknown"


def scan_port(ip, port=8899, timeout=0.5):
    """Check if a port is open on an IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        s.close()
        return result == 0
    except Exception:
        return False


def read_modbus_serial(ip, port=8899, timeout=3.0):
    """Try to read the inverter serial via Modbus TCP."""
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


def scan_network():
    """Scan the local network for GivEnergy inverters on port 8899."""
    subnet, local_ip = get_local_subnet()
    found = []
    lock = threading.Lock()

    def check_ip(ip):
        if scan_port(ip, 8899, timeout=0.5):
            serial = read_modbus_serial(ip) or ""
            with lock:
                found.append({
                    "ip": ip,
                    "serial": serial.upper() if serial else "",
                    "batterySerial": "",
                    "model": "GivEnergy Inverter",
                    "method": "network_scan",
                })

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

    return {
        "success": len(found) > 0,
        "inverters": found,
        "subnet": subnet,
        "localIp": local_ip,
        "scannedCount": 254,
        "method": "network_scan",
    }


# Run scan at startup and cache the result
print(f"GivAssist: Pre-scanning network...", flush=True)
CACHED_SCAN = scan_network()
print(f"GivAssist: Found {len(CACHED_SCAN['inverters'])} inverter(s) on {CACHED_SCAN['subnet']}.x", flush=True)
for inv in CACHED_SCAN['inverters']:
    print(f"  → {inv['ip']} (serial: {inv['serial'] or 'unknown'})", flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Strip ingress prefix if present
        path = self.path.split("?")[0]
        # Handle /api/scan anywhere in the path
        if path.endswith("/api/scan") or path == "/api/scan":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # Return cached result or rescan
            if "rescan" in self.path:
                global CACHED_SCAN
                CACHED_SCAN = scan_network()
            self.wfile.write(json.dumps(CACHED_SCAN).encode())
            return

        if path.endswith("/api/health") or path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT, "subnet": CACHED_SCAN.get("subnet"), "inverters_found": len(CACHED_SCAN.get("inverters", []))}).encode())
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
