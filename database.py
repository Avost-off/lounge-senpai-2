# utils/database.py
import aiosqlite
import os
import traceback
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

# ==============================
# CONFIGURATION
# ==============================
DATA_DIR = "./data"
DB_PATH = os.path.join(DATA_DIR, "database.db")


class DatabaseManager:
    """
    Gère toutes les interactions avec la base de données SQLite de manière asynchrone.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    # ==============================
    # CONNECTION
    # ==============================
    async def connect(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
            print(f"✅ Connexion DB réussie : {self.db_path}")
        except Exception as e:
            print("❌ ERREUR connexion DB")
            traceback.print_exc()
            raise e

    async def close(self):
        if self._connection:
            await self._connection.close()
            print("🔒 Connexion DB fermée")

    # ==============================
    # INITIALISATION DES TABLES
    # ==============================
    async def initialize_tables(self):
        if not self._connection:
            raise RuntimeError("DB non connectée")

        schema = """
        BEGIN TRANSACTION;

        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            suggestions_config TEXT,
            feedback_channel_id INTEGER,
            birthday_channel_id INTEGER,
            ticket_config TEXT,
            automod_config TEXT,
            leveling_config TEXT
        );

        CREATE TABLE IF NOT EXISTS temp_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            unban_timestamp REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            marriage_timestamp TEXT NOT NULL,
            UNIQUE (guild_id, user1_id, user2_id)
        );

        CREATE TABLE IF NOT EXISTS prison (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            prison_channel_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL,
            saved_roles TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            money INTEGER DEFAULT 0,
            UNIQUE (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            enabled INTEGER DEFAULT 1,
            required_role TEXT DEFAULT 'member'
        );

        COMMIT;
        """
        try:
            await self._connection.executescript(schema)
            print("✅ Tables initialisées")
        except Exception:
            print("❌ ERREUR création tables")
            traceback.print_exc()

    # ==============================
    # GENERIC METHODS
    # ==============================
    async def execute(self, query: str, params: tuple = ()):
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            await self._connection.commit()

    async def fetch_one(self, query: str, params: tuple = ()):
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: tuple = ()):
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ==============================
    # WARNINGS
    # ==============================
    async def add_warning(self, guild_id, user_id, moderator_id, reason):
        await self.execute(
            "INSERT INTO warnings VALUES (NULL,?,?,?,?,?)",
            (guild_id, user_id, moderator_id, reason, datetime.now(timezone.utc).isoformat())
        )

    async def get_warnings(self, guild_id, user_id):
        return await self.fetch_all(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )

    # ==============================
    # PRISON
    # ==============================
    async def is_prisoner(self, guild_id, user_id):
        return await self.fetch_one(
            "SELECT 1 FROM prison WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ) is not None

    # ==============================
    # USER DATA / LEVELING
    # ==============================
    async def get_user_data(self, guild_id, user_id):
        data = await self.fetch_one(
            "SELECT * FROM user_data WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        if not data:
            await self.execute(
                "INSERT INTO user_data (guild_id,user_id) VALUES (?,?)",
                (guild_id, user_id)
            )
            return await self.get_user_data(guild_id, user_id)
        return data

    async def update_user_xp(self, guild_id, user_id, xp, level):
        await self.execute(
            "UPDATE user_data SET xp=?, level=? WHERE guild_id=? AND user_id=?",
            (xp, level, guild_id, user_id)
        )

    async def get_leaderboard(self, guild_id, limit=10):
        return await self.fetch_all(
            "SELECT user_id, xp, level FROM user_data WHERE guild_id=? ORDER BY level DESC, xp DESC LIMIT ?",
            (guild_id, limit)
        )

    # ==============================
    # COMMANDS (PANEL)
    # ==============================
    async def get_commands(self):
        return await self.fetch_all("SELECT * FROM commands")

    async def toggle_command(self, command_id, enabled):
        await self.execute(
            "UPDATE commands SET enabled=? WHERE id=?",
            (enabled, command_id)
        )


# ==============================
# INSTANCE GLOBALE
# ==============================
db = DatabaseManager(DB_PATH)
