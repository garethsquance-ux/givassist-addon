#!/usr/bin/env python3
"""
GivAssist Addon Server v2
Orchestrates the complete setup: Mosquitto → GivTCP → Discovery → Ready.
The user never needs to configure GivTCP or Mosquitto manually.
"""
import http.server
import json
import os
import time
import urllib.request
import urllib.error

PORT = int(os.environ.get("INGRESS_PORT", 8099))
DIR = "/app"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

os.chdir(DIR)

MOSQUITTO_SLUG = "core_mosquitto"
GIVTCP_REPO = "https://github.com/britkat1980/ha-addons"
GIVTCP_SLUG = "533ea71a_givtcp"


def sup(path, method="GET", data=None):
    """Call the Supervisor API."""
    if not SUPERVISOR_TOKEN:
        return None, "No supervisor token"
    url = f"http://supervisor/{path}"
    hdrs = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        return result, None
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode()
        except: pass
        return None, f"HTTP {e.code}: {body[:200]}"
    except Exception as e:
        return None, str(e)


def addon_state(slug):
    """Get addon state: 'started', 'stopped', 'not_installed'."""
    data, err = sup(f"addons/{slug}/info")
    if err or not data:
        return "not_installed"
    return data.get("data", {}).get("state", "unknown")


def install_and_start(slug, options=None):
    """Install addon, set options, start it. Returns (success, message)."""
    state = addon_state(slug)

    if state == "started":
        return True, "already_running"

    if state == "not_installed":
        print(f"  Installing {slug}...", flush=True)
        _, err = sup(f"addons/{slug}/install", method="POST")
        if err:
            return False, f"Install failed: {err}"
        # Wait for install to complete
        for _ in range(60):
            time.sleep(2)
            if addon_state(slug) != "not_installed":
                break
        print(f"  {slug} installed", flush=True)

    # Set options if provided
    if options:
        print(f"  Configuring {slug}...", flush=True)
        _, err = sup(f"addons/{slug}/options", method="POST", data={"options": options})
        if err:
            print(f"  Warning: options failed: {err}", flush=True)

    # Start
    if addon_state(slug) != "started":
        print(f"  Starting {slug}...", flush=True)
        _, err = sup(f"addons/{slug}/start", method="POST")
        if err:
            return False, f"Start failed: {err}"
        # Wait for start
        for _ in range(30):
            time.sleep(2)
            if addon_state(slug) == "started":
                break

    final = addon_state(slug)
    return final == "started", final


def add_repo(url):
    """Add addon repository if not already present."""
    data, err = sup("store")
    if err:
        # Try alternate endpoint
        data, err = sup("store/repositories")
    if err:
        return False, err

    # Check if already present
    repos = []
    if isinstance(data, dict):
        d = data.get("data", data)
        if isinstance(d, dict):
            repos = d.get("repositories", [])
        elif isinstance(d, list):
            repos = d

    for r in repos:
        src = r.get("source", r.get("url", "")) if isinstance(r, dict) else str(r)
        if url in src:
            return True, "already_added"

    _, err = sup("store/repositories", method="POST", data={"repository": url})
    if err:
        return False, err

    # Wait for store to refresh
    time.sleep(5)
    return True, "added"


def get_inverter_entities():
    """Read GivTCP entities from HA to find discovered inverters."""
    data, err = sup("core/api/states")
    if err:
        return []

    states = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []

    inverters = []
    seen = set()

    for state in states:
        eid = state.get("entity_id", "")
        if not eid.startswith("sensor.givtcp") or not eid.endswith("_soc"):
            continue

        # sensor.givtcp_fd2249g811_soc → fd2249g811
        # sensor.givtcp2_fd2320f456_soc → fd2320f456
        parts = eid.replace("sensor.", "").rsplit("_soc", 1)[0]
        # Remove givtcp/givtcp2/givtcp3 prefix
        if parts.startswith("givtcp3_"):
            serial = parts[8:]
            prefix = "givtcp3"
        elif parts.startswith("givtcp2_"):
            serial = parts[8:]
            prefix = "givtcp2"
        elif parts.startswith("givtcp_"):
            serial = parts[7:]
            prefix = "givtcp"
        else:
            continue

        serial = serial.upper()
        if serial in seen:
            continue
        seen.add(serial)

        # Find IP
        ip = ""
        for s2 in states:
            eid2 = s2.get("entity_id", "")
            if serial.lower() in eid2 and ("invertor_ip" in eid2 or "ip_address" in eid2):
                ip = s2.get("state", "")
                break

        soc = state.get("state", "?")
        inverters.append({
            "serial": serial,
            "ip": ip,
            "soc": soc,
            "prefix": prefix,
            "batterySerial": "",
            "model": "GivEnergy Inverter",
        })

    return inverters


