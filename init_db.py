import sqlite3
import json

DATABASE = "main_database.db"
conn = sqlite3.connect(DATABASE)
c = conn.cursor()

# USER STATS
c.execute("""
CREATE TABLE IF NOT EXISTS user_stats (
    guild_id INTEGER,
    user_id INTEGER,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    balance INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

# GUILD SETTINGS
c.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    leveling_config TEXT
)
""")

# MARRIAGES
c.execute("""
CREATE TABLE IF NOT EXISTS marriages (
    guild_id INTEGER,
    user1_id INTEGER,
    user2_id INTEGER,
    married_at INTEGER,
    PRIMARY KEY (guild_id, user1_id, user2_id)
)
""")

# PRISON
c.execute("""
CREATE TABLE IF NOT EXISTS prison (
    guild_id INTEGER,
    user_id INTEGER,
    release_time INTEGER,
    PRIMARY KEY (guild_id, user_id)
)
""")

conn.commit()
conn.close()
print("✅ Database initialisée")
