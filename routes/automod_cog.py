# cogs/automod_cog.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, List, Dict, Literal
import json
import os
import re
import time
import datetime
import traceback
from collections import defaultdict

# --- Fonctions Helper (inchangées) ---
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
        with open(temp_filepath, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
        os.replace(temp_filepath, filepath)
    except Exception as e:
        print(f"Erreur critique sauvegarde {filepath}: {e}"); traceback.print_exc()

# --- Constantes (inchangées) ---
DATA_DIR = './data'
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
SPAM_TIMEFRAME = 10
SPAM_MESSAGE_COUNT = 5

# --- Classe Cog ---
class AutoModCog(commands.Cog, name="Auto-Modération"):
    def __init__(self, bot: commands.Bot, db_manager):
        self.bot = bot
        self.db = db_manager
        self.settings = load_data(SETTINGS_FILE) 
        self.spam_tracker = defaultdict(lambda: defaultdict(list))
        self.check_unbans_loop.start()

    def cog_unload(self):
        self.check_unbans_loop.cancel()

    @tasks.loop(minutes=5)
    async def check_unbans_loop(self):
        # ... (votre code de boucle reste inchangé)
        try:
            current_time = time.time()
            expired_bans = await self.db.get_expired_bans(current_time)
            if not expired_bans: return
            print(f"Trouvé {len(expired_bans)} ban(s) expiré(s) à traiter.")
            for ban in expired_bans:
                ban_id, guild_id, user_id = ban['id'], ban['guild_id'], ban['user_id']
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await self.db.remove_temp_ban(ban_id); continue
                try:
                    user_to_unban = discord.Object(id=user_id)
                    await guild.unban(user_to_unban, reason="Le ban temporaire a expiré.")
                    await self.db.remove_temp_ban(ban_id)
                    print(f"UNBAN AUTO: Utilisateur {user_id} débanni de {guild.name}.")
                except discord.NotFound: await self.db.remove_temp_ban(ban_id)
                except discord.Forbidden: print(f"ERREUR UNBAN: Permissions manquantes pour débannir {user_id} de {guild.name}.")
                except Exception as e: print(f"ERREUR UNBAN inattendue pour {user_id} sur {guild.name}: {e}")
        except Exception as e:
            if isinstance(e, ConnectionError):
                print(f"ERREUR CRITIQUE dans la boucle check_unbans_loop: {e}")
            else:
                print(f"ERREUR CRITIQUE dans la boucle check_unbans_loop: {e}"); traceback.print_exc()

    @check_unbans_loop.before_loop
    async def before_check_unbans_loop(self):
        # ... (votre code before_loop reste inchangé)
        print("La boucle 'check_unbans_loop' attend que le bot soit prêt...")
        await self.bot.wait_until_ready()
        print("Bot prêt. La boucle 'check_unbans_loop' démarre.")

    # ==============================================================================
    # --- CORRECTION 1 : Implémentation de la fonction manquante ---
    def get_guild_automod_config(self, guild_id: int) -> dict:
        """Récupère la configuration de l'automod pour un serveur spécifique."""
        guild_settings = self.settings.setdefault(str(guild_id), {})
        automod_config = guild_settings.setdefault("automod_config", {})
        return automod_config
    # ==============================================================================

    # --- Commandes de Configuration ---
    automod_group = app_commands.Group(name="automod", description="Configure le système d'avertissement automatique.")

    @automod_group.command(name="sanctions", description="Définit les seuils de sanction de l'automod.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        seuil_timeout="Nombre de warns avant un timeout (0=désactivé).",
        duree_timeout_minutes="Durée en minutes du timeout.",
        seuil_ban_temporaire="Nombre de warns avant un ban temporaire (0=désactivé).",
        duree_ban_temporaire_jours="Durée en jours du ban temporaire.",
        seuil_ban_permanent="Nombre de warns avant un ban permanent (0=désactivé)."
    )
    async def automod_sanctions(self, interaction: discord.Interaction,
                                seuil_timeout: app_commands.Range[int, 0, 100],
                                duree_timeout_minutes: app_commands.Range[int, 1, 40320],
                                seuil_ban_temporaire: app_commands.Range[int, 0, 100],
                                duree_ban_temporaire_jours: app_commands.Range[int, 1, 365],
                                seuil_ban_permanent: app_commands.Range[int, 0, 100]):
        
        # ==============================================================================
        # --- CORRECTION 2 : Application du pattern "pare-balles" ---
        await interaction.response.defer(ephemeral=True)

        try:
            config = self.get_guild_automod_config(interaction.guild.id)
            config["timeout_threshold"] = seuil_timeout
            config["timeout_duration_minutes"] = duree_timeout_minutes
            config["temp_ban_threshold"] = seuil_ban_temporaire
            config["temp_ban_duration_days"] = duree_ban_temporaire_jours
            config["perm_ban_threshold"] = seuil_ban_permanent
            save_data(SETTINGS_FILE, self.settings)

            embed = discord.Embed(title="⚙️ Sanctions AutoMod Mises à Jour", color=discord.Color.blue())
            embed.add_field(name="Timeout", value=f"{seuil_timeout} warns → {duree_timeout_minutes} min" if seuil_timeout > 0 else "Désactivé", inline=False)
            embed.add_field(name="Ban Temporaire", value=f"{seuil_ban_temporaire} warns → {duree_ban_temporaire_jours} jour(s)" if seuil_ban_temporaire > 0 else "Désactivé", inline=False)
            embed.add_field(name="Ban Permanent", value=f"{seuil_ban_permanent} warns" if seuil_ban_permanent > 0 else "Désactivé", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"--- ERREUR DANS /automod sanctions ---")
            traceback.print_exc()
            try:
                await interaction.followup.send("❌ Une erreur interne est survenue. L'administrateur a été notifié.", ephemeral=True)
            except discord.HTTPException:
                pass
        # ==============================================================================

    # ... (vos autres commandes, listeners et fonctions de gestion restent inchangés) ...
    # =============================================
    # ==          LISTENER ON_MESSAGE            ==
    # =============================================
    @commands.Cog.listener("on_message")
    async def on_automod_message(self, message: discord.Message):
        # ... (votre code inchangé)
        pass

    @commands.Cog.listener("on_message_edit")
    async def on_automod_edit(self, before: discord.Message, after: discord.Message):
        await self.on_automod_message(after)

    # --- Fonctions de Gestion ---
    async def _handle_nsfw_content(self, message: discord.Message, config: dict):
        # ... (votre code inchangé)
        pass

    async def apply_sanction(self, guild: discord.Guild, author: discord.Member, bot_user, reason: str):
        # ... (votre code inchangé)
        pass
    
# --- Setup du Cog (inchangé) ---
async def setup(bot: commands.Bot):
    if not hasattr(bot, 'db'):
        print("ERREUR CRITIQUE (automod_cog.py): L'objet bot n'a pas d'attribut 'db'. Assurez-vous qu'il est défini dans main.py.")
        return
    await bot.add_cog(AutoModCog(bot, bot.db))