def full_setup():
    """Run the complete setup: Mosquitto → GivTCP repo → GivTCP → wait for entities."""
    steps = []

    # 1. Mosquitto
    print("Step 1: Mosquitto...", flush=True)
    ok, msg = install_and_start(MOSQUITTO_SLUG)
    steps.append({"step": "mosquitto", "ok": ok, "msg": msg})
    if not ok:
        return {"success": False, "steps": steps, "error": "Mosquitto failed"}

    # 2. Add GivTCP repo
    print("Step 2: GivTCP repository...", flush=True)
    ok, msg = add_repo(GIVTCP_REPO)
    steps.append({"step": "givtcp_repo", "ok": ok, "msg": msg})
    if not ok:
        return {"success": False, "steps": steps, "error": "GivTCP repo failed"}

    # 3. Install and configure GivTCP
    print("Step 3: GivTCP...", flush=True)
    givtcp_options = {
        "self_run": True,
        "MQTT_Address": "core-mosquitto",
        "MQTT_Port": "1883",
        "MQTT_Topic": "GivEnergy",
        "Log_Level": "Info",
    }
    ok, msg = install_and_start(GIVTCP_SLUG, options=givtcp_options)
    steps.append({"step": "givtcp", "ok": ok, "msg": msg})
    if not ok:
        return {"success": False, "steps": steps, "error": "GivTCP failed"}

    # 4. Wait for inverter entities
    print("Step 4: Waiting for inverter discovery...", flush=True)
    inverters = []
    for i in range(30):
        time.sleep(5)
        inverters = get_inverter_entities()
        if inverters:
            print(f"  Found {len(inverters)} inverter(s)!", flush=True)
            for inv in inverters:
                print(f"    → {inv['serial']} at {inv.get('ip', '?')} (SOC: {inv.get('soc', '?')}%)", flush=True)
            break
        if i % 6 == 0:
            print(f"  Still waiting... ({i*5}s)", flush=True)

    steps.append({"step": "discovery", "ok": len(inverters) > 0, "msg": f"Found {len(inverters)} inverters"})

    return {
        "success": len(inverters) > 0,
        "steps": steps,
        "inverters": inverters,
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path.endswith("/api/health"):
            self.json_response({
                "status": "ok",
                "port": PORT,
                "has_supervisor": bool(SUPERVISOR_TOKEN),
            })
            return

        if path.endswith("/api/setup/status"):
            result = {
                "mosquitto": addon_state(MOSQUITTO_SLUG) == "started",
                "givtcp": addon_state(GIVTCP_SLUG) == "started",
                "givtcp_state": addon_state(GIVTCP_SLUG),
                "inverters": get_inverter_entities() if addon_state(GIVTCP_SLUG) == "started" else [],
            }
            self.json_response(result)
            return

        if path.endswith("/api/setup/run"):
            result = full_setup()
            self.json_response(result)
            return

        if path.endswith("/api/setup/inverters"):
            self.json_response({"inverters": get_inverter_entities()})
            return

        # SPA fallback
        translated = self.translate_path(self.path)
        if not os.path.exists(translated) or os.path.isdir(translated):
            self.path = "/index.html"
        return super().do_GET()

    def json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass


# Startup
print(f"GivAssist v2 starting on port {PORT}", flush=True)
print(f"Supervisor: {'connected' if SUPERVISOR_TOKEN else 'NOT AVAILABLE'}", flush=True)

if SUPERVISOR_TOKEN:
    try:
        m = addon_state(MOSQUITTO_SLUG)
        g = addon_state(GIVTCP_SLUG)
        print(f"Mosquitto: {m}", flush=True)
        print(f"GivTCP: {g}", flush=True)
        if g == "started":
            invs = get_inverter_entities()
            print(f"Inverters: {len(invs)} found", flush=True)
    except Exception as e:
        print(f"Startup check: {e}", flush=True)

print("Server starting...", flush=True)

http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
