import json
import os
import secrets
import sqlite3
from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request, session, url_for, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "main_database.db")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

CLIENT_ID = os.environ.get("CLIENT_ID")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
OAUTH_EXCHANGE_URL = os.environ.get("OAUTH_EXCHANGE_URL")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_API_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Connexion Discord</title>
  <style>
    :root {
      --panel: rgba(255, 255, 255, 0.07);
      --line: rgba(255, 255, 255, 0.12);
      --text: #f3f6ff;
      --muted: #aeb8d8;
      --accent: #5865f2;
      --danger: #ffb4a0;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(88, 101, 242, 0.18), transparent 26%),
        linear-gradient(135deg, #0a1020 0%, #121a2f 45%, #11182c 100%);
      padding: 20px;
    }
    .card {
      width: min(100%, 520px);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }
    .eyebrow {
      margin: 0 0 10px;
      font-size: 0.75rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }
    h1 {
      margin: 0 0 10px;
      font-size: 2rem;
      line-height: 1.05;
    }
    .muted {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .alert {
      margin-top: 18px;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255, 180, 160, 0.12);
      border: 1px solid rgba(255, 180, 160, 0.2);
      color: var(--danger);
      line-height: 1.5;
      word-break: break-word;
    }
    .actions {
      display: flex;
      gap: 12px;
      margin-top: 22px;
      flex-wrap: wrap;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 12px 18px;
      border-radius: 14px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      font-weight: 700;
      border: 0;
      cursor: pointer;
    }
    .btn.secondary {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--line);
      color: var(--text);
    }
    .info {
      margin-top: 22px;
      padding: 14px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--line);
    }
    .info strong {
      display: block;
      margin-bottom: 8px;
    }
    code {
      display: inline-block;
      margin-top: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      color: var(--text);
      word-break: break-all;
    }
  </style>
</head>
<body>
  <main class="card">
    <p class="eyebrow">Discord OAuth</p>
    <h1>Connexion au panel</h1>
    <p class="muted">Connecte-toi avec Discord pour acceder au dashboard.</p>

    {% if error %}
      <div class="alert">{{ error }}</div>
    {% endif %}

    <div class="actions">
      <a class="btn" href="{{ url_for('discord_login') }}">Se connecter avec Discord</a>
      <a class="btn secondary" href="{{ url_for('healthz') }}">Verifier le service</a>
    </div>

    <div class="info">
      <strong>Redirect URI attendue</strong>
      <code>{{ redirect_uri }}</code>
    </div>
  </main>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Erreur OAuth</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1a0f16, #2b1221);
            color: white;
            padding: 20px;
        }
        .card {
            width: min(92vw, 720px);
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.1);
            border-radius: 20px;
            padding: 28px;
            box-shadow: 0 20px 60px rgba(0,0,0,.35);
        }
        .btn {
            display: inline-block;
            margin-top: 16px;
            padding: 14px 18px;
            border-radius: 12px;
            background: #5865f2;
            color: white;
            text-decoration: none;
            font-weight: bold;
        }
        pre {
            white-space: pre-wrap;
            word-break: break-word;
            background: rgba(0,0,0,.25);
            padding: 14px;
            border-radius: 12px;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Erreur OAuth</h1>
        <p>{{ message }}</p>
        <pre>{{ details }}</pre>
        <a class="btn" href="{{ url_for('login') }}">Retour connexion</a>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
</head>
<body>
    <h1>Dashboard</h1>
    <p>Connecte en tant que {{ user.username }}</p>
    <a href="{{ url_for('logout') }}">Deconnexion</a>
</body>
</html>
"""


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS oauth_sessions (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        access_token TEXT NOT NULL,
        guilds_json TEXT NOT NULL
    )
    """)
    db.commit()
    db.close()


def save_oauth_session(user_id: str, username: str, access_token: str, guilds_admin: list[dict]):
    db = get_db()
    db.execute("""
        INSERT INTO oauth_sessions (user_id, username, access_token, guilds_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            access_token = excluded.access_token,
            guilds_json = excluded.guilds_json
    """, (user_id, username, access_token, json.dumps(guilds_admin)))
    db.commit()
    db.close()


def render_oauth_error(message: str, details: str, status_code: int = 400):
    return render_template_string(ERROR_HTML, message=message, details=details), status_code


init_db()


