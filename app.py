# app.py
import os
import sqlite3
import json
import requests
from flask import Flask, render_template, redirect, request, session, url_for, jsonify, flash

# ==============================
# APP FLASK
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "database.db")

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
# DATABASE
# ==============================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
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
    );

    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        name TEXT NOT NULL,
        category TEXT,
        description TEXT,
        enabled INTEGER DEFAULT 1,
        required_role TEXT DEFAULT 'member'
    );

    CREATE TABLE IF NOT EXISTS marriages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        user1 TEXT,
        user2 TEXT,
        marriage_timestamp TEXT,
        UNIQUE(guild_id, user1, user2)
    );

    CREATE TABLE IF NOT EXISTS prison (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        user_id TEXT,
        prison_channel_id TEXT,
        moderator_id TEXT,
        reason TEXT,
        timestamp TEXT,
        saved_roles TEXT
    );

    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        leveling_config TEXT DEFAULT '{"enabled": true}'
    );
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
        return "Erreur OAuth : code manquant"

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
        return "Erreur OAuth : token invalide"

    access_token = token_json["access_token"]

    user = requests.get(DISCORD_API_URL, headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds = requests.get(DISCORD_GUILDS_URL, headers={"Authorization": f"Bearer {access_token}"}).json()

    # Filtrer uniquement les guilds où l'utilisateur est administrateur
    guilds = [g for g in guilds if int(g.get("permissions", 0)) & 0x8]

    session["user"] = user
    session["guilds"] = guilds
    session["token"] = access_token

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
    search_user = request.args.get("search_user")
    search_cmd = request.args.get("search_cmd")

    db = get_db()

    # Users
    users_query = "SELECT * FROM users"
    users_params = []
    if selected_guild:
        users_query += " WHERE guild_id=?"
        users_params.append(selected_guild)
    if search_user:
        if "WHERE" in users_query:
            users_query += " AND (user_id LIKE ? OR LOWER(username) LIKE LOWER(?))"
        else:
            users_query += " WHERE (user_id LIKE ? OR LOWER(username) LIKE LOWER(?))"
        users_params.extend([f"%{search_user}%", f"%{search_user}%"])
    users_query += " ORDER BY level DESC, xp DESC LIMIT 50"
    users = db.execute(users_query, users_params).fetchall()

    # Commands
    commands_query = "SELECT * FROM commands"
    cmd_params = []
    if selected_guild:
        commands_query += " WHERE guild_id=?"
        cmd_params.append(selected_guild)
    if search_cmd:
        if "WHERE" in commands_query:
            commands_query += " AND (name LIKE ? OR category LIKE ? OR description LIKE ?)"
        else:
            commands_query += " WHERE (name LIKE ? OR category LIKE ? OR description LIKE ?)"
        cmd_params.extend([f"%{search_cmd}%"]*3)
    commands = db.execute(commands_query, cmd_params).fetchall()

    # Stats
    total_balance = db.execute("SELECT SUM(balance) as total FROM users").fetchone()["total"] or 0
    prison_count = db.execute("SELECT COUNT(*) as total FROM prison").fetchone()["total"] or 0
    marriages_count = db.execute("SELECT COUNT(*) as total FROM marriages").fetchone()["total"] or 0

    # Leveling
    leveling_row = db.execute("SELECT leveling_config FROM guild_settings WHERE guild_id=? LIMIT 1", (selected_guild,)).fetchone() if selected_guild else None
    leveling = json.loads(leveling_row["leveling_config"]) if leveling_row else {"enabled": False}

    db.close()

    return render_template(
        "dashboard.html",
        users=users,
        commands=commands,
        total_balance=total_balance,
        prison_count=prison_count,
        marriages_count=marriages_count,
        leveling=leveling,
        user=session["user"],
        guilds=session.get("guilds", []),
        selected_guild=selected_guild
    )

# ==============================
# TOGGLE COMMAND AJAX
# ==============================
@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    if "user" not in session:
        return jsonify({"success": False, "error": "Not logged in"})

    data = request.get_json()
    command_id = data.get("command_id")
    if not command_id:
        return jsonify({"success": False, "error": "No command ID"})

    db = get_db()
    row = db.execute("SELECT enabled FROM commands WHERE id=?", (command_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({"success": False, "error": "Command not found"})

    new_state = 0 if row["enabled"] else 1
    db.execute("UPDATE commands SET enabled=? WHERE id=?", (new_state, command_id))
    db.close()

    return jsonify({"success": True, "new_state": new_state})

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
