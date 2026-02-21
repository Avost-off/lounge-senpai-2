import os
import sqlite3
import requests
from flask import Flask, render_template, redirect, request, session, jsonify, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SESSION_SECRET", "SUPER_SECRET_KEY")

DATABASE = os.path.join(BASE_DIR, "main_database.db")

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"
DISCORD_GUILDS_URL = "https://discord.com/api/users/@me/guilds"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()

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

    db.commit()
    db.close()

def get_admin_guilds(token):
    resp = requests.get(
        DISCORD_GUILDS_URL,
        headers={"Authorization": f"Bearer {token}"}
    )
    guilds = resp.json()

    return [
        g for g in guilds
        if int(g.get("permissions", 0)) & 0x8
    ]

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
    token_resp = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    token_json = token_resp.json()

    access_token = token_json["access_token"]

    user = requests.get(
        DISCORD_API_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    session["user"] = user
    session["token"] = access_token
    session["guilds"] = get_admin_guilds(access_token)

    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    guild_id = request.args.get("guild_id")

    db = get_db()

    commands = []
    if guild_id:
        commands = db.execute(
            "SELECT * FROM commands WHERE guild_id = ?",
            (guild_id,)
        ).fetchall()

    db.close()

    return render_template(
        "dashboard.html",
        user=session["user"],
        guilds=session.get("guilds", []),
        commands=commands,
        selected_guild=guild_id
    )

# 🔥 AJAX TOGGLE
@app.route("/toggle_command_ajax", methods=["POST"])
def toggle_command_ajax():
    command_id = request.json.get("command_id")

    db = get_db()
    cmd = db.execute(
        "SELECT enabled FROM commands WHERE id = ?",
        (command_id,)
    ).fetchone()

    if cmd:
        new_val = 0 if cmd["enabled"] else 1
        db.execute(
            "UPDATE commands SET enabled = ? WHERE id = ?",
            (new_val, command_id)
        )
        db.commit()

        db.close()
        return jsonify({"success": True, "new_state": new_val})

    db.close()
    return jsonify({"success": False})

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
