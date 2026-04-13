#!/usr/bin/env python3
"""Simple HTTP server for GivAssist wizard."""
import http.server
import os

PORT = 8099
DIR = "/app"

os.chdir(DIR)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # SPA fallback - serve index.html for any non-file path
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = '/index.html'
        return super().do_GET()

    def log_message(self, format, *args):
        pass  # Suppress logs

print(f"GivAssist Wizard running on port {PORT}")
http.server.HTTPServer(("", PORT), Handler).serve_forever()
