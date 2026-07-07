"""
Web2OS – Developer Portal Server
Serves the public integration website and issues real API keys to
companies that want to integrate with the Web2OS agent running on end
users' computers.

This is the "central" side of Web2OS — in a real deployment it runs on
Web2OS's own servers (e.g. www.web2os.dev) with a proper database, HTTPS,
and account login. Run it locally to develop or preview the site and the
signup flow as-is.

IMPORTANT: issuing a key here does not, by itself, grant a company access
to anyone's computer. A company's website still has to call a specific
end user's local Web2OS agent (127.0.0.1:8765/api/register) with this
key, and that user still has to click Allow on their own screen before
the key is trusted on their device. This server only hands out the key —
it has no reach into any user's computer at all.

DEPLOYMENT NOTE: this stores issued keys in a local JSON file, which is
fine for local development but does NOT persist across deploys/restarts
on platforms like Render unless you attach a persistent disk (Render:
Dashboard -> your service -> Disks) and point _DIR at a path inside it.
For real production use, swap _load()/_save() for a proper database.
"""
import os, json, secrets, datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

_DIR  = os.path.join(os.path.expanduser("~"), ".web2os_portal")
_FILE = os.path.join(_DIR, "companies.json")

_MAX_NAME_LEN  = 80
_MAX_EMAIL_LEN = 120


def _find_website_dir():
    """Look for index.html in the couple of places it's reasonable to be,
    relative to this script — not tied to one exact folder layout.
    Returns the directory path, or None if not found anywhere."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "website"),   # the layout this project ships with
        here,                             # index.html copied next to this script
    ]
    for c in candidates:
        if os.path.isfile(os.path.join(c, "index.html")):
            return c
    return None


_WEBSITE_DIR = _find_website_dir()


def _load() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    os.makedirs(_DIR, exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Needed so the site still works if it's ever opened directly (file://) and
# falls back to calling this server cross-origin, and so any other origin
# testing against a deployed portal isn't silently blocked.
@app.after_request
def _cors(resp):
    resp.headers.update({
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    })
    return resp


# ── Website ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if _WEBSITE_DIR is None:
        return (
            "<h1>Web2OS Portal is running, but can't find index.html</h1>"
            "<p>Expected it at <code>website/index.html</code> next to "
            "<code>portal_server.py</code>, or directly next to it. "
            "Check your folder layout matches the project structure.</p>"
        ), 404
    return send_from_directory(_WEBSITE_DIR, "index.html")


@app.route("/api/developer/signup", methods=["POST", "OPTIONS"])
def signup():
    if request.method == "OPTIONS":
        return jsonify({}), 204

    data  = request.get_json(force=True, silent=True) or {}
    name  = data.get("company_name", "").strip()[:_MAX_NAME_LEN]
    email = data.get("contact_email", "").strip()[:_MAX_EMAIL_LEN]

    if not name or not email:
        return jsonify({"success": False,
                        "message": "Company name and contact email are required"}), 400
    if "@" not in email or " " in email:
        return jsonify({"success": False, "message": "Enter a valid email address"}), 400

    companies = _load()
    api_key = "w2os_" + secrets.token_urlsafe(24)
    companies[api_key] = {
        "company_name":  name,
        "contact_email": email,
        "created_at":    datetime.datetime.now().isoformat(timespec="seconds"),
    }
    _save(companies)

    return jsonify({
        "success": True,
        "api_key": api_key,
        "message": (
            f"Key issued for '{name}'. Put it in your site's Web2OS calls — it "
            f"only starts working for a given visitor once your site asks them "
            f"to connect and they approve it in their own permission popup."
        ),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9000))
    if _WEBSITE_DIR is None:
        print("[Web2OS Portal] WARNING: could not find index.html — the site "
              "route will 404 until website/index.html (or index.html next to "
              "portal_server.py) exists.")
    print(f"[Web2OS Portal] Serving the integration site at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)