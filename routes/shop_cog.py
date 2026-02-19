# cogs/shop_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict
import json
import os
import traceback
import datetime

# --- Dépendances et Helpers ---
DATA_DIR = './data'
SHOP_DATA_FILE = os.path.join(DATA_DIR, 'shop_data.json')
# Note : Pour l'achat, ce cog aura besoin de l'objet 'db' de utils.database
# Assurez-vous que l'import est correct si vous l'utilisez
# from utils.database import db

def load_data(filepath):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(filepath, 'w', encoding='utf-8') as f: json.dump({}, f); return {}
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

# --- Classe Cog ---
class ShopCog(commands.Cog, name="Boutique"):
    def __init__(self, bot: commands.Bot): # Retiré db_manager pour l'instant car non utilisé
        self.bot = bot
        self.shop_data = load_data(SHOP_DATA_FILE)

    def get_guild_shop_data(self, guild_id: int) -> dict:
        guild_id_str = str(guild_id)
        guild_data = self.shop_data.setdefault(guild_id_str, {})
        guild_data.setdefault("config", {"currency_name": "Points", "currency_emoji": "💰"})
        guild_data.setdefault("items", {})
        return guild_data

    # =============================================
    # ==          GROUPE COMMANDES BOUTIQUE      ==
    # =============================================
    boutique_group = app_commands.Group(name="boutique", description="Commandes pour interagir avec la boutique du serveur.")

    @boutique_group.command(name="voir", description="Affiche les articles disponibles dans la boutique.")
    async def boutique_voir(self, interaction: discord.Interaction):
        guild_data = self.get_guild_shop_data(interaction.guild.id)
        items = guild_data.get("items", {})
        config = guild_data.get("config", {})
        
        if not items:
            await interaction.response.send_message("ℹ️ La boutique est actuellement vide.", ephemeral=True); return

        embed = discord.Embed(title=f"🛍️ Boutique de {interaction.guild.name}", color=discord.Color.gold())
        description = ""
        sorted_items = sorted(items.items(), key=lambda item: (item[1].get('price', 0), item[1].get('xp_cost', 0)))

        for item_key, item_data in sorted_items:
            name = item_data.get('display_name', item_key)
            price = item_data.get('price', 0)
            xp_cost = item_data.get('xp_cost', 0)
            desc = item_data.get('description', 'N/A')
            quantity = item_data.get('quantity', -1)
            qty_str = "Infinie" if quantity == -1 else str(quantity)
            emoji = config.get('currency_emoji', '💰')
            currency_name = config.get('currency_name', 'Points')
            
            reward_parts = []
            role_id = item_data.get('role_id')
            xp_gain = item_data.get('xp_gain', 0)
            if role_id and (role := interaction.guild.get_role(role_id)):
                reward_parts.append(f"Rôle {role.mention}")
            if xp_gain > 0:
                reward_parts.append(f"**{xp_gain}** ✨ XP")
            reward_str = " | Récompense: " + ", ".join(reward_parts) if reward_parts else ""

            cost_parts = []
            if price > 0:
                cost_parts.append(f"**{price}** {emoji}{currency_name}")
            if xp_cost > 0:
                cost_parts.append(f"**{xp_cost}** ✨ XP")
            cost_str = " et ".join(cost_parts) if cost_parts else "Gratuit"
            
            description += f"**{name}**{reward_str}\n> *{discord.utils.escape_markdown(desc)}*\n> **Coût :** {cost_str} | **Quantité :** `{qty_str}`\n\n"
        
        embed.description = description
        await interaction.response.send_message(embed=embed)

    @boutique_group.command(name="acheter", description="Acheter un article de la boutique.")
    @app_commands.describe(article="Le nom de l'article que vous voulez acheter.")
    async def boutique_acheter(self, interaction: discord.Interaction, article: str):
        await interaction.response.send_message(f"Fonctionnalité d'achat pour **{article}** en cours de développement !", ephemeral=True)

    # =============================================
    # ==      COMMANDES ADMIN POUR LA BOUTIQUE   ==
    # =============================================
    
    @boutique_group.command(name="configurer", description="Configure les paramètres de base de la boutique.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        nom_monnaie="Le nom de la monnaie utilisée (ex: Points).",
        emoji_monnaie="L'emoji pour la monnaie (ex: 💰)."
    )
    async def boutique_configurer(self, interaction: discord.Interaction, nom_monnaie: str, emoji_monnaie: str):
        guild_data = self.get_guild_shop_data(interaction.guild.id)
        config = guild_data["config"]
        config["currency_name"] = nom_monnaie
        config["currency_emoji"] = emoji_monnaie
        save_data(SHOP_DATA_FILE, self.shop_data)
        await interaction.response.send_message(f"✅ La monnaie de la boutique a été définie sur : {emoji_monnaie} {nom_monnaie}", ephemeral=True)

    @boutique_group.command(name="créer-item", description="Crée un nouvel article pour la boutique.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        nom="Le nom de l'article (unique).",
        description="Une courte description de l'article.",
        prix="Optionnel : Le prix dans la monnaie du serveur.",
        cout_xp="Optionnel : Le coût en points d'expérience (XP).",
        role_recompense="Optionnel : Le rôle que cet article donne à l'achat.",
        xp_a_donner="Optionnel : La quantité d'XP que cet article donne à l'achat.",
        quantite="Optionnel : Quantité disponible (-1 ou vide pour infini)."
    )
    async def boutique_creer_item(self, interaction: discord.Interaction,
                                  nom: str,
                                  description: str,
                                  prix: Optional[app_commands.Range[int, 0, None]] = None,
                                  cout_xp: Optional[app_commands.Range[int, 0, None]] = None,
                                  role_recompense: Optional[discord.Role] = None,
                                  xp_a_donner: Optional[app_commands.Range[int, 1, None]] = None,
                                  quantite: Optional[app_commands.Range[int, -1, None]] = -1):
        
        prix_val = prix if prix is not None else 0
        xp_val = cout_xp if cout_xp is not None else 0
        xp_gain_val = xp_a_donner if xp_a_donner is not None else 0

        if prix_val <= 0 and xp_val <= 0:
            await interaction.response.send_message("❌ L'article doit avoir un coût ! Spécifiez un `prix` ou un `cout_xp`.", ephemeral=True); return
        if not role_recompense and xp_gain_val <= 0:
            await interaction.response.send_message("❌ L'article doit avoir une récompense ! Spécifiez un `role_recompense` ou `xp_a_donner`.", ephemeral=True); return

        guild_data = self.get_guild_shop_data(interaction.guild.id)
        items = guild_data["items"]
        item_key = nom.lower().strip()

        if item_key in items:
            await interaction.response.send_message(f"❌ Un article nommé `{nom}` existe déjà.", ephemeral=True); return

        if role_recompense and role_recompense >= interaction.guild.me.top_role:
            await interaction.response.send_message(f"❌ Je ne peux pas gérer le rôle {role_recompense.mention}.", ephemeral=True); return

        items[item_key] = {
            "display_name": nom, "description": description, "price": prix_val, "xp_cost": xp_val,
            "role_id": role_recompense.id if role_recompense else None, "xp_gain": xp_gain_val,
            "quantity": quantite, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        save_data(SHOP_DATA_FILE, self.shop_data)

        config = guild_data.get("config", {}); currency_emoji = config.get('currency_emoji', '💰')
        cost_parts = []
        if prix_val > 0: cost_parts.append(f"{prix_val}{currency_emoji}")
        if xp_val > 0: cost_parts.append(f"{xp_val}✨ XP")
        cost_str = " et ".join(cost_parts)

        reward_parts = []
        if role_recompense: reward_parts.append(f"le rôle {role_recompense.mention}")
        if xp_gain_val > 0: reward_parts.append(f"**{xp_gain_val}**✨ XP")
        reward_str = " et ".join(reward_parts)

        await interaction.response.send_message(
            f"✅ Article `{nom}` ajouté !\n**Coût :** {cost_str}\n**Récompense :** {reward_str}", 
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @boutique_group.command(name="supprimer-item", description="Supprime un article de la boutique.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(article="Le nom de l'article à supprimer.")
    async def boutique_supprimer_item(self, interaction: discord.Interaction, article: str):
        guild_data = self.get_guild_shop_data(interaction.guild.id)
        items = guild_data["items"]
        item_key_to_delete = article.lower().strip()

        if item_key_to_delete not in items:
            await interaction.response.send_message(f"❌ L'article `{article}` n'a pas été trouvé.", ephemeral=True); return
            
        display_name = items[item_key_to_delete].get("display_name", article)
        del items[item_key_to_delete]
        save_data(SHOP_DATA_FILE, self.shop_data)
        
        await interaction.response.send_message(f"🗑️ L'article `{display_name}` a été supprimé de la boutique.", ephemeral=True)

# --- Setup du Cog ---
async def setup(bot: commands.Bot):
    # CORRECTION : Le __init__ de ShopCog n'a pas besoin de db_manager pour l'instant
    # Si la commande /acheter est implémentée, il faudra le passer comme pour les autres cogs.
    await bot.add_cog(ShopCog(bot))
    print("Cog Boutique (corrigé) chargé.")