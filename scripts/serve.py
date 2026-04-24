"""Tiny static file server that sets its own cwd — avoids sandbox getcwd() issues."""
import http.server
import os
import socketserver
import sys

WEB_DIR = "/Users/michelle/Desktop/duetlearn/web"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173

os.chdir(WEB_DIR)
print(f"📡 Serving {WEB_DIR} on http://localhost:{PORT}", flush=True)
with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    httpd.serve_forever()
