# cogs/debug_cog.py
import discord
from discord.ext import commands
from discord import app_commands

class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="debug-hello", description="[Propriétaire] Un simple test pour voir si les commandes apparaissent.")
    @commands.is_owner()
    async def debug_hello(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bonjour ! La commande de débogage fonctionne !", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DebugCog(bot))
    print("[DIAGNOSTIC] Le Cog 'debug_cog.py' a été chargé par le bot.")