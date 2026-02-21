# app.py
import os
import sqlite3
import json
from flask import Flask, render_template, request, session, redirect, url_for, jsonify

# ==============================
# CONFIG FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")

DB_PATH = os.path.join(BASE_DIR, "database.db")

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            name TEXT,
            category TEXT,
            description TEXT,
            enabled INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

# ==============================
# LOGIN / OAUTH2
# ==============================
@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify%20guilds"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect("/login")
    
    import requests
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
    
    # Filtrer les guilds où l'utilisateur est admin (permission 0x8)
    guilds_admin = [g for g in guilds if g.get("permissions", 0) & 0x8]

    session["user"] = user
    session["guilds"] = guilds_admin
    session["token"] = access_token
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
    if "user" not in session:
        return redirect("/login")
    
    guild_id = request.args.get("guild_id")
    db = get_db()

    # Users
    users = []
    if guild_id:
        users_query = "SELECT * FROM users WHERE guild_id=?"
        users_params = (guild_id,)
        users = db.execute(users_query, users_params).fetchall()

    # Commands
    commands = []
    if guild_id:
        commands_query = "SELECT * FROM commands WHERE guild_id=? ORDER BY category,name"
        commands_params = (guild_id,)
        commands = db.execute(commands_query, commands_params).fetchall()

    # Stats
    total_balance = db.execute("SELECT SUM(balance) FROM users").fetchone()[0] or 0
    db.close()

    return render_template(
        "dashboard.html",
        user=session["user"],
        guilds=session.get("guilds", []),
        selected_guild=guild_id,
        users=users,
        commands=commands,
        total_balance=total_balance
    )

# ==============================
# AJAX Toggle Command
# ==============================
@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    if "user" not in session:
        return jsonify({"success": False})
    
    data = request.get_json()
    command_id = data.get("command_id")
    if not command_id:
        return jsonify({"success": False})

    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id=?", (command_id,)).fetchone()
    if not cmd:
        db.close()
        return jsonify({"success": False})
    
    new_state = 0 if cmd["enabled"] else 1
    db.execute("UPDATE commands SET enabled=? WHERE id=?", (new_state, command_id))
    db.commit()
    db.close()

    return jsonify({"success": True, "new_state": new_state})

# ==============================
# START
# ==============================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
