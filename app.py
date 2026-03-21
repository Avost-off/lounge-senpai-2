import os
import sqlite3
import requests
from flask import Flask, render_template, redirect, request, session, flash, url_for

# ==============================
# APP FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# ⚡ SECRET KEY et configuration cookies
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY_LONG_AND_RANDOM")
if os.environ.get("RENDER") == "true":  # Render HTTPS
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )
else:  # Local dev HTTP
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )

DATABASE = os.path.join(BASE_DIR, "main_database.db")

# ==============================
# DISCORD OAUTH CONFIG
# ==============================
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")  # Exemple : https://ton-app.onrender.com/callback

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("⚠️ Variables OAuth Discord manquantes !")

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
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        name TEXT,
        category TEXT,
        description TEXT,
        enabled INTEGER DEFAULT 1
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        leveling_enabled INTEGER DEFAULT 1
    )""")
    db.commit()
    db.close()

init_db()

# ==============================
# LOGIN / OAUTH2
# ==============================
@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_AUTH_URL}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify%20guilds"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        flash("Erreur OAuth : code manquant", "danger")
        return redirect(url_for("login"))

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        token_resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers, timeout=10)
        token_resp.raise_for_status()
        token_json = token_resp.json()
    except requests.RequestException as e:
        flash(f"Erreur OAuth Discord : {e}", "danger")
        return redirect(url_for("login"))

    access_token = token_json.get("access_token")
    if not access_token:
        flash("Erreur OAuth : token invalide", "danger")
        return redirect(url_for("login"))

    # Récupération info user et guilds
    try:
        user_resp = requests.get(DISCORD_API_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        user_resp.raise_for_status()
        user = user_resp.json()

        guilds_resp = requests.get(DISCORD_GUILDS_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        guilds_resp.raise_for_status()
        guilds = guilds_resp.json()
    except requests.RequestException as e:
        flash(f"Impossible de récupérer les données Discord : {e}", "danger")
        return redirect(url_for("login"))

    # Filtre guilds où l'utilisateur est admin
    guilds_admin = [{"id": g["id"], "name": g["name"]} for g in guilds if int(g.get("permissions", 0)) & 0x8]

    # ⚡ Stockage session
    session["user"] = {"id": user["id"], "username": user["username"]}
    session["guilds"] = guilds_admin
    session["token"] = access_token

    print("SESSION USER:", session.get("user"))  # Debug

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
    if "user" not in session:
        return redirect(url_for("login"))

    selected_guild = request.args.get("guild_id")
    db = get_db()

    users = []
    commands = []
    total_balance = 0

    if selected_guild:
        users = db.execute("SELECT * FROM users WHERE guild_id=?", (selected_guild,)).fetchall()
        commands = db.execute("SELECT * FROM commands WHERE guild_id=?", (selected_guild,)).fetchall()
        result = db.execute("SELECT SUM(balance) FROM users WHERE guild_id=?", (selected_guild,)).fetchone()
        total_balance = result[0] if result and result[0] else 0

    db.close()

    return render_template(
        "dashboard.html",
        user=session["user"],
        guilds=session.get("guilds", []),
        selected_guild=selected_guild,
        users=users,
        commands=commands,
        total_balance=total_balance
    )

# ==============================
# TOGGLE COMMAND AJAX
# ==============================
@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    if "user" not in session:
        return {"success": False}

    data = request.get_json()
    command_id = data.get("command_id")
    if not command_id:
        return {"success": False}

    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id=?", (command_id,)).fetchone()
    if not cmd:
        db.close()
        return {"success": False}

    new_state = 0 if cmd["enabled"] else 1
    db.execute("UPDATE commands SET enabled=? WHERE id=?", (new_state, command_id))
    db.commit()
    db.close()

    return {"success": True, "new_state": new_state}

# ==============================
# RUN LOCAL / Render
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
