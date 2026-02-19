# cogs/marriage_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import datetime
import traceback
import re # Ajout pour l'autocomplétion

# --- Dépendances ---
from utils.database import db

# --- Vue pour la Demande en Mariage (Modifiée) ---
class MarriageProposalView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member, cog_instance):
        super().__init__(timeout=180.0) # 3 minutes pour répondre
        self.author = author
        self.target = target
        self.cog = cog_instance
        self.message: Optional[discord.InteractionMessage] = None

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                # Le timeout modifie le message original sans ping
                await self.message.edit(content="💍 La demande en mariage a expiré.", embed=None, view=self)
            except discord.NotFound:
                pass # Le message a peut-être été supprimé

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("Ce n'est pas votre demande !", ephemeral=True)
            return

        self.stop()
        for item in self.children: item.disabled = True
        
        try:
            # Ajouter le mariage à la base de données
            await db.add_marriage(interaction.guild.id, self.author.id, self.target.id)
            
            response_embed = discord.Embed(
                title="🎉 Mariage Accepté ! 🎉",
                description=f"Félicitations ! {self.author.mention} et {self.target.mention} sont maintenant marié(e)s !",
                color=discord.Color.fuchsia()
            )
            
            # --- MODIFICATION ---
            # Ajouter content="@everyone" et allowed_mentions
            await interaction.response.edit_message(
                content="@everyone", 
                embed=response_embed, 
                view=self,
                allowed_mentions=discord.AllowedMentions(everyone=True)
            )

        except Exception as e:
            await interaction.response.edit_message(content="❌ Une erreur est survenue lors de l'enregistrement du mariage.", view=self)
            print(f"Erreur lors de l'acceptation du mariage: {e}"); traceback.print_exc()

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger)
    async def refuse_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.author.id, self.target.id]:
            await interaction.response.send_message("Ce n'est pas votre demande !", ephemeral=True)
            return

        self.stop()
        for item in self.children: item.disabled = True
        
        response_embed = discord.Embed(
            title="💔 Demande Refusée",
            description=f"{self.target.mention} a refusé la demande en mariage de {self.author.mention}.",
            color=discord.Color.dark_grey()
        )

        # --- MODIFICATION ---
        # Ajouter content="@everyone" et allowed_mentions
        await interaction.response.edit_message(
            content="@everyone", 
            embed=response_embed, 
            view=self,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )


# ----- Classe Cog -----
class MarriageCog(commands.Cog, name="Système de Mariage"):
    def __init__(self, bot: commands.Bot, db_manager):
        self.bot = bot
        self.db = db_manager

    # --- Autocomplétion pour la commande /divorce (Inchangée) ---
    async def divorce_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        partners_ids = await self.db.get_partners(interaction.guild.id, interaction.user.id)
        if not partners_ids:
            return []
        
        choices = [app_commands.Choice(name="💔 Divorcer de tout le monde", value="all")]
        for partner_id in partners_ids:
            member = interaction.guild.get_member(partner_id)
            if member:
                if current.lower() in member.display_name.lower():
                    choices.append(app_commands.Choice(name=f"💔 Divorcer de {member.display_name}", value=str(partner_id)))
            else:
                # Si le membre n'est plus sur le serveur
                if current.lower() in str(partner_id):
                    choices.append(app_commands.Choice(name=f"💔 Divorcer de (ID: {partner_id})", value=str(partner_id)))

        return choices[:25]

    # =============================================
    # ==          COMMANDES DE MARIAGE           ==
    # =============================================
    @app_commands.command(name="mariage", description="Demander un autre membre en mariage.")
    @app_commands.describe(membre="La personne que vous souhaitez demander en mariage.")
    async def mariage_command(self, interaction: discord.Interaction, membre: discord.Member):
        author = interaction.user
        guild = interaction.guild

        if membre == author:
            await interaction.response.send_message("❌ Vous ne pouvez pas vous marier avec vous-même !", ephemeral=True); return
        if membre.bot:
            await interaction.response.send_message("❌ Désolé, les bots ne peuvent pas se marier.", ephemeral=True); return

        are_already_married = await self.db.are_married(guild.id, author.id, membre.id)
        if are_already_married:
            await interaction.response.send_message(f"ℹ️ Vous êtes déjà marié(e) avec {membre.mention} !", ephemeral=True); return
        
        view = MarriageProposalView(author, membre, self)

        embed = discord.Embed(
            title="💍 Demande en Mariage 💍",
            description=f"{membre.mention}, voulez-vous épouser {author.mention} ?",
            color=discord.Color.pink()
        )
        
        # --- MODIFICATION ---
        # S'assurer que la réponse n'est PAS éphémère pour qu'elle soit publique
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        view.message = await interaction.original_response()

    @app_commands.command(name="divorce", description="Mettre fin à un ou plusieurs mariages.")
    @app_commands.describe(partenaire="Choisissez de qui divorcer, ou 'Tous'.")
    @app_commands.autocomplete(partenaire=divorce_autocomplete)
    async def divorce_command(self, interaction: discord.Interaction, partenaire: str):
        # (Logique de divorce inchangée, elle était déjà correcte)
        author = interaction.user
        guild = interaction.guild

        if partenaire == "all":
            await self.db.remove_all_marriages(guild.id, author.id)
            await interaction.response.send_message("💔 Vous avez divorcé de tous vos partenaires.", ephemeral=True)
            return

        try:
            target_id = int(partenaire)
            target_user = self.bot.get_user(target_id) or await self.bot.fetch_user(target_id)
            
            if not await self.db.are_married(guild.id, author.id, target_id):
                await interaction.response.send_message(f"❌ Vous n'êtes pas marié(e) avec {target_user.mention}.", ephemeral=True); return

            await self.db.remove_marriage(guild.id, author.id, target_id)
            await interaction.response.send_message(f"💔 Vous avez divorcé de {target_user.mention}.", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Sélection invalide. Veuillez choisir dans la liste.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Partenaire introuvable.", ephemeral=True)


    @app_commands.command(name="partenaires", description="Affiche la liste de vos partenaires.")
    @app_commands.describe(membre="Le membre dont voir les partenaires (optionnel).")
    async def partenaires_command(self, interaction: discord.Interaction, membre: Optional[discord.Member] = None):
        # (Logique de /partenaires inchangée, elle était déjà correcte)
        target_user = membre or interaction.user
        partners_ids = await self.db.get_partners(interaction.guild.id, target_user.id)
        embed = discord.Embed(title=f"❤️ Partenaires de {target_user.display_name}", color=discord.Color.red()).set_thumbnail(url=target_user.display_avatar.url)
        if not partners_ids: embed.description = "Cette personne n'est mariée à personne."
        else:
            mentions = [f"<@{pid}>" for pid in partners_ids]
            embed.description = " & ".join(mentions)
        await interaction.response.send_message(embed=embed)


# =============================================
# ==           SETUP DU COG                  ==
# =============================================
async def setup(bot: commands.Bot):
    if not hasattr(bot, 'db'):
        print("ERREUR CRITIQUE (marriage_cog.py): L'objet bot n'a pas d'attribut 'db'.")
        return
    await bot.add_cog(MarriageCog(bot, bot.db))
    print("Cog Mariage chargé.")