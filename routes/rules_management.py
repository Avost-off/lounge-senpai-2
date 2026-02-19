import discord
from discord import app_commands
from discord.ext import commands
import json
import os

# --- Fonctions de gestion de données ---
def load_config_data():
    try:
        with open('data/server_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_config_data(data):
    with open('data/server_config.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Classe du Cog de gestion du règlement ---
class RulesManagement(commands.Cog, name="Gestion du Règlement"):
    
    # On crée un groupe de commandes pour /regles
    rules_group = app_commands.Group(name="regles", description="Commandes pour gérer le message du règlement.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Commande pour créer le message de règlement ---
    @rules_group.command(name="creer", description="[Admin] Crée le message du règlement dans un salon.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        salon="Le salon où le message du règlement sera posté.",
        titre="Le titre principal du règlement (ex: ⭐ Règlement du Serveur ⭐)."
    )
    async def create_rules(self, interaction: discord.Interaction, salon: discord.TextChannel, titre: str):
        await interaction.response.defer(ephemeral=True)
        
        # On crée un embed de base avec un exemple de règle
        embed = discord.Embed(
            title=titre,
            description="Voici les règles à respecter pour garantir un environnement agréable pour tous.\n\n"
                        "Utilisez la commande `/regles modifier` pour ajouter ou changer des règles.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="1. Exemple de Règle",
            value="Soyez respectueux. (Utilisez `/regles modifier numero:1 nouveau_titre:... nouvelle_description:...`)",
            inline=False
        )
        embed.set_footer(text="Ce règlement peut être mis à jour à tout moment.")
        
        try:
            rules_message = await salon.send(embed=embed)
            
            # On sauvegarde l'ID du salon et du message
            config = load_config_data()
            server_id = str(interaction.guild.id)
            if server_id not in config:
                config[server_id] = {}
            
            config[server_id]["rules_config"] = {
                "channel_id": salon.id,
                "message_id": rules_message.id
            }
            save_config_data(config)
            
            await interaction.followup.send(f"✅ Message du règlement créé avec succès dans {salon.mention} !", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas la permission d'envoyer des messages dans ce salon.", ephemeral=True)
        except Exception as e:
            print(f"Erreur lors de la création du règlement : {e}")
            await interaction.followup.send("❌ Une erreur inattendue est survenue.", ephemeral=True)


    # --- Commande pour modifier une règle ---
    @rules_group.command(name="modifier", description="[Admin] Modifie ou ajoute une règle au message du règlement.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        numero="Le numéro de la règle à modifier ou à ajouter (ex: 1, 2, 3...).",
        nouveau_titre="Le nouveau titre de la règle (ex: 'Respect et Courtoisie').",
        nouvelle_description="La nouvelle description détaillée de la règle."
    )
    async def edit_rule(self, interaction: discord.Interaction, numero: app_commands.Range[int, 1, 25], nouveau_titre: str, nouvelle_description: str):
        await interaction.response.defer(ephemeral=True)

        config = load_config_data()
        server_id = str(interaction.guild.id)
        rules_config = config.get(server_id, {}).get("rules_config")

        if not rules_config:
            return await interaction.followup.send("❌ Le message du règlement n'a pas été créé. Utilisez d'abord `/regles creer`.", ephemeral=True)
        
        try:
            # On récupère le message du règlement
            channel_id = rules_config["channel_id"]
            message_id = rules_config["message_id"]
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return await interaction.followup.send("❌ Le salon du règlement est introuvable. A-t-il été supprimé ?", ephemeral=True)
                
            rules_message = await channel.fetch_message(message_id)
            
            # On récupère l'embed actuel et on le modifie
            embed = rules_message.embeds[0]
            
            # On cherche si la règle existe déjà pour la modifier, sinon on l'ajoute.
            # L'index des "fields" commence à 0, donc on fait numero - 1.
            field_index = numero - 1
            
            if field_index < len(embed.fields):
                # La règle existe, on la modifie
                embed.set_field_at(
                    index=field_index,
                    name=f"{numero}. {nouveau_titre}",
                    value=nouvelle_description,
                    inline=False
                )
            elif field_index == len(embed.fields):
                # C'est la prochaine règle à ajouter
                embed.add_field(
                    name=f"{numero}. {nouveau_titre}",
                    value=nouvelle_description,
                    inline=False
                )
            else:
                # L'utilisateur essaie de sauter un numéro
                return await interaction.followup.send(f"❌ Veuillez ajouter les règles dans l'ordre. La prochaine règle à ajouter est la numéro {len(embed.fields) + 1}.", ephemeral=True)
            
            # On met à jour le message avec le nouvel embed
            await rules_message.edit(embed=embed)
            
            await interaction.followup.send(f"✅ Règle n°{numero} mise à jour avec succès !", ephemeral=True)

        except discord.NotFound:
            await interaction.followup.send("❌ Le message du règlement est introuvable. A-t-il été supprimé ? Recréez-le avec `/regles creer`.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas les permissions nécessaires pour modifier le message.", ephemeral=True)
        except IndexError:
             await interaction.followup.send("❌ Le message du règlement semble corrompu (pas d'embed). Recréez-le.", ephemeral=True)
        except Exception as e:
            print(f"Erreur lors de la modification de la règle : {e}")
            await interaction.followup.send("❌ Une erreur inattendue est survenue.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RulesManagement(bot))