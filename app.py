import json
import os
import sqlite3
from datetime import timedelta
from urllib.parse import urlencode

import requests
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

# ==============================
# APP FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

DATABASE = os.path.join(BASE_DIR, "main_database.db")

# ==============================
# DISCORD OAUTH CONFIG
# ==============================
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("OAuth non configure !")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"

# ==============================
# DATABASE
# ==============================
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

# ==============================
# HEALTHCHECK
# ==============================
@app.route("/healthz")
def healthz():
    return {"ok": True}, 200


# ==============================
# LOGIN / OAUTH2
# ==============================
@app.route("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


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


# ==============================
# DASHBOARD
# ==============================
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

    return render_template(
        "dashboard.html",
        user={
            "id": user_id,
            "username": username,
        },
        guilds=guilds,
        selected_guild=selected_guild,
        users=users,
        commands=commands,
        total_balance=total_balance,
    )


# ==============================
# TOGGLE COMMAND AJAX
# ==============================
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


# ==============================
# RUN LOCAL ONLY
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
