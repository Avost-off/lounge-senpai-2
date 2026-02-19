# cogs/suggestions_tickets_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import traceback
import datetime
from typing import Optional
import io

# --- Fonctions Helper (inchangées) ---
DATA_DIR = './data'
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

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

# --- Vues Persistantes (inchangées) ---
class TicketPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✉️ Créer un Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_persistent")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button): pass

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="close_ticket_persistent")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button): pass

# --- Classe Cog ---
class SuggestionsTicketsCog(commands.Cog, name="Suggestions & Tickets"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = load_data(SETTINGS_FILE)
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketCloseView())

    def get_guild_settings(self, guild_id: int) -> dict:
        guild_id_str = str(guild_id)
        guild_data = self.settings.setdefault(guild_id_str, {})
        guild_data.setdefault("suggestions_config", {})
        guild_data.setdefault("ticket_config", {})
        return guild_data

    # --- Groupe de commandes SUGGESTIONS (inchangé) ---
    suggestions_group = app_commands.Group(name="suggestions", description="Commandes liées aux suggestions.")
    # ... (votre code pour les suggestions reste ici)

    # --- Groupe de commandes TICKETS ---
    ticket_group = app_commands.Group(name="ticket", description="Commandes pour le système de tickets.")
    
    @ticket_group.command(name="config", description="[Admin] Configure la catégorie et le rôle pour les tickets.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_config(self, interaction: discord.Interaction, categorie: discord.CategoryChannel, role_support: discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_settings = self.get_guild_settings(interaction.guild.id)
            config = guild_settings["ticket_config"]
            config["ticket_category_id"] = categorie.id
            config["support_role_id"] = role_support.id
            save_data(SETTINGS_FILE, self.settings)

            await interaction.followup.send(
                f"✅ Configuration des tickets enregistrée !\n"
                f"- **Catégorie :** `{categorie.name}`\n"
                f"- **Rôle Support :** `{role_support.name}`",
                ephemeral=True
            )
        except Exception as e:
            print(f"--- ERREUR DANS /ticket config ---"); traceback.print_exc()
            await interaction.followup.send("❌ Une erreur interne est survenue. Vérifiez la console.", ephemeral=True)

    @ticket_group.command(name="setup", description="[Admin] Affiche le panneau de création de tickets dans un salon.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        try:
            guild_settings = self.get_guild_settings(interaction.guild.id)
            config = guild_settings.get("ticket_config", {})
            
            if not config.get("ticket_category_id") or not config.get("support_role_id"):
                return await interaction.followup.send("❌ Veuillez d'abord configurer le système avec `/ticket config`.", ephemeral=True)

            embed = discord.Embed(title="Support & Aide", description="Besoin d'aide ? Cliquez sur le bouton ci-dessous pour ouvrir un ticket privé avec le staff.", color=discord.Color.blurple())
            await salon.send(embed=embed, view=TicketPanelView())
            await interaction.followup.send(f"✅ Panneau de tickets posté dans {salon.mention}.", ephemeral=True)
        except Exception as e:
            print(f"--- ERREUR DANS /ticket setup ---"); traceback.print_exc()
            await interaction.followup.send("❌ Une erreur interne est survenue. Vérifiez la console.", ephemeral=True)

    @commands.Cog.listener("on_interaction")
    async def on_ticket_interaction(self, interaction: discord.Interaction):
        if not (interaction.type == discord.InteractionType.component and interaction.data): return
        custom_id = interaction.data.get("custom_id")
        if custom_id == "create_ticket_persistent":
            await self.handle_create_ticket(interaction)
        elif custom_id == "close_ticket_persistent":
            await self.handle_close_ticket(interaction)

    async def handle_create_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # ==============================================================================
        # --- CORRECTION APPLIQUÉE ICI ---
        try:
            self.settings = load_data(SETTINGS_FILE)
            guild_settings = self.get_guild_settings(interaction.guild.id)
            config = guild_settings.get("ticket_config", {})
            category_id = config.get("ticket_category_id")
            support_role_id = config.get("support_role_id")
            
            if not category_id or not support_role_id:
                return await interaction.followup.send("❌ Le système de tickets n'a pas été configuré par un admin.", ephemeral=True)

            category = interaction.guild.get_channel(category_id)
            support_role = interaction.guild.get_role(support_role_id)
            
            if not category or not isinstance(category, discord.CategoryChannel):
                return await interaction.followup.send("❌ **Erreur Admin :** La catégorie pour les tickets est invalide ou a été supprimée. Veuillez reconfigurer avec `/ticket config`.", ephemeral=True)
            if not support_role:
                 return await interaction.followup.send("❌ **Erreur Admin :** Le rôle de support est invalide ou a été supprimé. Veuillez reconfigurer avec `/ticket config`.", ephemeral=True)

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            channel = await category.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
            embed = discord.Embed(title=f"Ticket de {interaction.user.display_name}", description="Veuillez décrire votre problème. Le staff vous répondra bientôt.", color=discord.Color.green())
            await channel.send(content=f"{interaction.user.mention} {support_role.mention}", embed=embed, view=TicketCloseView())
            await interaction.followup.send(f"✅ Ticket créé : {channel.mention}", ephemeral=True)
        except Exception as e:
            print(f"--- ERREUR CRITIQUE DANS handle_create_ticket ---"); traceback.print_exc()
            try:
                await interaction.followup.send("❌ Une erreur interne est survenue lors de la création du ticket.", ephemeral=True)
            except discord.HTTPException: pass
        # ==============================================================================

    async def handle_close_ticket(self, interaction: discord.Interaction):
        # ... (votre code de fermeture reste inchangé)
        # Mais il est bon de le protéger aussi
        try:
            # La réponse doit être faite avant toute opération potentiellement lente
            await interaction.response.defer(ephemeral=True)
            
            self.settings = load_data(SETTINGS_FILE)
            guild_settings = self.get_guild_settings(interaction.guild.id)
            config = guild_settings.get("ticket_config", {})
            support_role = interaction.guild.get_role(config.get("support_role_id"))
            
            if support_role and support_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
                return await interaction.followup.send("❌ Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)

            await interaction.followup.send("🔒 Fermeture du ticket en cours...", ephemeral=True)
            
            transcript_messages = [f"Transcript du ticket #{interaction.channel.name}\n\n"]
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                transcript_messages.append(f"[{message.created_at.strftime('%H:%M:%S')}] {message.author}: {message.content}\n")
            transcript_file = io.StringIO("".join(transcript_messages))
            
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user}")
        except Exception as e:
            print(f"--- ERREUR DANS handle_close_ticket ---"); traceback.print_exc()

# --- Setup du Cog (inchangé) ---
async def setup(bot: commands.Bot):
    await bot.add_cog(SuggestionsTicketsCog(bot))
    print("Cog Suggestions & Tickets (corrigé) chargé.")
