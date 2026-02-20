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
SESSION_SECRET = os.environ.get("SESSION_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not SESSION_SECRET:
    raise RuntimeError("Variables d'environnement manquantes !")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"

# ==============================
# DATABASE
# ==============================
def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()

    # TABLE USER_STATS
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0
        )
    """)

    # TABLE GUILD_SETTINGS
    db.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            leveling_config TEXT
        )
    """)

    # TABLE COMMANDS
    db.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            description TEXT,
            enabled INTEGER DEFAULT 1
        )
    """)

    # INSERT DATA SI VIDE
    if db.execute("SELECT COUNT(*) FROM user_stats").fetchone()[0] == 0:
        db.execute("INSERT INTO user_stats (user_id, username, xp, level, balance) VALUES (?,?,?,?,?)",
                   ("1111", "UserOne", 150, 2, 500))
        db.execute("INSERT INTO user_stats (user_id, username, xp, level, balance) VALUES (?,?,?,?,?)",
                   ("2222", "UserTwo", 450, 5, 2000))

    if db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0:
        db.execute("INSERT INTO commands (name, category, description) VALUES (?,?,?)",
                   ("ban", "moderation", "Ban a user"))
        db.execute("INSERT INTO commands (name, category, description) VALUES (?,?,?)",
                   ("kick", "moderation", "Kick a user"))
        db.execute("INSERT INTO commands (name, category, description) VALUES (?,?,?)",
                   ("daily", "economy", "Claim daily reward"))

    db.commit()
    db.close()


init_db()

# ==============================
# LOGIN
# ==============================
@app.route("/login")
def login():
    return redirect(
        f"{DISCORD_AUTH_URL}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope=identify"
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
        "scope": "identify"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    token = token_response.json()

    if "access_token" not in token:
        return redirect("/login")

    user_response = requests.get(
        DISCORD_API_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"}
    )

    session["user"] = user_response.json()
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

    search_member = request.args.get("search_member")
    search_command = request.args.get("search_command")

    # MEMBERS SEARCH
    if search_member:
        users = db.execute("""
            SELECT * FROM user_stats
            WHERE user_id LIKE ?
            OR LOWER(username) LIKE LOWER(?)
            LIMIT 50
        """, (f"%{search_member}%", f"%{search_member}%")).fetchall()
    else:
        users = db.execute("SELECT * FROM user_stats LIMIT 50").fetchall()

    # COMMANDS SEARCH
    if search_command:
        commands = db.execute("""
            SELECT * FROM commands
            WHERE LOWER(name) LIKE LOWER(?)
            OR LOWER(category) LIKE LOWER(?)
            LIMIT 50
        """, (f"%{search_command}%", f"%{search_command}%")).fetchall()
    else:
        commands = db.execute("SELECT * FROM commands LIMIT 50").fetchall()

    # STATS
    total_balance = db.execute("SELECT SUM(balance) FROM user_stats").fetchone()[0] or 0
    members_count = db.execute("SELECT COUNT(*) FROM user_stats").fetchone()[0]
    commands_count = db.execute("SELECT COUNT(*) FROM commands").fetchone()[0]

    db.close()

    return render_template(
        "dashboard.html",
        users=users,
        commands=commands,
        total_balance=total_balance,
        members_count=members_count,
        commands_count=commands_count,
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
        return redirect("/")

    db = get_db()
    db.execute("UPDATE user_stats SET balance=? WHERE user_id=?",
               (balance, user_id))
    db.commit()
    db.close()

    return redirect("/")


# ==============================
# TOGGLE COMMAND
# ==============================
@app.route("/toggle_command/<int:cmd_id>")
def toggle_command(cmd_id):
    db = get_db()
    cmd = db.execute("SELECT enabled FROM commands WHERE id=?",
                     (cmd_id,)).fetchone()

    if cmd:
        new_state = 0 if cmd["enabled"] == 1 else 1
        db.execute("UPDATE commands SET enabled=? WHERE id=?",
                   (new_state, cmd_id))
        db.commit()

    db.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

