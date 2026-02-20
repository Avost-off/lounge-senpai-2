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
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://lounge-senpai-2.onrender.com/callback")

if not CLIENT_ID or not CLIENT_SECRET or not SESSION_SECRET:
    raise RuntimeError("Les variables d'environnement CLIENT_ID, CLIENT_SECRET ou SESSION_SECRET ne sont pas définies !")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_URL = "https://discord.com/api/users/@me"

# ==============================
# DATABASE
# ==============================
def get_db():
    try:
        conn = sqlite3.connect(DATABASE, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print("Erreur BDD:", e)
        return None

def init_db():
    db = get_db()
    if not db:
        print("Erreur DB")
        return

    # Création des tables si elles n'existent pas
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            leveling_config TEXT DEFAULT '{"enabled": true}'
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user1_id TEXT NOT NULL,
            user2_id TEXT NOT NULL,
            marriage_timestamp TEXT NOT NULL,
            UNIQUE (guild_id, user1_id, user2_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS prison (
            guild_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            prison_channel_id INTEGER,
            moderator_id TEXT,
            reason TEXT,
            timestamp TEXT,
            saved_roles TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            description TEXT,
            enabled BOOLEAN DEFAULT 1,
            required_role TEXT DEFAULT 'member'
        )
    """)

    # Inserts de test si vide
    if db.execute("SELECT COUNT(*) FROM user_stats").fetchone()[0] == 0:
        db.execute("""
            INSERT INTO user_stats (guild_id, user_id, username, xp, level, balance)
            VALUES (?,?,?,?,?,?)
        """, (1, "1111", "UserOne", 150, 2, 500))
        db.execute("""
            INSERT INTO user_stats (guild_id, user_id, username, xp, level, balance)
            VALUES (?,?,?,?,?,?)
        """, (1, "2222", "UserTwo", 450, 5, 2000))

    if db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0:
        db.execute("""
            INSERT INTO commands (name, category, description, enabled)
            VALUES ('!daily', 'Economy', 'Claim daily coins', 1)
        """)
        db.execute("""
            INSERT INTO commands (name, category, description, enabled)
            VALUES ('!marry', 'Fun', 'Marry a member', 1)
        """)

    db.commit()
    db.close()

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
@app.route("/", methods=["GET"])
def dashboard():
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    if not db:
        return "Erreur DB", 500

    # Recherche membre
    search = request.args.get("search")
    try:
        if search:
            users = db.execute("""
                SELECT * FROM user_stats
                WHERE user_id LIKE ? OR LOWER(username) LIKE LOWER(?)
                LIMIT 50
            """, (f"%{search}%", f"%{search}%")).fetchall()
        else:
            users = db.execute("SELECT * FROM user_stats LIMIT 50").fetchall()
    except sqlite3.Error as e:
        print("Erreur BDD:", e)
        users = []

    # Leveling
    try:
        leveling_row = db.execute("SELECT leveling_config FROM guild_settings LIMIT 1").fetchone()
        leveling = json.loads(leveling_row["leveling_config"]) if leveling_row else {"enabled": False}
    except:
        leveling = {"enabled": False}

    # Counts
    try:
        marriages_count = db.execute("SELECT COUNT(*) FROM marriages").fetchone()[0]
    except:
        marriages_count = 0

    try:
        prison_count = db.execute("SELECT COUNT(*) FROM prison").fetchone()[0]
    except:
        prison_count = 0

    try:
        total_balance = db.execute("SELECT SUM(balance) FROM user_stats").fetchone()[0] or 0
    except:
        total_balance = 0

    # Recherche commandes
    cmd_search = request.args.get("cmd_search")
    try:
        if cmd_search:
            commands = db.execute("""
                SELECT * FROM commands
                WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
                LIMIT 50
            """, (f"%{cmd_search}%", f"%{cmd_search}%", f"%{cmd_search}%")).fetchall()
        else:
            commands = db.execute("SELECT * FROM commands LIMIT 50").fetchall()
    except sqlite3.Error as e:
        print("Erreur BDD commandes:", e)
        commands = []

    db.close()

    return render_template(
        "dashboard.html",
        users=users,
        commands=commands,
        leveling=leveling,
        marriages_count=marriages_count,
        prison_count=prison_count,
        total_balance=total_balance,
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
        return redirect(url_for("dashboard"))

    try:
        balance = int(balance)
    except ValueError:
        flash("Erreur : balance doit être un nombre entier", "danger")
        return redirect(url_for("dashboard"))

    db = get_db()
    if db:
        try:
            db.execute("UPDATE user_stats SET balance = ? WHERE user_id = ?", (balance, user_id))
            db.commit()
        except sqlite3.Error as e:
            print("Erreur BDD:", e)
        db.close()

    flash(f"Balance de l'utilisateur {user_id} mise à jour !", "success")
    return redirect(url_for("dashboard"))

# ==============================
# TOGGLE LEVELING
# ==============================
@app.route("/toggle_leveling", methods=["POST"])
def toggle_leveling():
    if "user" not in session:
        return redirect("/login")

    db = get_db()
    if not db:
        flash("Erreur DB", "danger")
        return redirect(url_for("dashboard"))

    try:
        row = db.execute("SELECT guild_id, leveling_config FROM guild_settings LIMIT 1").fetchone()
        if row:
            config = json.loads(row["leveling_config"])
            config["enabled"] = not config.get("enabled", False)
            db.execute(
                "UPDATE guild_settings SET leveling_config = ? WHERE guild_id = ?",
                (json.dumps(config), row["guild_id"])
            )
        else:
            config = {"enabled": True}
            db.execute(
                "INSERT INTO guild_settings (guild_id, leveling_config) VALUES (?, ?)",
                (1, json.dumps(config))
            )
        db.commit()
    except sqlite3.Error as e:
        print("Erreur BDD:", e)
    finally:
        db.close()

    return redirect(url_for("dashboard"))

# ==============================
# RUN INIT
# ==============================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
