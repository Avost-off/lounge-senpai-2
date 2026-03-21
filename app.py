import json
import os
import sqlite3
from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, flash, redirect, request, session, url_for, render_template_string
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
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("OAuth non configure !")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        user_id TEXT,
        username TEXT,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        balance INTEGER DEFAULT 0,
        UNIQUE(guild_id, user_id)
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        name TEXT,
        category TEXT,
        description TEXT,
        enabled INTEGER DEFAULT 1
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        leveling_enabled INTEGER DEFAULT 1
    )
    """)
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


def get_saved_guilds(user_id: str) -> list[dict]:
    db = get_db()
    row = db.execute(
        "SELECT guilds_json FROM oauth_sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    db.close()

    if not row:
        return []

    try:
        return json.loads(row["guilds_json"])
    except (TypeError, json.JSONDecodeError):
        return []


init_db()

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion Discord</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #0a1020, #121f38);
            color: white;
        }
        .card {
            width: min(92vw, 480px);
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
        .msg {
            margin: 10px 0;
            padding: 10px 12px;
            border-radius: 12px;
            background: rgba(255,255,255,.08);
        }
        .muted {
            color: #b8c2df;
        }
        code {
            background: rgba(255,255,255,.08);
            padding: 2px 7px;
            border-radius: 999px;
        }
    </style>
</head>
<body>
    <div class="card">
        <p style="text-transform:uppercase;letter-spacing:.16em;font-size:.75rem;color:#aab6d7;">Discord OAuth</p>
        <h1>Connexion au panel</h1>
        <p class="muted">Connecte-toi avec Discord pour acceder au dashboard.</p>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="msg">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <a class="btn" href="{{ url_for('discord_login') }}">Se connecter avec Discord</a>

        <p class="muted" style="margin-top:16px;">
            Redirect URI attendue :
            <br>
            <code>{{ redirect_uri }}</code>
        </p>
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
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #0b1120, #131d33);
            color: white;
            padding: 24px;
        }
        .wrap {
            max-width: 1100px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.1);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 18px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }
        .card {
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.1);
            border-radius: 16px;
            padding: 18px;
        }
        .muted {
            color: #b8c2df;
        }
        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 18px;
        }
        .btn {
            display: inline-block;
            padding: 10px 14px;
            border-radius: 12px;
            background: #5865f2;
            color: white;
            text-decoration: none;
            border: 0;
            cursor: pointer;
        }
        select {
            padding: 10px 12px;
            border-radius: 12px;
            border: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,.08);
            text-align: left;
        }
        @media (max-width: 900px) {
            .grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media (max-width: 600px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .topbar {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
<div class="wrap">
    <div class="topbar">
        <div>
            <h1>Dashboard</h1>
            <p class="muted">Connecte en tant que {{ user.username }}</p>
        </div>
        <div>
            <a class="btn" href="{{ url_for('logout') }}">Deconnexion</a>
        </div>
    </div>

    <div class="panel">
        <form method="get" action="{{ url_for('dashboard') }}">
            <label for="guild_id">Choisir un serveur :</label>
            <select name="guild_id" id="guild_id" onchange="this.form.submit()">
                <option value="">Selectionne un serveur</option>
                {% for guild in guilds %}
                    <option value="{{ guild.id }}" {% if selected_guild == guild.id %}selected{% endif %}>
                        {{ guild.name }}
                    </option>
                {% endfor %}
            </select>
        </form>
    </div>

    <div class="grid">
        <div class="card">
            <div class="muted">Serveurs admin</div>
            <h2>{{ guilds|length }}</h2>
        </div>
        <div class="card">
            <div class="muted">Utilisateurs</div>
            <h2>{{ users|length }}</h2>
        </div>
        <div class="card">
            <div class="muted">Commandes</div>
            <h2>{{ commands|length }}</h2>
        </div>
        <div class="card">
            <div class="muted">Balance totale</div>
            <h2>{{ total_balance }}</h2>
        </div>
    </div>

    <div class="panel">
        <h2>Utilisateurs</h2>
        {% if users %}
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>XP</th>
                        <th>Level</th>
                        <th>Balance</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in users %}
                    <tr>
                        <td>{{ u.username }}</td>
                        <td>{{ u.xp }}</td>
                        <td>{{ u.level }}</td>
                        <td>{{ u.balance }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p class="muted">Aucun utilisateur pour ce serveur.</p>
        {% endif %}
    </div>

    <div class="panel">
        <h2>Commandes</h2>
        {% if commands %}
            <table>
                <thead>
                    <tr>
                        <th>Nom</th>
                        <th>Categorie</th>
                        <th>Description</th>
                        <th>Etat</th>
                    </tr>
                </thead>
                <tbody>
                    {% for c in commands %}
                    <tr>
                        <td>{{ c.name }}</td>
                        <td>{{ c.category }}</td>
                        <td>{{ c.description }}</td>
                        <td>{{ "Active" if c.enabled else "Desactivee" }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p class="muted">Aucune commande pour ce serveur.</p>
        {% endif %}
    </div>
</div>
</body>
</html>
"""


