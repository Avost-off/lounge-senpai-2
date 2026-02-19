# cogs/config_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import json
import os
import traceback

# --- Constantes et Helpers ---
DATA_DIR = './data'
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# Helper pour les types de logs, si vous avez une commande de config pour ça
LogType = Literal[
    "joins", "leaves", "message_edit", "message_delete",
    "mod_actions", "voice_state", "channel_updates", "role_updates", "member_update"
]

def load_data(filepath):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(filepath, 'w', encoding='utf-8') as f: json.dump({}, f)
        return {}
    except Exception as e:
        print(f"Erreur chargement {filepath}: {e}"); traceback.print_exc(); return {}

def save_data(filepath, data):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_filepath, filepath)
    except Exception as e:
        print(f"Erreur critique sauvegarde {filepath}: {e}"); traceback.print_exc()

# ----- Classe Cog -----
class ConfigCog(commands.Cog, name="Configuration"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = load_data(SETTINGS_FILE)

    def get_guild_settings(self, guild_id: int) -> dict:
        guild_id_str = str(guild_id)
        guild_data = self.settings.setdefault(guild_id_str, {})
        # S'assurer que toutes les sous-sections de config existent pour éviter les erreurs
        guild_data.setdefault("suggestions_config", {})
        guild_data.setdefault("ticket_config", {})
        guild_data.setdefault("boost_config", {})
        guild_data.setdefault("log_config", {})
        guild_data.setdefault("automod_config", {})
        guild_data.setdefault("economy_config", {})
        guild_data.setdefault("shop_config", {})
        guild_data.setdefault("leveling_config", {})
        return guild_data
    
    # =============================================
    # ==      GROUPE DE COMMANDES PRINCIPAL      ==
    # =============================================
    config_group = app_commands.Group(
        name="config",
        description="Configure les différents modules du bot.",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    # =============================================
    # ==    /config suggestions                  ==
    # =============================================
    @config_group.command(name="suggestions", description="Configure le système de suggestions.")
    @app_commands.describe(
        canal_suggestions="Canal où les membres postent leurs idées.",
        canal_approuvees="Canal pour les suggestions acceptées.",
        canal_refusees="Canal pour les suggestions refusées."
    )
    async def config_suggestions(self, interaction: discord.Interaction,
                                 canal_suggestions: discord.TextChannel,
                                 canal_approuvees: discord.TextChannel,
                                 canal_refusees: discord.TextChannel):
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["suggestions_config"]
        config["suggestion_channel"] = canal_suggestions.id
        config["review_channel"] = canal_suggestions.id
        config["approved_channel"] = canal_approuvees.id
        config["refused_channel"] = canal_refusees.id
        save_data(SETTINGS_FILE, self.settings)
        await interaction.response.send_message("✅ Configuration des suggestions mise à jour !", ephemeral=True)

    # =============================================
    # ==    /config tickets                      ==
    # =============================================
    @config_group.command(name="tickets", description="Configure le système de tickets.")
    @app_commands.describe(
        categorie="La catégorie où les tickets seront créés.",
        role_support="Le rôle qui aura accès aux tickets."
    )
    async def config_tickets(self, interaction: discord.Interaction,
                             categorie: discord.CategoryChannel,
                             role_support: discord.Role):
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["ticket_config"]
        config["ticket_category_id"] = categorie.id
        config["support_role_id"] = role_support.id
        save_data(SETTINGS_FILE, self.settings)
        await interaction.response.send_message("✅ Configuration des tickets mise à jour !", ephemeral=True)

    # =============================================
    # ==    /config economie (Sous-groupe)       ==
    # =============================================
    economie_subgroup = app_commands.Group(name="economie", description="Configure le système économique.", parent=config_group)
    
    @economie_subgroup.command(name="monnaie", description="Définit le nom et l'emoji de la monnaie.")
    @app_commands.describe(nom="Le nom de la monnaie (ex: Points).", emoji="L'emoji de la monnaie (ex: 💰).")
    async def config_economie_monnaie(self, interaction: discord.Interaction, nom: str, emoji: Optional[str] = "💰"):
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["economy_config"]
        config["currency_name"] = nom
        config["currency_emoji"] = emoji
        save_data(SETTINGS_FILE, self.settings)
        await interaction.response.send_message(f"✅ Monnaie configurée : {emoji} {nom}", ephemeral=True)
        
    @economie_subgroup.command(name="daily", description="Configure les gains de la récompense quotidienne.")
    @app_commands.describe(minimum="Montant minimum que l'on peut gagner.", maximum="Montant maximum que l'on peut gagner.")
    async def config_economie_daily(self, interaction: discord.Interaction, minimum: int, maximum: int):
        if minimum >= maximum:
            await interaction.response.send_message("❌ Le minimum doit être inférieur au maximum.", ephemeral=True); return
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["economy_config"]
        config["daily_min"] = minimum
        config["daily_max"] = maximum
        save_data(SETTINGS_FILE, self.settings)
        await interaction.response.send_message(f"✅ Daily configuré pour donner entre {minimum} et {maximum}.", ephemeral=True)

    # =============================================
    # ==    /config leveling                     ==
    # =============================================
    @config_group.command(name="leveling", description="Configure le système de niveaux et d'XP.")
    @app_commands.describe(
        activer="Activer ou désactiver le gain d'XP sur le serveur.",
        message_level_up="Message affiché lors d'une montée de niveau. Utilisez {user} et {level}."
    )
    async def config_leveling(self, interaction: discord.Interaction, activer: bool, message_level_up: Optional[str] = None):
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["leveling_config"]
        config["activated"] = activer
        if message_level_up:
            config["level_up_message"] = message_level_up
        
        save_data(SETTINGS_FILE, self.settings)
        
        status = "✅ Système de niveaux activé." if activer else "❌ Système de niveaux désactivé."
        if message_level_up:
            status += f"\nMessage de level up mis à jour."
        await interaction.response.send_message(status, ephemeral=True)

    # =============================================
    # ==    /config shop                         ==
    # =============================================
    @config_group.command(name="shop", description="Configure le canal d'affichage de la boutique.")
    @app_commands.describe(canal="Le canal où la commande /boutique voir affichera les articles.")
    async def config_shop(self, interaction: discord.Interaction, canal: discord.TextChannel):
        guild_settings = self.get_guild_settings(interaction.guild.id)
        config = guild_settings["shop_config"]
        config["shop_channel_id"] = canal.id
        save_data(SETTINGS_FILE, self.settings)
        await interaction.response.send_message(f"✅ Le canal de la boutique a été défini sur {canal.mention}.", ephemeral=True)

# =============================================
# ==           SETUP DU COG                  ==
# =============================================
async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
    print("Cog Configuration (centralisé) chargé.")