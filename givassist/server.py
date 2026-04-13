#!/usr/bin/env python3
"""GivAssist addon server — serves wizard + provides network scan API."""
import http.server
import json
import os
import socket
import threading
import struct

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


def scan_port(ip, port=8899, timeout=1.0):
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
    """Try to read the inverter serial via Modbus TCP register."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))

        # Modbus TCP: read holding registers starting at register 0, count 6
        # Transaction ID (2) + Protocol (2) + Length (2) + Unit (1) + Function (1) + Start (2) + Count (2)
        request = struct.pack(">HHHBBHH", 1, 0, 6, 0, 3, 0, 6)
        s.send(request)
        response = s.recv(256)
        s.close()

        if len(response) > 9:
            # Parse the register data as ASCII characters
            data = response[9:]
            serial = ""
            for i in range(0, min(len(data), 12), 2):
                if i + 1 < len(data):
                    c1 = data[i]
                    c2 = data[i + 1]
                    if 32 <= c1 < 127:
                        serial += chr(c1)
                    if 32 <= c2 < 127:
                        serial += chr(c2)
            return serial.strip() if serial.strip() else None
        return None
    except Exception:
        return None


def scan_network():
    """Scan the local network for GivEnergy inverters on port 8899."""
    subnet, local_ip = get_local_subnet()
    found = []
    scanned = 0

    # Scan common IP ranges first (faster discovery)
    ips_to_scan = []
    for i in range(1, 255):
        ips_to_scan.append(f"{subnet}.{i}")

    def check_ip(ip):
        nonlocal scanned
        if scan_port(ip, 8899, timeout=0.5):
            serial = read_modbus_serial(ip) or ""
            found.append({
                "ip": ip,
                "serial": serial.upper() if serial else "",
                "batterySerial": "",
                "model": "GivEnergy Inverter",
                "method": "network_scan",
            })
        scanned += 1

    # Scan in parallel threads (fast)
    threads = []
    for ip in ips_to_scan:
        t = threading.Thread(target=check_ip, args=(ip,))
        t.start()
        threads.append(t)
        # Limit concurrent threads
        if len(threads) >= 50:
            for t in threads:
                t.join()
            threads = []

    for t in threads:
        t.join()

    return {
        "success": len(found) > 0,
        "inverters": found,
        "subnet": subnet,
        "localIp": local_ip,
        "scannedCount": scanned,
        "method": "network_scan",
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # API endpoint: scan network for inverters
        if self.path == "/api/scan" or self.path.startswith("/api/scan?"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            result = scan_network()
            self.wfile.write(json.dumps(result).encode())
            return

        # API endpoint: health check
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
            return

        # SPA fallback
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass


print(f"GivAssist Wizard listening on port {PORT}", flush=True)
print(f"Network scan available at /api/scan", flush=True)
http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