@app.route("/healthz")
def healthz():
    return {"ok": True}, 200


@app.route("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML, redirect_uri=REDIRECT_URI)


@app.route("/discord-login")
def discord_login():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return redirect(f"{DISCORD_AUTH_URL}?{urlencode(params)}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        flash(f"Erreur OAuth Discord: {error}", "danger")
        return redirect(url_for("login"))

    if not code:
        flash("Erreur OAuth : code manquant", "danger")
        return redirect(url_for("login"))

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        token_resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers, timeout=15)

        if token_resp.status_code == 429:
            retry_after = token_resp.headers.get("Retry-After", "quelques")
            flash(f"Trop de requetes sur Discord. Reessaie dans {retry_after} secondes.", "warning")
            return redirect(url_for("login"))

        token_resp.raise_for_status()
        token_json = token_resp.json()
    except requests.exceptions.HTTPError:
        flash(f"Erreur OAuth Discord: {token_resp.status_code}", "danger")
        return redirect(url_for("login"))
    except requests.exceptions.RequestException:
        flash("Impossible de contacter l'API Discord.", "danger")
        return redirect(url_for("login"))
    except ValueError:
        flash("Reponse invalide de l'API Discord.", "danger")
        return redirect(url_for("login"))

    access_token = token_json.get("access_token")
    if not access_token:
        flash("Erreur OAuth : token invalide", "danger")
        return redirect(url_for("login"))

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    try:
        user_resp = requests.get(DISCORD_API_URL, headers=auth_headers, timeout=15)
        user_resp.raise_for_status()
        user = user_resp.json()

        guilds_resp = requests.get(DISCORD_GUILDS_URL, headers=auth_headers, timeout=15)
        guilds_resp.raise_for_status()
        guilds = guilds_resp.json()
    except requests.exceptions.RequestException:
        flash("Impossible de recuperer tes informations Discord.", "danger")
        return redirect(url_for("login"))
    except ValueError:
        flash("Reponse invalide de l'API Discord.", "danger")
        return redirect(url_for("login"))

    guilds_admin = []
    for g in guilds:
        permissions = int(g.get("permissions", 0))
        if permissions & 0x8:
            guilds_admin.append({
                "id": g["id"],
                "name": g["name"],
            })

    user_id = user.get("id")
    username = user.get("username")

    if not user_id or not username:
        flash("Informations utilisateur Discord invalides.", "danger")
        return redirect(url_for("login"))

    save_oauth_session(user_id, username, access_token, guilds_admin)

    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["username"] = username

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
def dashboard():
    user_id = session.get("user_id")
    username = session.get("username")

    if not user_id or not username:
        return redirect(url_for("login"))

    guilds = get_saved_guilds(user_id)
    selected_guild = request.args.get("guild_id")

    db = get_db()

    users = []
    commands = []
    total_balance = 0

    if selected_guild:
        users = db.execute(
            "SELECT * FROM users WHERE guild_id = ?",
            (selected_guild,),
        ).fetchall()

        commands = db.execute(
            "SELECT * FROM commands WHERE guild_id = ?",
            (selected_guild,),
        ).fetchall()

        result = db.execute(
            "SELECT SUM(balance) AS total FROM users WHERE guild_id = ?",
            (selected_guild,),
        ).fetchone()

        total_balance = result["total"] if result and result["total"] else 0

    db.close()

    return render_template_string(
        DASHBOARD_HTML,
        user={"id": user_id, "username": username},
        guilds=guilds,
        selected_guild=selected_guild,
        users=users,
        commands=commands,
        total_balance=total_balance,
    )


@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    if "user_id" not in session:
        return {"success": False}, 401

    data = request.get_json(silent=True) or {}
    command_id = data.get("command_id")

    if not command_id:
        return {"success": False}, 400

    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id = ?", (command_id,)).fetchone()

    if not cmd:
        db.close()
        return {"success": False}, 404

    new_state = 0 if cmd["enabled"] else 1
    db.execute("UPDATE commands SET enabled = ? WHERE id = ?", (new_state, command_id))
    db.commit()
    db.close()

    return {"success": True, "new_state": new_state}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
