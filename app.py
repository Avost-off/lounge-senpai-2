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
    # USERS multi-serveurs
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
    # COMMANDS
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
    # MARRIAGES
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
    # PRISON
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
    # GUILD SETTINGS
    db.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            leveling_config TEXT DEFAULT '{"enabled": true}'
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
    # User + Guilds
    user = requests.get(DISCORD_API_URL, headers={"Authorization": f"Bearer {access_token}"}).json()
    guilds = requests.get(DISCORD_GUILDS_URL, headers={"Authorization": f"Bearer {access_token}"}).json()

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
@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    db = get_db()

    selected_guild = request.args.get("guild_id")
    search_user = request.args.get("search_user")
    search_cmd = request.args.get("search_cmd")
    selected_command_id = request.args.get("command_id")

    # Serveurs disponibles
    guilds = session.get("guilds", [])

    # USERS filtrés par serveur + recherche
    users_query = "SELECT * FROM users"
    users_params = []
    if selected_guild:
        users_query += " WHERE guild_id = ?"
        users_params.append(selected_guild)
        if search_user:
            users_query += " AND (user_id LIKE ? OR LOWER(username) LIKE LOWER(?))"
            users_params += [f"%{search_user}%", f"%{search_user}%"]
    elif search_user:
        users_query += " WHERE user_id LIKE ? OR LOWER(username) LIKE LOWER(?)"
        users_params += [f"%{search_user}%", f"%{search_user}%"]
    else:
        users_query += " LIMIT 50"
    users = db.execute(users_query, users_params).fetchall()

    # COMMANDS filtrées par serveur + recherche + sélection
    commands_query = "SELECT * FROM commands"
    commands_params = []
    if selected_guild:
        commands_query += " WHERE guild_id = ?"
        commands_params.append(selected_guild)
        if search_cmd:
            commands_query += " AND (name LIKE ? OR category LIKE ? OR description LIKE ?)"
            commands_params += [f"%{search_cmd}%"]*3
        if selected_command_id:
            commands_query += " AND id = ?"
            commands_params.append(selected_command_id)
    else:
        if search_cmd:
            commands_query += " WHERE name LIKE ? OR category LIKE ? OR description LIKE ?"
            commands_params += [f"%{search_cmd}%"]*3
        elif selected_command_id:
            commands_query += " WHERE id = ?"
            commands_params.append(selected_command_id)
        else:
            commands_query += " LIMIT 50"
    commands = db.execute(commands_query, commands_params).fetchall()

    # STATS serveur
    stats_where = f"WHERE guild_id = '{selected_guild}'" if selected_guild else ""
    total_balance = db.execute(f"SELECT SUM(balance) FROM users {stats_where}").fetchone()[0] or 0
    prison_count = db.execute(f"SELECT COUNT(*) FROM prison {stats_where}").fetchone()[0]
    marriages_count = db.execute(f"SELECT COUNT(*) FROM marriages {stats_where}").fetchone()[0]

    # LEVELING
    leveling_row = db.execute("SELECT leveling_config FROM guild_settings WHERE guild_id = ? LIMIT 1", (selected_guild,)).fetchone() if selected_guild else None
    leveling = json.loads(leveling_row["leveling_config"]) if leveling_row else {"enabled": False}

    db.close()
    return render_template(
        "dashboard.html",
        guilds=guilds,
        selected_guild=selected_guild,
        users=users,
        commands=commands,
        selected_command_id=selected_command_id,
        search_user=search_user,
        search_cmd=search_cmd,
        total_balance=total_balance,
        prison_count=prison_count,
        marriages_count=marriages_count,
        leveling=leveling,
        user=session["user"]
    )

# ==============================
# UPDATE BALANCE
# ==============================
@app.route("/update_balance", methods=["POST"])
def update_balance():
    user_id = request.form.get("user_id")
    balance = request.form.get("balance")
    try:
        balance = int(balance)
    except:
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
    db.commit()
    db.close()
    return redirect(url_for("dashboard"))

# ==============================
# TOGGLE COMMAND
# ==============================
@app.route("/toggle_command", methods=["POST"])
def toggle_command():
    command_id = request.form.get("command_id")
    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id = ?", (command_id,)).fetchone()
    if cmd:
        new_val = 0 if cmd["enabled"] else 1
        db.execute("UPDATE commands SET enabled = ? WHERE id = ?", (new_val, command_id))
        db.commit()
    db.close()
    return redirect(url_for("dashboard"))

# ==============================
# INIT & RUN
# ==============================
init_db()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
