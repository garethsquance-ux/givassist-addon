#!/usr/bin/env python3
"""Simple HTTP server for GivAssist wizard."""
import http.server
import os
import sys

# HA assigns the ingress port dynamically
PORT = int(os.environ.get("INGRESS_PORT", 8099))
DIR = "/app"

os.chdir(DIR)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # SPA fallback - serve index.html for any path that isn't a real file
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = '/index.html'
        return super().do_GET()

    def log_message(self, format, *args):
        pass

print(f"GivAssist Wizard listening on port {PORT}", flush=True)
http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
