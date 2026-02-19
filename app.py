import os
import sqlite3
import requests
import json
from flask import Flask, render_template, redirect, request, session, url_for, flash

# ==============================
# APP FLASK
# ==============================
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "CHANGE_THIS_SECRET_KEY")

DATABASE = "database.db"

# ==============================
# DISCORD OAUTH CONFIG
# ==============================
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://lounge-senpai-2.onrender.com/callback")

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
    if not code:
        flash("Erreur OAuth : code manquant", "danger")
        return redirect("/")

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
        flash("Erreur OAuth : token invalide", "danger")
        return redirect("/login")

    user_response = requests.get(
        DISCORD_API_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"}
    )
    user = user_response.json()
    session["user"] = user
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

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
            LIMIT 50
        """, (f"%{search}%",)).fetchall()
    else:
        users = db.execute("""
            SELECT * FROM user_stats
            LIMIT 50
        """).fetchall()

    leveling_row = db.execute("""
        SELECT leveling_config FROM guild_settings LIMIT 1
    """).fetchone()

    db.close()

    leveling = json.loads(leveling_row["leveling_config"]) if leveling_row else {"enabled": False}

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
    user_id = request.form.get("user_id")
    balance = request.form.get("balance")

    if not user_id or balance is None:
        flash("Erreur : identifiant ou balance manquant", "danger")
        return redirect("/")

    try:
        balance = int(balance)
    except ValueError:
        flash("Erreur : balance doit être un nombre entier", "danger")
        return redirect("/")

    db = get_db()
    db.execute("""
        UPDATE user_stats
        SET balance = ?
        WHERE user_id = ?
    """, (balance, user_id))
    db.commit()
    db.close()

    flash(f"Balance de l'utilisateur {user_id} mise à jour !", "success")
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
# RUN
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
