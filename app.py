"""Naš jezik: a local Serbo-Croatian course. Flask serves one page; the course API lives in serbocroatian.py."""
import os
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

# stdlib .env loader — skips adding python-dotenv for three lines of parsing.
for line in Path(".env").read_text().splitlines() if Path(".env").exists() else []:
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import setup_support
setup_support.load_saved_key()

import db
import serbocroatian

app = Flask(__name__)
serbocroatian.register(app)
setup_support.register(app)


@app.errorhandler(HTTPException)
def api_http_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": error.description}), error.code
    return error


@app.get("/")
def home():
    return render_template("serbocroatian.html")


@app.get("/cert")
def https_cert_download():
    """The public half of the local HTTPS cert, so an iPhone can install and trust it."""
    from startup import CERT_DIR
    path = os.path.join(CERT_DIR, "cert.pem")
    if not os.path.exists(path):
        return "HTTPS is off (set SONGTOLEARN_HTTPS=1).", 404
    with open(path, "rb") as f:
        return Response(f.read(), mimetype="application/x-x509-ca-cert",
                        headers={"Content-Disposition": "attachment; filename=songtolearn.crt"})


if __name__ == "__main__":
    from startup import server_settings, print_urls
    host, port = server_settings()
    # Warm the Serbian voice in the background so a slow model never blocks startup.
    serbocroatian.sc_piper.start_warmup()

    def _backup_loop():
        while db.is_live():   # never beside a test's temporary database
            try:
                db.backup_daily()
            except Exception as e:   # a failed backup must never take the app down
                print(f"[backup] failed: {e}", flush=True)
            time.sleep(3600)
    threading.Thread(target=_backup_loop, daemon=True).start()
    # Phone browsers only allow the microphone over HTTPS (see /cert).
    https = os.environ.get("SONGTOLEARN_HTTPS") == "1"
    print_urls(host, port, "https" if https else "http")
    ssl_context = None
    if https:
        from startup import https_cert
        ssl_context = https_cert()
    # use_reloader=False: the reloader forks a second process and leaves orphans holding the port.
    app.run(host=host, port=port, debug=False, use_debugger=False, use_reloader=False,
            ssl_context=ssl_context)
