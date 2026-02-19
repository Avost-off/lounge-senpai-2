# cogs/economie_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict
import json
import os
import traceback
import datetime
import random
import time

# --- Constantes ---
DATA_DIR = './data'
# CORRECTION : Utiliser une seule constante pour le fichier de config principal.
# Le Cog économie lira la section "economy_config" de ce fichier.
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
USER_BALANCES_FILE = os.path.join(DATA_DIR, 'user_balances.json')
DAILY_COOLDOWN_HOURS = 22

# --- Fonctions Helper JSON ---
def load_data(filepath):
    """Charge les données depuis un fichier JSON, le crée s'il manque."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(filepath, 'w', encoding='utf-8') as f: json.dump({}, f)
        return {}
    except Exception as e:
        print(f"Erreur chargement {filepath}: {e}"); traceback.print_exc(); return {}

def save_data(filepath, data):
    """Sauvegarde les données dans un fichier JSON de manière atomique."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_filepath, filepath)
    except Exception as e:
        print(f"Erreur critique sauvegarde {filepath}: {e}"); traceback.print_exc()


# --- Classe Cog ---
class EconomieCog(commands.Cog, name="Économie"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # CORRECTION : Charger les bons fichiers avec les bons noms
        self.settings = load_data(SETTINGS_FILE)
        self.user_balances = load_data(USER_BALANCES_FILE)

    # CORRECTION : Implémentation des fonctions helper internes
    def get_guild_config(self, guild_id: int) -> dict:
        """Récupère ou initialise la config économie depuis le fichier settings global."""
        guild_id_str = str(guild_id)
        guild_settings = self.settings.setdefault(guild_id_str, {})
        eco_config = guild_settings.setdefault("economy_config", {
            "currency_name": "Points",
            "currency_emoji": "💰",
            "daily_min": 50,
            "daily_max": 250
        })
        return eco_config
    
    def get_user_data(self, guild_id: int, user_id: int) -> dict:
        """Récupère ou initialise les données d'un utilisateur."""
        guild_id_str = str(guild_id)
        user_id_str = str(user_id)
        
        guild_balances = self.user_balances.setdefault(guild_id_str, {})
        user_data = guild_balances.setdefault(user_id_str, {
            "balance": 0,
            "inventory": [],
            "last_daily": None
        })
        
        # S'assurer que toutes les clés par défaut existent pour l'utilisateur
        user_data.setdefault("balance", 0)
        user_data.setdefault("inventory", [])
        user_data.setdefault("last_daily", None)
        
        return user_data

    # =============================================
    # ==        GROUPE COMMANDES ÉCONOMIE        ==
    # =============================================
    economie_group = app_commands.Group(name="economie", description="Commandes liées à l'économie du serveur.")

    @economie_group.command(name="solde", description="Affiche votre solde ou celui d'un autre membre.")
    @app_commands.describe(membre="Le membre dont voir le solde (optionnel).")
    async def economie_solde(self, interaction: discord.Interaction, membre: Optional[discord.Member] = None):
        target_user = membre or interaction.user
        if target_user.bot:
            await interaction.response.send_message("❌ Les bots n'ont pas de solde.", ephemeral=True); return

        user_data = self.get_user_data(interaction.guild.id, target_user.id)
        config = self.get_guild_config(interaction.guild.id)
        embed = discord.Embed(
            title=f"💰 Solde de {target_user.display_name}",
            description=f"{user_data.get('balance', 0)} {config.get('currency_emoji', '💰')} {config.get('currency_name', 'Points')}",
            color=discord.Color.gold()
        ).set_thumbnail(url=target_user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @economie_group.command(name="classement", description="Affiche le classement des membres les plus riches.")
    async def economie_classement(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Recharger les données pour avoir le classement le plus récent
        self.user_balances = load_data(USER_BALANCES_FILE)
        
        guild_balances = self.user_balances.get(str(interaction.guild.id), {})
        config = self.get_guild_config(interaction.guild.id)
        if not guild_balances:
            await interaction.followup.send("ℹ️ Personne n'a encore de monnaie.", ephemeral=True); return

        sorted_users = sorted(guild_balances.items(), key=lambda item: item[1].get("balance", 0), reverse=True)
        
        embed = discord.Embed(
            title=f"🏆 Classement - {config.get('currency_name', 'Points')}",
            color=discord.Color.gold()
        )
        description = ""
        for i, (user_id_str, data) in enumerate(sorted_users[:10]):
            balance = data.get('balance', 0)
            description += f"**{i+1}.** <@{user_id_str}> - {balance} {config.get('currency_emoji', '💰')}\n"
        
        embed.description = description if description else "Aucune donnée."
        await interaction.followup.send(embed=embed)


    @app_commands.command(name="daily", description="Récupère votre récompense quotidienne.")
    async def daily_claim(self, interaction: discord.Interaction):
        config = self.get_guild_config(interaction.guild.id)
        user_data = self.get_user_data(interaction.guild.id, interaction.user.id)
        
        last_daily_str = user_data.get("last_daily")
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        if last_daily_str:
            try:
                last_daily_dt = datetime.datetime.fromisoformat(last_daily_str)
                time_since = now_utc - last_daily_dt
                if time_since.total_seconds() < DAILY_COOLDOWN_HOURS * 3600:
                    remaining = datetime.timedelta(seconds=(DAILY_COOLDOWN_HOURS * 3600) - time_since.total_seconds())
                    next_claim = discord.utils.format_dt(now_utc + remaining, style='R')
                    await interaction.response.send_message(f"⏳ Prochain daily disponible {next_claim}.", ephemeral=True); return
            except ValueError:
                print(f"WARN: Format de date invalide pour last_daily de {interaction.user.id}")
        
        min_amount = config.get("daily_min", 50)
        max_amount = config.get("daily_max", 250)
        if max_amount <= min_amount: max_amount = min_amount + 1 
        amount_won = random.randint(min_amount, max_amount)
        
        user_data["balance"] = user_data.get("balance", 0) + amount_won
        user_data["last_daily"] = now_utc.isoformat()
        save_data(USER_BALANCES_FILE, self.user_balances)
        
        await interaction.response.send_message(f"🎉 Vous avez gagné **{amount_won}** {config.get('currency_emoji', '💰')} !")

# --- Setup du Cog ---
async def setup(bot: commands.Bot):
    await bot.add_cog(EconomieCog(bot))
    print("Cog Économie (corrigé) chargé.")