@app.route("/routes", methods=["GET"])
def routes():
    return {
        "routes": sorted([str(rule) for rule in app.url_map.iter_rules()])
    }, 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return {"ok": True}, 200


@app.route("/", methods=["GET", "HEAD"])
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "HEAD"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    missing = []
    if not CLIENT_ID:
        missing.append("CLIENT_ID")
    if not REDIRECT_URI:
        missing.append("REDIRECT_URI")
    if not OAUTH_EXCHANGE_URL:
        missing.append("OAUTH_EXCHANGE_URL")

    if missing:
        return {
            "missing": missing,
            "CLIENT_ID": CLIENT_ID or "MANQUANT",
            "REDIRECT_URI": REDIRECT_URI or "MANQUANT",
            "OAUTH_EXCHANGE_URL": OAUTH_EXCHANGE_URL or "MANQUANT",
        }, 500

    return render_template_string(LOGIN_HTML, redirect_uri=REDIRECT_URI, error=None)


@app.route("/discord-login", methods=["GET"])
def discord_login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    session.permanent = True
    session.modified = True

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }
    return redirect(f"{DISCORD_AUTH_URL}?{urlencode(params)}")


@app.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    returned_state = request.args.get("state")
    expected_state = session.get("oauth_state")

    if error:
        return render_oauth_error("Discord a renvoye une erreur OAuth.", f"error={error}", 400)

    if not code:
        return render_oauth_error("Le callback Discord ne contient pas de code.", str(dict(request.args)), 400)

    if not expected_state:
        return render_oauth_error(
            "Le state OAuth n'existe plus dans la session.",
            "La session n'a probablement pas ete conservee entre /discord-login et /callback.",
            400,
        )

    if returned_state != expected_state:
        return render_oauth_error(
            "Le state OAuth est invalide.",
            f"state_recu={returned_state} | state_attendu={expected_state}",
            400,
        )

    try:
        exchange_resp = requests.post(
            OAUTH_EXCHANGE_URL,
            json={"code": code, "redirect_uri": REDIRECT_URI},
            timeout=20,
        )
        response_text = exchange_resp.text
        exchange_resp.raise_for_status()
        token_json = exchange_resp.json()
    except requests.exceptions.HTTPError:
        return render_oauth_error(
            f"Erreur HTTP du service OAuth: {exchange_resp.status_code}",
            response_text,
            exchange_resp.status_code,
        )
    except requests.exceptions.RequestException as exc:
        return render_oauth_error(
            "Impossible de contacter le service OAuth externe.",
            str(exc),
            502,
        )
    except ValueError:
        return render_oauth_error(
            "Le service OAuth a renvoye un JSON invalide.",
            response_text if "response_text" in locals() else "pas de reponse",
            502,
        )

    access_token = token_json.get("access_token")
    if not access_token:
        return render_oauth_error(
            "Le service OAuth n'a pas renvoye access_token.",
            json.dumps(token_json, ensure_ascii=False),
            400,
        )

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    try:
        user_resp = requests.get(DISCORD_API_URL, headers=auth_headers, timeout=15)
        user_resp.raise_for_status()
        user = user_resp.json()

        guilds_resp = requests.get(DISCORD_GUILDS_URL, headers=auth_headers, timeout=15)
        guilds_resp.raise_for_status()
        guilds = guilds_resp.json()
    except requests.exceptions.RequestException as exc:
        return render_oauth_error(
            "Impossible de recuperer le profil ou les serveurs Discord.",
            str(exc),
            502,
        )

    guilds_admin = []
    for g in guilds:
        permissions = int(g.get("permissions", 0))
        if permissions & 0x8:
            guilds_admin.append({"id": g["id"], "name": g["name"]})

    user_id = user.get("id")
    username = user.get("username")

    if not user_id or not username:
        return render_oauth_error(
            "Les infos utilisateur Discord sont invalides.",
            json.dumps(user, ensure_ascii=False),
            400,
        )

    save_oauth_session(user_id, username, access_token, guilds_admin)

    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["username"] = username

    return redirect(url_for("dashboard"))


@app.route("/dashboard", methods=["GET"])
def dashboard():
    user_id = session.get("user_id")
    username = session.get("username")

    if not user_id or not username:
        return redirect(url_for("login"))

    return render_template_string(
        DASHBOARD_HTML,
        user={"id": user_id, "username": username},
    )


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
