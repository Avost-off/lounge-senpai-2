# cogs/admin_eco_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

# --- Dépendances ---
from utils.database import db

# --- Classe Cog ---
class AdminEcoCog(commands.Cog, name="Administration Économie"):
    def __init__(self, bot: commands.Bot, db_manager):
        self.bot = bot
        self.db = db_manager

    # =============================================
    # ==      GROUPE COMMANDES ADMIN-XP          ==
    # =============================================
    admin_xp_group = app_commands.Group(
        name="admin-xp",
        description="Commandes d'administration pour l'XP des membres.",
        default_permissions=discord.Permissions(manage_guild=True), # Seuls les admins peuvent voir/utiliser
        guild_only=True
    )

    @admin_xp_group.command(name="ajouter", description="Ajoute de l'XP à un membre.")
    @app_commands.describe(
        membre="Le membre à qui ajouter de l'XP.",
        montant="La quantité d'XP à ajouter."
    )
    async def admin_xp_ajouter(self, interaction: discord.Interaction,
                               membre: discord.Member,
                               montant: app_commands.Range[int, 1, None]):
        
        if membre.bot:
            await interaction.response.send_message("❌ Vous ne pouvez pas modifier l'XP d'un bot.", ephemeral=True)
            return

        try:
            # Récupérer les données actuelles de l'utilisateur
            user_data = await self.db.get_user_data(interaction.guild.id, membre.id)
            current_xp = user_data.get("xp", 0)
            new_xp = current_xp + montant
            
            # Récupérer le Cog de leveling pour recalculer le niveau
            leveling_cog = self.bot.get_cog("Niveaux & XP") # Assurez-vous que le nom est correct
            if not leveling_cog:
                await interaction.response.send_message("❌ Erreur : Le module de leveling n'est pas chargé.", ephemeral=True)
                return
                
            new_level = leveling_cog.calculate_level(new_xp)

            # Mettre à jour la base de données
            await self.db.update_user_xp(interaction.guild.id, membre.id, new_xp, new_level)
            
            await interaction.response.send_message(
                f"✅ **{montant}** ✨ XP ont été ajoutés à {membre.mention}.\n"
                f"Nouveau total : `{new_xp}` XP (Niveau `{new_level}`).",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors de la mise à jour de l'XP.", ephemeral=True)
            print(f"Erreur dans /admin-xp ajouter : {e}")

    # =============================================
    # ==    GROUPE COMMANDES ADMIN-MONNAIE       ==
    # =============================================
    admin_monnaie_group = app_commands.Group(
        name="admin-monnaie",
        description="Commandes d'administration pour la monnaie des membres.",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    @admin_monnaie_group.command(name="ajouter", description="Ajoute de la monnaie à un membre.")
    @app_commands.describe(
        membre="Le membre à qui ajouter de la monnaie.",
        montant="Le montant à ajouter."
    )
    async def admin_monnaie_ajouter(self, interaction: discord.Interaction,
                                    membre: discord.Member,
                                    montant: app_commands.Range[int, 1, None]):

        if membre.bot:
            await interaction.response.send_message("❌ Vous ne pouvez pas modifier le solde d'un bot.", ephemeral=True)
            return

        try:
            # Récupérer les données actuelles
            user_data = await self.db.get_user_data(interaction.guild.id, membre.id)
            current_balance = user_data.get("balance", 0)
            new_balance = current_balance + montant
            
            # Mettre à jour la base de données
            await self.db.update_user_balance(interaction.guild.id, membre.id, new_balance)

            # Récupérer la config pour l'affichage de la monnaie
            # Vous pouvez créer une méthode db.get_economy_config() ou la charger depuis settings.json
            currency_emoji = "💰" # Valeur par défaut
            # economie_cog = self.bot.get_cog("Économie")
            # if economie_cog:
            #     config = economie_cog.get_guild_config(interaction.guild.id)
            #     currency_emoji = config.get("currency_emoji", "💰")

            await interaction.response.send_message(
                f"✅ **{montant}** {currency_emoji} ont été ajoutés à {membre.mention}.\n"
                f"Nouveau solde : `{new_balance}` {currency_emoji}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ Une erreur est survenue lors de la mise à jour du solde.", ephemeral=True)
            print(f"Erreur dans /admin-monnaie ajouter : {e}")

# =============================================
# ==           SETUP DU COG                  ==
# =============================================
async def setup(bot: commands.Bot):
    if not hasattr(bot, 'db'):
        print("ERREUR CRITIQUE (admin_eco_cog.py): L'objet bot n'a pas d'attribut 'db'.")
        return
    await bot.add_cog(AdminEcoCog(bot, bot.db))
    print("Cog Administration Économie chargé.")