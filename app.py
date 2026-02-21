import os
import sqlite3
import json
import requests
from flask import Flask, render_template, redirect, request, session, url_for

# ==============================
# APP FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")
DATABASE = os.path.join(BASE_DIR, "database.db")

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
# DATABASE FUNCTIONS
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
            in_prison INTEGER DEFAULT 0,
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
            enabled INTEGER DEFAULT 1,
            required_role TEXT DEFAULT 'member'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user1 TEXT,
            user2 TEXT,
            marriage_timestamp TEXT,
            UNIQUE(guild_id, user1, user2)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS prison (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            prison_channel_id TEXT,
            moderator_id TEXT,
            reason TEXT,
            timestamp TEXT,
            saved_roles TEXT
        )
    """)
    db.commit()
    db.close()
    print("✅ Database initialized")

# ==============================
# LOGIN / OAUTH
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
        return redirect("/login")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    token_json = token_resp.json()
    if "access_token" not in token_json:
        return redirect("/login")
    access_token = token_json["access_token"]

    user = requests.get(DISCORD_API_URL, headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds = requests.get(DISCORD_GUILDS_URL, headers={"Authorization": f"Bearer {access_token}"}).json()

    # Garde uniquement les guildes où l'utilisateur est admin (permissions 0x8)
    session["guilds"] = [
        {"id": g["id"], "name": g["name"], "permissions": g.get("permissions", 0)}
        for g in guilds if int(g.get("permissions", 0)) & 0x8
    ]
    session["user"] = {"id": user["id"], "username": user["username"]}
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==============================
# DASHBOARD
# ==============================
@app.route("/")
def dashboard():
    try:
        if "user" not in session:
            return redirect("/login")

        db = get_db()
        selected_guild = request.args.get("guild_id")

        # Utilisateurs
        if selected_guild:
            users = db.execute("SELECT * FROM users WHERE guild_id=? LIMIT 50", (selected_guild,)).fetchall()
            commands = db.execute("SELECT * FROM commands WHERE guild_id=?", (selected_guild,)).fetchall()
        else:
            users = []
            commands = []

        # Stats
        total_balance = sum([u["balance"] for u in users]) if users else 0
        prison_count = db.execute("SELECT COUNT(*) FROM prison WHERE guild_id=?", (selected_guild,)).fetchone()[0] if selected_guild else 0
        marriages_count = db.execute("SELECT COUNT(*) FROM marriages WHERE guild_id=?", (selected_guild,)).fetchone()[0] if selected_guild else 0

        db.close()
        return render_template(
            "dashboard.html",
            user=session["user"],
            guilds=session.get("guilds", []),
            selected_guild=selected_guild,
            users=users,
            commands=commands,
            total_balance=total_balance,
            prison_count=prison_count,
            marriages_count=marriages_count
        )

    except Exception as e:
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>"

# ==============================
# TOGGLE COMMAND (AJAX)
# ==============================
@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    if "user" not in session:
        return {"success": False, "error": "Not logged in"}

    data = request.get_json()
    command_id = data.get("command_id")
    if not command_id:
        return {"success": False, "error": "Missing command_id"}

    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id=?", (command_id,)).fetchone()
    if cmd:
        new_state = 0 if cmd["enabled"] else 1
        db.execute("UPDATE commands SET enabled=? WHERE id=?", (new_state, command_id))
        db.commit()
        db.close()
        return {"success": True, "new_state": new_state}
    db.close()
    return {"success": False, "error": "Command not found"}

# ==============================
# START APP
# ==============================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
