import discord
from discord import app_commands # Cet import est inutile si vous n'utilisez que des commandes à préfixe
from discord.ext import commands
from typing import Optional
import os
from dotenv import load_dotenv
import asyncio
import datetime # <-- AJOUT NÉCESSAIRE pour la gestion des messages anciens

# Je commente ces lignes car elles semblent causer des confusions ou des erreurs
# from cogs.utility import is_not_maintenance 
# class ModerationCog(commands.Cog): ...

# --- Configuration ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    print("Erreur: Le token Discord n'a pas été trouvé.")
    print("Assurez-vous d'avoir un fichier .env avec DISCORD_TOKEN=VOTRE_TOKEN")
    exit()

COMMAND_PREFIX = "!"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- Événements (inchangés) ---

@bot.event
async def on_ready():
    """ Affiche un message quand le bot est connecté et prêt. """
    print(f'Connecté en tant que {bot.user.name} ({bot.user.id})')
    print('Le bot est prêt.')
    print('------')
    await bot.change_presence(activity=discord.Game(name=f"Modérer avec {COMMAND_PREFIX}"))

@bot.event
async def on_command_error(ctx, error):
    """ Gère les erreurs de commandes courantes. """
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Argument manquant. Utilisation : `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Vous n'avez pas les permissions nécessaires pour exécuter cette commande.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("Je n'ai pas les permissions nécessaires pour exécuter cette action.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(f"Membre non trouvé : `{error.argument}`.")
    elif isinstance(error, commands.BadArgument):
         await ctx.send(f"Argument invalide. Vérifiez le type d'argument attendu (ex: un nombre, une mention).")
    else:
        print(f'Erreur non gérée dans la commande {ctx.command}: {error}')
        await ctx.send("Une erreur est survenue lors de l'exécution de la commande.")

# --- Commandes de Modération ---

@bot.command(name='kick', help='Expulse un membre du serveur.')
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    """ Commande pour expulser un membre. """
    if member == ctx.author:
        await ctx.send("Vous ne pouvez pas vous expulser vous-même !")
        return
    if member == bot.user:
        await ctx.send("Je ne peux pas m'expulser moi-même !")
        return
    if ctx.author.top_role <= member.top_role and ctx.guild.owner != ctx.author:
         await ctx.send("Vous ne pouvez pas expulser un membre ayant un rôle égal ou supérieur au vôtre.")
         return
    if ctx.guild.me.top_role <= member.top_role:
         await ctx.send("Je ne peux pas expulser ce membre car son rôle est égal ou supérieur au mien.")
         return

    try:
        await member.kick(reason=f"{reason} (Par {ctx.author.name})")
        await ctx.send(f"👢 {member.mention} a été expulsé avec succès. Raison : {reason}")
        try:
            await member.send(f"Vous avez été expulsé du serveur '{ctx.guild.name}'. Raison : {reason}")
        except discord.Forbidden:
            print(f"Impossible d'envoyer un MP à {member.name}")
    except discord.Forbidden:
        await ctx.send("Je n'ai pas la permission d'expulser ce membre.")
    except discord.HTTPException as e:
        await ctx.send(f"Une erreur est survenue : {e}")

@bot.command(name='ban', help='Bannit un membre du serveur.')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    """ Commande pour bannir un membre. """
    if member == ctx.author:
        await ctx.send("Vous ne pouvez pas vous bannir vous-même !")
        return
    if member == bot.user:
        await ctx.send("Je ne peux pas me bannir moi-même !")
        return
    if ctx.author.top_role <= member.top_role and ctx.guild.owner != ctx.author:
         await ctx.send("Vous ne pouvez pas bannir un membre ayant un rôle égal ou supérieur au vôtre.")
         return
    if ctx.guild.me.top_role <= member.top_role:
         await ctx.send("Je ne peux pas bannir ce membre car son rôle est égal ou supérieur au mien.")
         return

    try:
        await member.ban(reason=f"{reason} (Par {ctx.author.name})", delete_message_days=1)
        await ctx.send(f"🔨 {member.mention} a été banni avec succès. Raison : {reason}")
        try:
            await member.send(f"Vous avez été banni du serveur '{ctx.guild.name}'. Raison : {reason}")
        except discord.Forbidden:
             print(f"Impossible d'envoyer un MP à {member.name}")
    except discord.Forbidden:
        await ctx.send("Je n'ai pas la permission de bannir ce membre.")
    except discord.HTTPException as e:
        await ctx.send(f"Une erreur est survenue : {e}")

# ==============================================================================
# --- CORRECTION APPLIQUÉE À LA COMMANDE CLEAR ---
@bot.command(name='clear', aliases=['purge'], help='Supprime un nombre spécifié de messages.')
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True)
async def clear(ctx, amount: int, member: Optional[discord.Member] = None):
    """
    Supprime des messages, y compris ceux de plus de 14 jours, et peut filtrer par membre.
    Utilisation: !clear [nombre] [@membre optionnel]
    """
    if amount <= 0:
        return await ctx.send("Veuillez entrer un nombre positif.")
    
    # On supprime d'abord le message de commande
    await ctx.message.delete()
    
    deleted_count = 0
    
    try:
        # On définit le filtre
        def check(message):
            if member is None:
                return True # Si aucun membre, on supprime tout
            return message.author == member # Sinon, on filtre par auteur

        # La méthode `purge` avec `bulk=False` gère les messages anciens,
        # mais est plus lente. On utilise une méthode hybride.
        
        fourteen_days_ago = discord.utils.utcnow() - datetime.timedelta(days=14)
        
        # Messages récents (peuvent être supprimés en masse)
        recent_messages = []
        # Messages anciens (doivent être supprimés un par un)
        old_messages = []
        
        async for message in ctx.channel.history(limit=amount * 2): # On scanne plus large pour le filtre
            if len(recent_messages) + len(old_messages) >= amount:
                break
            
            if check(message):
                if message.created_at > fourteen_days_ago:
                    recent_messages.append(message)
                else:
                    old_messages.append(message)

        # Suppression optimisée
        if recent_messages:
            deleted_recent = await ctx.channel.purge(limit=len(recent_messages), check=lambda m: m in recent_messages)
            deleted_count += len(deleted_recent)
        
        if old_messages:
            for msg in old_messages:
                await msg.delete()
                deleted_count += 1
        
        await ctx.send(f"🗑️ **{deleted_count}** messages ont été supprimés.", delete_after=5.0)

    except discord.Forbidden:
        await ctx.send("Je n'ai pas la permission de supprimer des messages dans ce salon.", delete_after=10.0)
    except Exception as e:
        print(f"Erreur dans la commande clear: {e}")
        await ctx.send("Une erreur est survenue.", delete_after=10.0)
# ==============================================================================

# --- Lancement du Bot ---
# Note : la section "SETUP DU COG" est retirée car ce fichier n'est pas un Cog.
if __name__ == "__main__":
    print("Lancement du bot...")
    bot.run(TOKEN)
