import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import time

class LevelingCog(commands.Cog, name="Système de Niveaux"):
    # On crée un groupe de commandes principal /xp
    xp_group = app_commands.Group(name="xp", description="Commandes liées au système d'expérience.")
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Cooldown pour éviter le spam d'XP (par utilisateur)
        self.cooldowns = {}

    # --- Listener pour donner de l'XP ---
    @commands.Cog.listener("on_message")
    async def on_xp_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        # Récupérer la config du serveur
        settings = await self.db.get_guild_settings(guild_id)
        if not settings or not json.loads(settings.get("leveling_config", "{}")).get("enabled", False):
            return

        # Gestion du Cooldown (1 minute par utilisateur)
        now = time.time()
        cooldown_key = f"{guild_id}-{user_id}"
        if cooldown_key in self.cooldowns and now - self.cooldowns[cooldown_key] < 60:
            return
        self.cooldowns[cooldown_key] = now

        # Donner de l'XP
        xp_gain = random.randint(15, 25)
        user_data = await self.db.get_user_data(guild_id, user_id)
        
        current_xp = user_data.get("xp", 0) + xp_gain
        current_level = user_data.get("level", 1)
        xp_needed = 5 * (current_level ** 2) + 50 * current_level + 100

        # Vérification du passage de niveau
        if current_xp >= xp_needed:
            current_level += 1
            current_xp -= xp_needed
            await self.db.update_user_xp(guild_id, user_id, current_xp, current_level)

            # Annonce de level-up
            leveling_config = json.loads(settings.get("leveling_config", "{}"))
            announcement_channel_id = leveling_config.get("announcement_channel")
            if announcement_channel_id:
                channel = message.guild.get_channel(announcement_channel_id)
                if channel:
                    await channel.send(f"🎉 Bravo {message.author.mention}, tu as atteint le niveau **{current_level}** !")

            # Attribution des rôles récompenses
            role_rewards = leveling_config.get("role_rewards", {})
            if str(current_level) in role_rewards:
                role_id = role_rewards[str(current_level)]
                role = message.guild.get_role(role_id)
                if role:
                    try:
                        await message.author.add_roles(role, reason=f"Récompense de niveau {current_level}")
                    except discord.Forbidden:
                        print(f"Permissions manquantes pour donner le rôle {role.name} sur le serveur {message.guild.name}")
        else:
            await self.db.update_user_xp(guild_id, user_id, current_xp, current_level)

    # --- Commandes de Configuration ---
    @xp_group.command(name="config-annonces", description="[Admin] Définit le salon pour les annonces de passage de niveau.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_announcements(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        settings = await self.db.get_guild_settings(interaction.guild.id)
        config = json.loads(settings.get("leveling_config", "{}")) if settings else {}
        
        config["announcement_channel"] = salon.id
        await self.db.update_guild_setting(interaction.guild.id, "leveling_config", config)
        
        await interaction.followup.send(f"✅ Les annonces de niveau seront maintenant envoyées dans {salon.mention}.", ephemeral=True)

    @xp_group.command(name="config-roles", description="[Admin] Ajoute un rôle récompense pour un certain niveau.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_roles(self, interaction: discord.Interaction, niveau: app_commands.Range[int, 1, 100], role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        
        if interaction.guild.me.top_role <= role:
            return await interaction.followup.send("❌ Je ne peux pas attribuer ce rôle car il est plus élevé que le mien dans la hiérarchie.", ephemeral=True)

        settings = await self.db.get_guild_settings(interaction.guild.id)
        config = json.loads(settings.get("leveling_config", "{}")) if settings else {}
        
        if "role_rewards" not in config:
            config["role_rewards"] = {}
        
        config["role_rewards"][str(niveau)] = role.id
        await self.db.update_guild_setting(interaction.guild.id, "leveling_config", config)

        await interaction.followup.send(f"✅ Le rôle {role.mention} sera maintenant donné au niveau **{niveau}**.", ephemeral=True)

    @xp_group.command(name="config-activer", description="[Admin] Active ou désactive le système de niveaux sur le serveur.")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_toggle(self, interaction: discord.Interaction, statut: bool):
        await interaction.response.defer(ephemeral=True)
        settings = await self.db.get_guild_settings(interaction.guild.id)
        config = json.loads(settings.get("leveling_config", "{}")) if settings else {}

        config["enabled"] = statut
        await self.db.update_guild_setting(interaction.guild.id, "leveling_config", config)

        message = "activé" if statut else "désactivé"
        await interaction.followup.send(f"✅ Le système de niveaux a été **{message}**.", ephemeral=True)
        
async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))
