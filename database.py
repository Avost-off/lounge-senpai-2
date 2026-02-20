# utils/database.py
import aiosqlite
import os
import traceback
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

DATA_DIR = "./data"
DB_PATH = os.path.join(DATA_DIR, "database.db")


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON;")
        print("✅ DB Connected")

    async def close(self):
        if self._connection:
            await self._connection.close()

    async def initialize_tables(self):
        schema = """
        BEGIN TRANSACTION;

        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            money INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id)
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
        await self._connection.executescript(schema)
        print("✅ Tables Ready")

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

    async def get_leaderboard(self, guild_id, limit=10):
        return await self.fetch_all(
            "SELECT user_id,xp,level FROM user_data WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT ?",
            (guild_id, limit)
        )

    async def get_commands(self):
        return await self.fetch_all("SELECT * FROM commands")

    async def toggle_command(self, command_id, enabled):
        await self.execute(
            "UPDATE commands SET enabled=? WHERE id=?",
            (enabled, command_id)
        )


db = DatabaseManager(DB_PATH)
