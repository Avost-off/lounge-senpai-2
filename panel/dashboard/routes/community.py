import discord
from discord import app_commands  # <-- CHANGEMENT 1: Utilisation de app_commands
from discord.ext import commands
import random
import asyncio
import datetime
import re
import json

# --- Les fonctions de gestion de données ne changent pas ---
def load_data(filename):
    try:
        with open(f'data/{filename}', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data, filename):
    with open(f'data/{filename}', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Les vues interactives ne changent pas ---
class RoleMenuView(discord.ui.View):
    def __init__(self, role_buttons_config):
        super().__init__(timeout=None)
        for config in role_buttons_config:
            self.add_item(RoleButton(
                role_id=config['role_id'],
                label=config['label'],
                emoji=config.get('emoji')
            ))

class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str = None):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=str(role_id), emoji=emoji)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            return await interaction.response.send_message("Ce rôle n'existe plus.", ephemeral=True)
        if interaction.guild.me.top_role <= role:
            return await interaction.response.send_message("Je ne peux pas gérer ce rôle car il est plus élevé que le mien.", ephemeral=True)
        if role in user.roles:
            await user.remove_roles(role, reason="Role Menu")
            await interaction.response.send_message(f"Le rôle **{role.name}** vous a été retiré.", ephemeral=True)
        else:
            await user.add_roles(role, reason="Role Menu")
            await interaction.response.send_message(f"Vous avez reçu le rôle **{role.name}** !", ephemeral=True)

