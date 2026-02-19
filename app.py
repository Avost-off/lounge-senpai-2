import os
import sqlite3
import requests
from flask import Flask, render_template, redirect, request, session, url_for

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

DATABASE = "database.db"

# ==============================
# DISCORD OAUTH CONFIG
# ==============================

CLIENT_ID = "TON_CLIENT_ID"
CLIENT_SECRET = "TON_CLIENT_SECRET"
REDIRECT_URI = "https://TON_APP.onrender.com/callback"

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"

# ==============================
# DATABASE
# ==============================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

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

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers).json()

    user = requests.get(
        DISCORD_API_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"}
    ).json()

    session["user"] = user
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ==============================
# DASHBOARD
# ==============================

@app.route("/", methods=["GET", "POST"])
def dashboard():

    if "user" not in session:
        return redirect("/login")

    db = get_db()

    search = request.args.get("search")
    if search:
        users = db.execute("""
            SELECT * FROM user_stats
            WHERE user_id LIKE ?
        """, (f"%{search}%",)).fetchall()
    else:
        users = db.execute("""
            SELECT * FROM user_stats
            LIMIT 50
        """).fetchall()

    leveling = db.execute("""
        SELECT leveling_config FROM guild_settings LIMIT 1
    """).fetchone()

    db.close()

    return render_template(
        "dashboard.html",
        users=users,
        leveling=leveling,
        user=session["user"]
    )

# ==============================
# UPDATE BALANCE
# ==============================

@app.route("/update_balance", methods=["POST"])
def update_balance():
    user_id = request.form["user_id"]
    balance = request.form["balance"]

    db = get_db()
    db.execute("""
        UPDATE user_stats
        SET balance = ?
        WHERE user_id = ?
    """, (balance, user_id))
    db.commit()
    db.close()

    return redirect("/")

# ==============================
# TOGGLE LEVELING
# ==============================

@app.route("/toggle_leveling")
def toggle_leveling():
    db = get_db()

    row = db.execute("""
        SELECT leveling_config FROM guild_settings LIMIT 1
    """).fetchone()

    if row:
        import json
        config = json.loads(row["leveling_config"])
        config["enabled"] = not config.get("enabled", False)

        db.execute("""
            UPDATE guild_settings
            SET leveling_config = ?
        """, (json.dumps(config),))

        db.commit()

    db.close()
    return redirect("/")

# ==============================

if __name__ == "__main__":
    app.run()
