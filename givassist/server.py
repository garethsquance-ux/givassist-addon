#!/usr/bin/env python3
"""GivAssist addon server — serves wizard + orchestrates GivTCP install."""
import http.server
import json
import os
import time
import urllib.request

PORT = int(os.environ.get("INGRESS_PORT", 8099))
DIR = "/app"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

os.chdir(DIR)

GIVTCP_REPO = "https://github.com/britkat1980/ha-addons"
GIVTCP_SLUG = "533ea71a_givtcp"  # Hashed repo prefix + slug
MOSQUITTO_SLUG = "core_mosquitto"


def supervisor_request(path, method="GET", data=None):
    """Make a request to the HA Supervisor API."""
    if not SUPERVISOR_TOKEN:
        return None, "No supervisor token"
    url = f"http://supervisor/{path}"
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return None, str(e)


def add_repository(repo_url):
    """Add a third-party addon repository."""
    # Get current repos
    data, err = supervisor_request("store")
    if err:
        return False, err

    # Check if already added
    repos = data.get("data", {}).get("repositories", [])
    for r in repos:
        if r.get("url", "") == repo_url or r.get("source", "") == repo_url:
            return True, "Already added"

    # Add it
    _, err = supervisor_request("store/repositories", method="POST", data={"repository": repo_url})
    if err:
        return False, err
    return True, "Added"


def install_addon(slug):
    """Install an addon by slug."""
    # Check if already installed
    data, err = supervisor_request(f"addons/{slug}/info")
    if not err and data:
        state = data.get("data", {}).get("state", "")
        if state == "started":
            return True, "already_running"
        if state == "stopped":
            # Start it
            supervisor_request(f"addons/{slug}/start", method="POST")
            return True, "started"

    # Not installed — install it
    _, err = supervisor_request(f"addons/{slug}/install", method="POST")
    if err:
        return False, err

    # Wait for install
    for _ in range(60):
        time.sleep(2)
        data, _ = supervisor_request(f"addons/{slug}/info")
        if data and data.get("data", {}).get("state"):
            break

    # Start it
    supervisor_request(f"addons/{slug}/start", method="POST")
    return True, "installed"


def get_givtcp_entities():
    """Read GivTCP entities from HA to find discovered inverters."""
    data, err = supervisor_request("core/api/states")
    if err:
        return [], err

    states = data if isinstance(data, list) else []
    # If supervisor wraps in {data: ...}
    if isinstance(data, dict) and "data" in data:
        states = data["data"] if isinstance(data["data"], list) else []

    inverters = []
    seen_serials = set()
    for state in states:
        eid = state.get("entity_id", "")
        if not eid.startswith("sensor.givtcp"):
            continue
        if not eid.endswith("_soc"):
            continue
        # Extract serial: sensor.givtcp_fd2249g811_soc -> fd2249g811
        # or sensor.givtcp2_fd2320f456_soc -> fd2320f456
        parts = eid.replace("sensor.", "").split("_")
        # Remove givtcp prefix (givtcp, givtcp2, givtcp3)
        prefix = parts[0]
        serial_parts = parts[1:-1]  # Remove first (givtcp) and last (soc)
        serial = "_".join(serial_parts).upper()

        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            # Try to find the IP from invertor_ip entity
            ip = ""
            for s2 in states:
                if serial.lower() in s2.get("entity_id", "") and "invertor_ip" in s2.get("entity_id", ""):
                    ip = s2.get("state", "")
                    break
            inverters.append({
                "serial": serial,
                "ip": ip,
                "batterySerial": "",
                "prefix": prefix,
            })

    return inverters, None


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path.endswith("/api/health"):
            self.json_response({"status": "ok", "port": PORT, "has_supervisor": bool(SUPERVISOR_TOKEN)})
            return

        if path.endswith("/api/setup/status"):
            """Check what's installed and what GivTCP has found."""
            result = {"mosquitto": False, "givtcp": False, "inverters": []}

            # Check Mosquitto
            data, _ = supervisor_request(f"addons/{MOSQUITTO_SLUG}/info")
            if data and data.get("data", {}).get("state") == "started":
                result["mosquitto"] = True

            # Check GivTCP
            data, _ = supervisor_request(f"addons/{GIVTCP_SLUG}/info")
            if data:
                state = data.get("data", {}).get("state", "")
                result["givtcp"] = state == "started"
                result["givtcp_state"] = state

            # Get discovered inverters
            if result["givtcp"]:
                inverters, _ = get_givtcp_entities()
                result["inverters"] = inverters

            self.json_response(result)
            return

        if path.endswith("/api/setup/install"):
            """Install Mosquitto + GivTCP repo + GivTCP addon."""
            steps = []

            # Step 1: Mosquitto
            ok, msg = install_addon(MOSQUITTO_SLUG)
            steps.append({"step": "mosquitto", "ok": ok, "msg": msg})

            # Step 2: Add GivTCP repo
            ok, msg = add_repository(GIVTCP_REPO)
            steps.append({"step": "givtcp_repo", "ok": ok, "msg": msg})

            # Step 3: Install GivTCP
            if ok:
                # Need to wait a moment for the repo to be processed
                time.sleep(3)
                ok, msg = install_addon(GIVTCP_SLUG)
                steps.append({"step": "givtcp_install", "ok": ok, "msg": msg})

            self.json_response({"steps": steps, "success": all(s["ok"] for s in steps)})
            return

        # SPA fallback
        translated = self.translate_path(self.path)
        if not os.path.exists(translated) or os.path.isdir(translated):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if path.endswith("/api/setup/install"):
            # Same as GET for simplicity
            self.do_GET()
            return

        self.send_response(404)
        self.end_headers()

    def json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass


print(f"GivAssist Wizard listening on port {PORT}", flush=True)
print(f"Supervisor token: {'present' if SUPERVISOR_TOKEN else 'MISSING'}", flush=True)

# Check current state at startup
if SUPERVISOR_TOKEN:
    print("GivAssist: Checking current setup state...", flush=True)
    data, err = supervisor_request(f"addons/{MOSQUITTO_SLUG}/info")
    mqtt_running = data and data.get("data", {}).get("state") == "started" if data else False
    print(f"  Mosquitto: {'running' if mqtt_running else 'not installed'}", flush=True)

    data, err = supervisor_request(f"addons/{GIVTCP_SLUG}/info")
    givtcp_state = data.get("data", {}).get("state", "not installed") if data else "not installed"
    print(f"  GivTCP: {givtcp_state}", flush=True)

    if givtcp_state == "started":
        inverters, _ = get_givtcp_entities()
        print(f"  Inverters found: {len(inverters)}", flush=True)
        for inv in inverters:
            print(f"    -> {inv['serial']} at {inv.get('ip', '?')}", flush=True)

http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