# --- Le Cog Principal de la Communauté ---
# CHANGEMENT 2: Organisation des commandes pour discord.py
@app_commands.guild_only() # Recommandé pour les commandes de guilde
class Community(commands.GroupCog, name="commu"):
    base = app_commands.Group(name="base", description="Commandes communautaires de base.")
    superieur = app_commands.Group(name="superieur", description="Commandes communautaires supérieures.")
    avance = app_commands.Group(name="avance", description="Commandes communautaires avancées.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        # Rechargement des vues persistantes
        role_menus = load_data('role_menus.json')
        for server_id, menus in role_menus.items():
            for message_id, menu_data in menus.items():
                view = RoleMenuView(role_buttons_config=menu_data['roles'])
                self.bot.add_view(view, message_id=int(message_id))
        print("-> Cog Communauté : Vues persistantes rechargées.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        server_id, user_id = str(message.guild.id), str(message.author.id)
        activity = load_data('activity.json')
        if server_id not in activity: activity[server_id] = {}
        if user_id not in activity[server_id]: activity[server_id][user_id] = {'messages': 0}
        activity[server_id][user_id]['messages'] += 1
        save_data(activity, 'activity.json')

    # --- COMMANDES DE BASE ---
    @base.command(name="ping", description="Affiche la latence du bot.")
    async def ping(self, interaction: discord.Interaction): # <-- CHANGEMENT 3: `interaction` au lieu de `ctx`
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong ! 🏓 Latence : `{latency}ms`", ephemeral=True) # <-- CHANGEMENT 4: `interaction.response`

    @base.command(name="server-info", description="Affiche des informations sur le serveur.")
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"Informations sur {guild.name}", color=discord.Color.blue())
        if guild.icon: embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 Propriétaire", value=guild.owner.mention, inline=True)
        embed.add_field(name="📆 Créé le", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="👥 Membres", value=f"{guild.member_count}", inline=True)
        await interaction.response.send_message(embed=embed)

    @base.command(name="user-info", description="Affiche des informations sur un membre.")
    async def user_info(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        roles = [role.mention for role in membre.roles if role.name != "@everyone"]
        embed = discord.Embed(title=f"Informations sur {membre.display_name}", color=membre.color)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="👤 Nom", value=f"`{membre.name}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{membre.id}`", inline=True)
        embed.add_field(name="📅 Compte créé le", value=f"<t:{int(membre.created_at.timestamp())}:D>", inline=False)
        embed.add_field(name="📥 A rejoint le", value=f"<t:{int(membre.joined_at.timestamp())}:D>", inline=False)
        if roles: embed.add_field(name=f"🎭 Rôles ({len(roles)})", value=", ".join(roles[:10]), inline=False)
        await interaction.response.send_message(embed=embed)

    @base.command(name="avatar", description="Affiche l'avatar d'un membre en grand.")
    async def avatar(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        embed = discord.Embed(title=f"Avatar de {membre.display_name}", color=membre.color)
        embed.set_image(url=membre.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # --- COMMANDES SUPÉRIEURES ---
    @superieur.command(name="sondage", description="Crée un sondage simple avec des réactions.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def poll(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(title="📊 SONDAGE", description=question, color=discord.Color.green())
        embed.set_footer(text=f"Sondage proposé par {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    @superieur.command(name="annonce", description="Crée et envoie une annonce formatée dans un salon.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def announce(self, interaction: discord.Interaction, salon: discord.TextChannel, titre: str, message: str, mention: discord.Role = None):
        embed = discord.Embed(title=f"📢 {titre}", description=message, color=discord.Color.orange(), timestamp=datetime.datetime.now())
        embed.set_author(name=f"Annonce de {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        mention_text = mention.mention if mention else ""
        await salon.send(content=mention_text, embed=embed)
        await interaction.response.send_message(f"Annonce envoyée dans {salon.mention}", ephemeral=True)

    @superieur.command(name="role-menu", description="Crée un menu de rôles interactif avec des boutons.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_role_menu(self, interaction: discord.Interaction, titre: str, description: str, roles: str):
        await interaction.response.defer(ephemeral=True)
        role_configs = []
        for part in [p.strip() for p in roles.split('|')]:
            elements = [e.strip() for e in part.split(';')]
            try:
                role_id = int(re.search(r'<@&(\d+)>', elements[0]).group(1))
                if not interaction.guild.get_role(role_id): return await interaction.followup.send(f"Rôle `{elements[0]}` introuvable.")
                role_configs.append({"role_id": role_id, "label": elements[1], "emoji": elements[2] if len(elements) > 2 else None})
            except (AttributeError, IndexError):
                return await interaction.followup.send(f"Format invalide pour : `{part}`.")
        
        embed = discord.Embed(title=titre, description=description, color=discord.Color.blurple())
        view = RoleMenuView(role_buttons_config=role_configs)
        menu_message = await interaction.channel.send(embed=embed, view=view)

        all_menus = load_data('role_menus.json')
        server_id = str(interaction.guild.id)
        if server_id not in all_menus: all_menus[server_id] = {}
        all_menus[server_id][str(menu_message.id)] = {"roles": role_configs}
        save_data(all_menus, 'role_menus.json')
        await interaction.followup.send("Menu de rôles créé !")

    # --- COMMANDES AVANCÉES ---
    @avance.command(name="purge", description="Supprime un nombre de messages avec des filtres.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, nombre: app_commands.Range[int, 1, 100], membre: discord.Member = None, contenant: str = None):
        await interaction.response.defer(ephemeral=True)
        def check(message):
            if membre and message.author != membre: return False
            if contenant and contenant.lower() not in message.content.lower(): return False
            return True
        deleted = await interaction.channel.purge(limit=nombre, check=check)
        await interaction.followup.send(f"✅ {len(deleted)} messages ont été supprimés.")

    @avance.command(name="mod-profile", description="Affiche l'historique de modération d'un membre.")
    @app_commands.checks.has_permissions(kick_members=True)
    async def mod_profile(self, interaction: discord.Interaction, membre: discord.Member):
        infractions = load_data('infractions.json').get(str(interaction.guild.id), {}).get(str(membre.id), [])
        if not infractions:
            return await interaction.response.send_message(f"{membre.mention} n'a aucune infraction enregistrée.", ephemeral=True)
        embed = discord.Embed(title=f"Profil de modération de {membre.display_name}", color=discord.Color.red())
        embed.set_thumbnail(url=membre.display_avatar.url)
        description = ""
        for infra in infractions[-5:]:
            moderator = interaction.guild.get_member(infra['moderator_id'])
            mod_name = moderator.name if moderator else "ID: " + str(infra['moderator_id'])
            description += f"**Type :** {infra['type'].capitalize()}\n**Raison :** {infra['reason']}\n**Date :** <t:{infra['timestamp']}:f>\n**Modérateur :** {mod_name}\n---\n"
        embed.description = description
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @avance.command(name="leaderboard", description="Affiche le classement d'activité du serveur (basé sur les messages).")
    async def leaderboard(self, interaction: discord.Interaction):
        activity = load_data('activity.json').get(str(interaction.guild.id), {})
        if not activity:
            return await interaction.response.send_message("Aucune donnée d'activité n'a été collectée.", ephemeral=True)
        sorted_users = sorted(activity.items(), key=lambda item: item[1]['messages'], reverse=True)
        embed = discord.Embed(title=f"🏆 Classement d'activité de {interaction.guild.name}", color=discord.Color.gold())
        description = ""
        rank_emojis = ["🥇", "🥈", "🥉"]
        for i, (user_id, data) in enumerate(sorted_users[:10]):
            member = interaction.guild.get_member(int(user_id))
            if member:
                rank = rank_emojis[i] if i < 3 else f"**#{i+1}**"
                description += f"{rank} {member.mention} - `{data['messages']}` messages\n"
        embed.description = description
        await interaction.response.send_message(embed=embed)

# --- CHANGEMENT 5: La fonction setup doit simplement charger le cog ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))