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
# DATABASE
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

    # ===============================
    # TABLE GUILDS
    # ===============================
    db.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id TEXT PRIMARY KEY,
            name TEXT,
            owner_id TEXT,
            created_at TEXT
        )
    """)

    # ===============================
    # TABLE USERS (multi-serveur)
    # ===============================
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

    # ===============================
    # TABLE COMMANDS
    # ===============================
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

    # ===============================
    # TABLE MARRIAGES
    # ===============================
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

    db.commit()
    db.close()


# ==============================
# LOGIN
# ==============================
@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
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

    token_response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    token_json = token_response.json()

    if "access_token" not in token_json:
        return redirect("/login")

    access_token = token_json["access_token"]

    user = requests.get(
        DISCORD_API_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    guilds = requests.get(
        DISCORD_GUILDS_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

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

    guild_id = request.args.get("guild_id")

    db = get_db()

    if guild_id:
        users = db.execute(
            "SELECT * FROM user_stats WHERE guild_id = ?",
            (guild_id,)
        ).fetchall()
    else:
        users = db.execute("SELECT * FROM user_stats LIMIT 50").fetchall()

    commands = db.execute("SELECT * FROM commands").fetchall()

    total_balance = db.execute(
        "SELECT SUM(balance) FROM user_stats"
    ).fetchone()[0] or 0

    prison_count = db.execute(
        "SELECT COUNT(*) FROM prison"
    ).fetchone()[0]

    marriages_count = db.execute(
        "SELECT COUNT(*) FROM marriages"
    ).fetchone()[0]

    db.close()

    return render_template(
        "dashboard.html",
        users=users,
        commands=commands,
        total_balance=total_balance,
        prison_count=prison_count,
        marriages_count=marriages_count,
        user=session["user"],
        guilds=session.get("guilds", [])
    )


# ==============================
# UPDATE BALANCE
# ==============================
@app.route("/update_balance", methods=["POST"])
def update_balance():
    user_id = request.form.get("user_id")
    balance = request.form.get("balance")

    if not user_id:
        return redirect(url_for("dashboard"))

    try:
        balance = int(balance)
    except:
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        "UPDATE user_stats SET balance = ? WHERE user_id = ?",
        (balance, user_id)
    )
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
    cmd = db.execute(
        "SELECT enabled FROM commands WHERE id = ?",
        (command_id,)
    ).fetchone()

    if cmd:
        new_value = 0 if cmd["enabled"] == 1 else 1
        db.execute(
            "UPDATE commands SET enabled = ? WHERE id = ?",
            (new_value, command_id)
        )
        db.commit()

    db.close()
    return redirect(url_for("dashboard"))


# ==============================
# START
# ==============================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
