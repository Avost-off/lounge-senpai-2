import os
import sqlite3
import requests
import json
from flask import Flask, render_template, redirect, request, session, flash, url_for

# ==============================
# APP FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")
DATABASE = os.path.join(BASE_DIR, "main_database.db")

# ==============================
# DISCORD OAUTH CONFIG
# ==============================
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("Variables OAuth manquantes !")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"

# ==============================
# DATABASE UTIL
# ==============================
def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    if not db:
        print("Erreur DB")
        return

    # Table users multi-serveur
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

    # Table commands
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

    # Table guild_settings
    db.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        leveling_enabled INTEGER DEFAULT 1
    )
    """)

    db.commit()
    db.close()

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
        return redirect("/login")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    token_json = token_resp.json()
    if "access_token" not in token_json:
        flash("Erreur OAuth : token invalide", "danger")
        return redirect("/login")

    access_token = token_json["access_token"]

    # Récupération user
    user = requests.get(DISCORD_API_URL, headers={"Authorization": f"Bearer {access_token}"}).json()

    # Récupération guildes (seulement id, name, permissions pour limiter la taille de session)
    guilds_resp = requests.get(DISCORD_GUILDS_URL, headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds_admin = []
    for g in guilds_resp:
        permissions = g.get("permissions", 0)
        if permissions & 0x8:  # ADMINISTRATOR
            guilds_admin.append({
                "id": g["id"],
                "name": g["name"],
                "permissions": permissions
            })

    session["user"] = {"id": user["id"], "username": user["username"]}
    session["guilds"] = guilds_admin
    session["token"] = access_token

    if not guilds_admin:
        flash("Tu n'es admin d'aucun serveur Discord.", "warning")

    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==============================
# DASHBOARD
# ==============================
@app.route("/", methods=["GET"])
def dashboard():
    if "user" not in session:
        return redirect("/login")

    selected_guild = request.args.get("guild_id")
    db = get_db()

    # Users
    users = []
    if selected_guild:
        users = db.execute(
            "SELECT * FROM users WHERE guild_id=?",
            (selected_guild,)
        ).fetchall()

    # Commands
    commands = []
    if selected_guild:
        commands = db.execute(
            "SELECT * FROM commands WHERE guild_id=?",
            (selected_guild,)
        ).fetchall()

    # Stats
    total_balance = db.execute(
        "SELECT SUM(balance) FROM users WHERE guild_id=?",
        (selected_guild,)
    ).fetchone()[0] or 0 if selected_guild else 0

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
# INIT & RUN
# ==============================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
