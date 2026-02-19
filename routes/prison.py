# cogs/prison.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict
import asyncio
import traceback
from datetime import datetime, timezone
import time
import json # <-- Ajout de l'import json

# --- Dépendances ---
from utils.database import db

# --- Constantes ---
PRISONER_ROLE_NAME = "Prisonnier"

# --- Classe Cog -----
class PrisonCog(commands.Cog, name="Système Prison"):
    def __init__(self, bot: commands.Bot, db_manager):
        self.bot = bot
        self.db = db_manager

    async def get_or_create_prisoner_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Trouve le rôle 'Prisonnier' ou le crée s'il n'existe pas."""
        # Chercher le rôle
        role = discord.utils.get(guild.roles, name=PRISONER_ROLE_NAME)
        if role:
            return role
        
        # S'il n'existe pas, le créer
        try:
            # Créer un rôle sans aucune permission
            no_perms = discord.Permissions.none()
            new_role = await guild.create_role(
                name=PRISONER_ROLE_NAME,
                permissions=no_perms,
                reason="Création du rôle pour le système de prison"
            )
            # Parcourir tous les canaux pour refuser explicitement la vue
            for channel in guild.channels:
                try:
                    await channel.set_permissions(new_role, view_channel=False, reason="Configuration du rôle Prisonnier")
                except discord.Forbidden:
                    print(f"PRISON SETUP: Impossible de configurer les perms pour le rôle Prisonnier dans #{channel.name}")
            return new_role
        except discord.Forbidden:
            print("PRISON SETUP: Impossible de créer le rôle Prisonnier.")
            return None
        except Exception as e:
            print(f"Erreur création rôle prisonnier: {e}"); traceback.print_exc(); return None

    @app_commands.command(name="prison", description="Envoie un membre en prison.")
    @app_commands.checks.has_permissions(administrator=True) # Requiert admin pour une action si disruptive
    @app_commands.checks.bot_has_permissions(manage_roles=True, manage_channels=True)
    @app_commands.describe(membre="Le membre à emprisonner.", prison_channel="Le salon qui servira de prison.", raison="Raison de l'emprisonnement.")
    async def prison_command(self, interaction: discord.Interaction,
                             membre: discord.Member,
                             prison_channel: discord.TextChannel,
                             raison: str = "Mis en prison par la modération."):
        
        guild = interaction.guild
        if membre == interaction.user or membre == self.bot.user:
            await interaction.response.send_message("❌ Action non autorisée.", ephemeral=True); return
        if membre.top_role >= interaction.user.top_role and interaction.user != guild.owner:
            await interaction.response.send_message("❌ Vous ne pouvez pas emprisonner un membre de rang égal ou supérieur.", ephemeral=True); return
        if membre.top_role >= guild.me.top_role:
            await interaction.response.send_message("❌ Ma hiérarchie de rôle est trop basse pour cette action.", ephemeral=True); return

        await interaction.response.defer(thinking=True, ephemeral=True)
        
        # 1. Obtenir/Créer le rôle Prisonnier
        prisoner_role = await self.get_or_create_prisoner_role(guild)
        if not prisoner_role:
            await interaction.followup.send("❌ Erreur critique : Impossible de créer ou trouver le rôle 'Prisonnier'.", ephemeral=True); return
            
        # Configurer les permissions du rôle prisonnier pour le canal prison
        try:
            await prison_channel.set_permissions(prisoner_role, view_channel=True, read_message_history=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Erreur: Je n'ai pas pu configurer les permissions pour le rôle prisonnier dans {prison_channel.mention}.", ephemeral=True); return

        is_admin = membre.guild_permissions.administrator
        saved_roles_json = None
        
        # 2. Gérer le cas Admin (mise en pause des rôles)
        if is_admin:
            # Sauvegarder tous les rôles SAUF @everyone
            roles_to_save = [role.id for role in membre.roles if role.name != "@everyone"]
            saved_roles_json = json.dumps(roles_to_save)
            
            try:
                # Retirer tous les rôles et ajouter le rôle prisonnier
                await membre.edit(roles=[prisoner_role], reason=f"Mis en prison (Admin) par {interaction.user}")
            except discord.Forbidden:
                await interaction.followup.send("❌ Je n'ai pas la permission de modifier les rôles de cet administrateur.", ephemeral=True); return
        else:
            # 3. Gérer le cas Non-Admin (ajout simple du rôle)
            try:
                await membre.add_roles(prisoner_role, reason=f"Mis en prison par {interaction.user}")
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Je n'ai pas la permission d'ajouter des rôles à {membre.mention}.", ephemeral=True); return

        # 4. Enregistrer dans la base de données
        await self.db.add_prisoner(guild.id, membre.id, prison_channel.id, interaction.user.id, raison, saved_roles_json)

        await interaction.followup.send(f"✅ **{membre.display_name}** a été emprisonné avec succès.", ephemeral=True)
        
        log_embed = discord.Embed(
            title="⚖️ Membre Emprisonné",
            description=f"{membre.mention} a été mis en prison par {interaction.user.mention}.",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        ).add_field(name="Raison", value=raison)
        if is_admin:
            log_embed.add_field(name="⚠️ Statut", value="Administrateur mis en pause. Rôles sauvegardés.", inline=False)
        try:
            if interaction.channel: await interaction.channel.send(embed=log_embed)
        except discord.Forbidden: pass

    @app_commands.command(name="unprison", description="Libère un membre de prison.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.checks.bot_has_permissions(manage_roles=True)
    @app_commands.describe(membre="Le membre à libérer.", raison="Raison de la libération.")
    async def unprison_command(self, interaction: discord.Interaction,
                               membre: discord.Member,
                               raison: str = "Libéré de prison par la modération."):

        prisoner_data = await self.db.get_prisoner_data(interaction.guild.id, membre.id)
        if not prisoner_data:
            await interaction.response.send_message("ℹ️ Ce membre n'est pas dans la base de données de la prison.", ephemeral=True); return

        await interaction.response.defer(thinking=True, ephemeral=True)

        prisoner_role = discord.utils.get(interaction.guild.roles, name=PRISONER_ROLE_NAME)
        
        saved_roles_json = prisoner_data.get("saved_roles")
        
        # 1. Gérer la restauration des rôles pour un admin
        if saved_roles_json:
            try:
                role_ids_to_restore = json.loads(saved_roles_json)
                roles_to_restore = [interaction.guild.get_role(rid) for rid in role_ids_to_restore if interaction.guild.get_role(rid) is not None]
                
                # Vérifier si on peut bien assigner tous les rôles
                if any(r >= interaction.guild.me.top_role for r in roles_to_restore):
                    await interaction.followup.send("❌ Erreur: Un des rôles sauvegardés est plus haut que le mien. Restauration manuelle requise.", ephemeral=True); return
                
                await membre.edit(roles=roles_to_restore, reason=f"Libéré de prison (Admin) par {interaction.user}")
            except json.JSONDecodeError:
                await interaction.followup.send("❌ Erreur critique: Impossible de lire les rôles sauvegardés. Restauration manuelle requise !", ephemeral=True); return
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Je n'ai pas la permission de restaurer les rôles de {membre.mention}.", ephemeral=True); return
        
        # 2. Gérer le cas non-admin (simple retrait du rôle)
        else:
            if prisoner_role and prisoner_role in membre.roles:
                try:
                    await membre.remove_roles(prisoner_role, reason=f"Libéré de prison par {interaction.user}")
                except discord.Forbidden:
                    await interaction.followup.send(f"❌ Je n'ai pas la permission de retirer le rôle Prisonnier de {membre.mention}.", ephemeral=True); return
        
        # 3. Nettoyer la base de données
        await self.db.remove_prisoner(interaction.guild.id, membre.id)
        
        await interaction.followup.send(f"✅ **{membre.display_name}** a été libéré avec succès.", ephemeral=True)
        
        log_embed = discord.Embed(
            title="⚖️ Membre Libéré",
            description=f"{membre.mention} a été libéré par {interaction.user.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        ).add_field(name="Raison", value=raison)
        try:
            if interaction.channel: await interaction.channel.send(embed=log_embed)
        except discord.Forbidden: pass
        # =============================================
        #==           SETUP DU COG                  ==
        # =============================================
# C'EST CE BLOC QUI EST MANQUANT OU MAL ÉCRIT
async def setup(bot: commands.Bot):
    # 'bot' ici est l'instance de votre classe MyBot
    # Dans le __init__ de MyBot, vous avez fait self.db = db
    # Donc, bot.db est maintenant accessible ici.
    if not hasattr(bot, 'db'):
        print("ERREUR CRITIQUE (prison.py): L'objet bot n'a pas d'attribut 'db'. Assurez-vous qu'il est défini dans main.py.")
        return

    # On passe l'instance de la base de données du bot au Cog lors de son initialisation
    await bot.add_cog(PrisonCog(bot, bot.db))
    print("Cog Prison chargé.")