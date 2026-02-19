# utils/database.py
import aiosqlite
import os
import traceback
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

# --- Configuration du chemin de la base de données ---
DATA_DIR = './data'
DB_PATH = os.path.join(DATA_DIR, 'database.db')


class DatabaseManager:
    """
    Gère toutes les interactions avec la base de données SQLite de manière asynchrone.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Établit la connexion à la base de données."""
        """Établit la connexion à la base de données."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
            print(f"Connexion à la base de données '{self.db_path}' réussie.")
            # L'initialisation des tables sera maintenant gérée explicitement depuis main.py
            # L'initialisation des tables sera maintenant gérée explicitement depuis main.py
        except Exception as e:
            print(f"ERREUR CRITIQUE lors de la connexion à la DB : {e}")
            traceback.print_exc()
            self._connection = None
            raise e

    # ==============================================================================
    # --- MODIFICATION 1 : RENOMMAGE ET AJOUT DE LA TABLE ---
    # Renommé en "initialize_tables" pour être plus clair et public.
    async def initialize_tables(self):
    # ==============================================================================
    # ==============================================================================
    # --- MODIFICATION 1 : RENOMMAGE ET AJOUT DE LA TABLE ---
    # Renommé en "initialize_tables" pour être plus clair et public.
        async def initialize_tables(self):
    # ==============================================================================
            """Crée les tables nécessaires si elles n'existent pas."""
        if not self._connection:
            print("ERREUR: Impossible d'initialiser les tables, pas de connexion DB.")
            return

        sql_schema = """
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
            automod_config TEXT
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
            user1_id INTEGER NOT NULL, -- Stocke toujours le plus petit ID
            user2_id INTEGER NOT NULL, -- Stocke toujours le plus grand ID
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
            saved_roles TEXT, -- Sera NULL pour les non-admins
            PRIMARY KEY (guild_id, user_id)
        );

        -- ==============================================================================
        -- MODIFICATION 2 : AJOUT DE LA TABLE MANQUANTE POUR LE LEVELING ET L'ÉCONOMIE
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            money INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id)
        );
        -- ==============================================================================

        -- ==============================================================================
        -- MODIFICATION 2 : AJOUT DE LA TABLE MANQUANTE POUR LE LEVELING ET L'ÉCONOMIE
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            money INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id)
        );
        -- ==============================================================================

        COMMIT;
        """
        try:
            await self._connection.executescript(sql_schema)
            print("Schéma de la base de données complet vérifié/initialisé.")
        except Exception as e:
            print(f"ERREUR lors de l'initialisation des tables : {e}")
            traceback.print_exc()

    async def close(self):
        """Ferme la connexion à la base de données."""
        if self._connection:
            await self._connection.close()
            print("Connexion à la base de données fermée.")

    # --- Méthodes Génériques ---
    async def execute(self, query: str, params: tuple = ()):
        if not self._connection: raise ConnectionError("La base de données n'est pas connectée.")
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            await self._connection.commit()

    async def fetch_one(self, query: str, params: tuple = ()):
        if not self._connection: raise ConnectionError("La base de données n'est pas connectée.")
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: tuple = ()):
        if not self._connection: raise ConnectionError("La base de données n'est pas connectée.")
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Warnings ---
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        query = "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)"
        timestamp_str = datetime.now(timezone.utc).isoformat()
        await self.execute(query, (guild_id, user_id, moderator_id, reason, timestamp_str))

    async def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        query = "SELECT id, moderator_id, reason, timestamp FROM warnings WHERE guild_id = ? AND user_id = ?"
        return await self.fetch_all(query, (guild_id, user_id))

    async def clear_warnings(self, guild_id: int, user_id: int):
        query = "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?"
        await self.execute(query, (guild_id, user_id))

    # --- Bans Temporaires ---
    async def add_temp_ban(self, guild_id: int, user_id: int, unban_timestamp: float):
        query = "INSERT INTO temp_bans (guild_id, user_id, unban_timestamp) VALUES (?, ?, ?)"
        await self.execute(query, (guild_id, user_id, unban_timestamp))

    async def get_expired_bans(self, current_timestamp: float) -> List[Dict]:
        query = "SELECT id, guild_id, user_id FROM temp_bans WHERE unban_timestamp <= ?"
        return await self.fetch_all(query, (current_timestamp,))

    async def remove_temp_ban(self, ban_id: int):
        query = "DELETE FROM temp_bans WHERE id = ?"
        await self.execute(query, (ban_id,))

    # --- Mariages ---
    async def get_partners(self, guild_id: int, user_id: int) -> list:
        query = """
            SELECT user2_id as partner_id FROM marriages WHERE guild_id = ? AND user1_id = ?
            UNION
            SELECT user1_id as partner_id FROM marriages WHERE guild_id = ? AND user2_id = ?
        """
        rows = await self.fetch_all(query, (guild_id, user_id, guild_id, user_id))
        return [row['partner_id'] for row in rows]

    async def are_married(self, guild_id: int, user1_id: int, user2_id: int) -> bool:
        query = "SELECT 1 FROM marriages WHERE guild_id = ? AND user1_id = ? AND user2_id = ?"
        params = (guild_id, min(user1_id, user2_id), max(user1_id, user2_id))
        return await self.fetch_one(query, params) is not None

    async def add_marriage(self, guild_id: int, user1_id: int, user2_id: int):
        query = "INSERT INTO marriages (guild_id, user1_id, user2_id, marriage_timestamp) VALUES (?, ?, ?, ?)"
        timestamp_str = datetime.now(timezone.utc).isoformat()
        await self.execute(query, (guild_id, min(user1_id, user2_id), max(user1_id, user2_id), timestamp_str))

    async def remove_marriage(self, guild_id: int, user1_id: int, user2_id: int):
        query = "DELETE FROM marriages WHERE guild_id = ? AND user1_id = ? AND user2_id = ?"
        params = (guild_id, min(user1_id, user2_id), max(user1_id, user2_id))
        await self.execute(query, params)

    async def remove_all_marriages(self, guild_id: int, user_id: int):
        query = "DELETE FROM marriages WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?)"
        await self.execute(query, (guild_id, user_id, user_id))
        
    # --- Prison ---
    async def add_prisoner(self, guild_id: int, user_id: int, prison_channel_id: int, moderator_id: int, reason: str, saved_roles: Optional[str] = None):
        query = """
            INSERT INTO prison (guild_id, user_id, prison_channel_id, moderator_id, reason, timestamp, saved_roles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                prison_channel_id = excluded.prison_channel_id,
                moderator_id = excluded.moderator_id,
                reason = excluded.reason,
                timestamp = excluded.timestamp,
                saved_roles = excluded.saved_roles
        """
        timestamp_str = datetime.now(timezone.utc).isoformat()
        params = (guild_id, user_id, prison_channel_id, moderator_id, reason, timestamp_str, saved_roles)
        await self.execute(query, params)

    async def get_prisoner_data(self, guild_id: int, user_id: int) -> Optional[Dict]:
        query = "SELECT * FROM prison WHERE guild_id = ? AND user_id = ?"
        return await self.fetch_one(query, (guild_id, user_id))

    async def is_prisoner(self, guild_id: int, user_id: int) -> bool:
        query = "SELECT 1 FROM prison WHERE guild_id = ? AND user_id = ?"
        return await self.fetch_one(query, (guild_id, user_id)) is not None

    async def remove_prisoner(self, guild_id: int, user_id: int):
        query = "DELETE FROM prison WHERE guild_id = ? AND user_id = ?"
        await self.execute(query, (guild_id, user_id))

    # --- Guild Settings ---
    async def get_guild_settings(self, guild_id: int) -> Optional[Dict]:
        query = "SELECT * FROM guild_settings WHERE guild_id = ?"
        settings = await self.fetch_one(query, (guild_id,))
        if settings:
            for key in ["suggestions_config", "ticket_config", "automod_config"]:
                if settings.get(key) and isinstance(settings[key], str):
                    try:
                        settings[key] = json.loads(settings[key])
                    except json.JSONDecodeError:
                        settings[key] = {}
        return settings
        
    async def update_guild_setting(self, guild_id: int, key: str, value: Any):
        if isinstance(value, dict):
            value = json.dumps(value)
        query = f"""
            INSERT INTO guild_settings (guild_id, {key})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {key} = excluded.{key}
        """
        await self.execute(query, (guild_id, value))

    # --- Méthodes pour le Leveling et les Données Utilisateur ---
    async def get_user_data(self, guild_id: int, user_id: int) -> Dict:
        """
        Récupère les données d'un utilisateur (xp, balance, etc.).
        Si l'utilisateur n'existe pas, une entrée est créée et retournée.
        """
        query = "SELECT * FROM user_data WHERE guild_id = ? AND user_id = ?"
        user_data = await self.fetch_one(query, (guild_id, user_id))

        if not user_data:
            insert_query = "INSERT OR IGNORE INTO user_data (guild_id, user_id) VALUES (?, ?)"
            insert_query = "INSERT OR IGNORE INTO user_data (guild_id, user_id) VALUES (?, ?)"
            await self.execute(insert_query, (guild_id, user_id))
            return await self.fetch_one(query, (guild_id, user_id))
            return await self.fetch_one(query, (guild_id, user_id))
        
        return user_data

    async def update_user_xp(self, guild_id: int, user_id: int, new_xp: int, new_level: int):
        """Met à jour l'XP et le niveau d'un utilisateur."""
        query = """
            UPDATE user_data SET xp = ?, level = ?
            WHERE guild_id = ? AND user_id = ?
            UPDATE user_data SET xp = ?, level = ?
            WHERE guild_id = ? AND user_id = ?
        """
        await self.execute(query, (new_xp, new_level, guild_id, user_id))
        await self.execute(query, (new_xp, new_level, guild_id, user_id))
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Récupère le classement des utilisateurs par XP."""
        query = """
            SELECT user_id, xp, level 
            FROM user_data 
            WHERE guild_id = ? 
            ORDER BY level DESC, xp DESC 
            ORDER BY level DESC, xp DESC 
            LIMIT ?
        """
        return await self.fetch_all(query, (guild_id, limit))
    
# --- Instance Globale ---
# La bonne pratique est de créer cette instance uniquement dans main.py.
# Je la laisse ici car vous avez demandé de ne pas modifier la structure existante.
# La bonne pratique est de créer cette instance uniquement dans main.py.
# Je la laisse ici car vous avez demandé de ne pas modifier la structure existante.
db = DatabaseManager(db_path=DB_PATH)
