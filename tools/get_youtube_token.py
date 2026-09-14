#!/usr/bin/env python3
"""Run this ONCE on your own computer to mint a YouTube refresh token.

    python tools/get_youtube_token.py

It asks for the Client ID and Client Secret you created in Google Cloud,
opens your browser, and prints the refresh token to paste into the repo's
GitHub secrets. Nothing is stored on disk.

Only requirement: `pip install requests`.
"""
from __future__ import annotations

import http.server
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

import requests

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
PORT = 8765
REDIRECT = f"http://localhost:{PORT}/"

_result: dict[str, str] = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in params
        self.wfile.write(
            ("<h2>Tamam, bu sekmeyi kapatabilirsin.</h2>" if ok else
             "<h2>Yetkilendirme iptal edildi.</h2>").encode("utf-8"))
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *args):  # silence the default request logging
        pass


def main() -> int:
    print("Google Cloud -> APIs & Services -> Credentials -> OAuth client ID")
    print("(Application type: Desktop app)\n")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client secret: ").strip()
    if not client_id or not client_secret:
        print("Both values are required.")
        return 1

    csrf = secrets.token_urlsafe(16)
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",          # forces a refresh token every time
        "state": csrf,
    })

    print(f"\nTarayıcı açılıyor. Açılmazsa şu adrese git:\n{auth_url}\n")
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("localhost", PORT), Handler)
    threading.Thread(target=webbrowser.open, args=(auth_url,), daemon=True).start()
    server.serve_forever()
    server.server_close()

    if _result.get("state") != csrf:
        print("State mismatch - başarısız, tekrar dene.")
        return 1
    code = _result.get("code")
    if not code:
        print(f"Yetkilendirme başarısız: {_result.get('error', 'bilinmeyen hata')}")
        return 1

    token = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }, timeout=60)
    if token.status_code != 200:
        print(f"Token alınamadı: {token.status_code} {token.text}")
        return 1

    body = token.json()
    refresh = body.get("refresh_token")
    if not refresh:
        print("Refresh token gelmedi. Google hesabında bu uygulamanın erişimini")
        print("kaldırıp (myaccount.google.com/permissions) tekrar çalıştır.")
        return 1

    # Confirm which channel this token actually controls.
    me = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        headers={"Authorization": f"Bearer {body['access_token']}"},
        params={"part": "snippet", "mine": "true"}, timeout=60).json()
    items = me.get("items", [])
    channel = items[0]["snippet"]["title"] if items else "(kanal okunamadı)"
    channel_id = items[0]["id"] if items else "?"

    print("\n" + "=" * 62)
    print(f"Kanal: {channel}")
    print(f"YT_CHANNEL_ID   {channel_id}")
    print(f"YT_CLIENT_ID    {client_id}")
    print(f"YT_CLIENT_SECRET {client_secret}")
    print(f"YT_REFRESH_TOKEN {refresh}")
    print("=" * 62)
    print("\nBu dördünü GitHub deposunda Settings -> Secrets and variables ->")
    print("Actions altına ekle. (YT_CHANNEL_ID 'Variables' sekmesine.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
