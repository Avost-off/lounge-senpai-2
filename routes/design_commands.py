# cogs/design_commands.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List, Union
import traceback

# ----- Styles Prédéfinis -----
TEXT_CHANNEL_STYLES: Dict[str, str] = {
    "simple_arrow": "➔・{name}", "simple_dot": "・{name}", "line_arrow": "➥・{name}",
    "double_arrow": "»・{name}", "star": "⭐︱{name}", "chat_bubble": "💬︱{name}",
    "hash": "# {name}", "announcement": "📢︱{name}", "rules": "📜︱{name}",
    "bracket": "[ {name} ]", "emoji_sparkles": "✨・{name}", "emoji_game": "🎮︱{name}",
}

VOICE_CHANNEL_STYLES: Dict[str, str] = {
    **TEXT_CHANNEL_STYLES,
    "voice_dot": "🔊・{name}", "headphone": "🎧︱{name}", "music": "🎵︱{name}",
    "stage": "🎤・{name}", "afk": "💤︱{name}",
}

CATEGORY_STYLES: Dict[str, str] = {
    "section_line": "╭─── ・ {name}", "section_heavy": "┏━━━ ・ {name}",
    "title_bold": "︱**{name}**︱", "title_upper": "{name}",
    "divider_dots": "﹒﹒﹒{name}﹒﹒﹒", "arrow_section": "》 {name} 《",
    "boxed_title": "┌──** {name} **──┐", "emoji_folder": "📁 {name}",
}

def create_choices(style_dict: Dict[str, str]) -> List[app_commands.Choice[str]]:
    choices = []
    for key, template in list(style_dict.items())[:25]:
        readable_name = key.replace("_", " ").title()
        preview = template.format(name="Nom")
        choice_name = f"{readable_name} ({preview})"
        if len(choice_name) > 100: choice_name = choice_name[:97] + "..."
        choices.append(app_commands.Choice(name=choice_name, value=key))
    return choices

# ----- Classe Cog -----
class DesignCommandsCog(commands.Cog, name="Outils de Design"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _apply_design(self, interaction: discord.Interaction, target: Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel], style_key: str, styles_dict: Dict[str, str], nom_base: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        
        template = styles_dict.get(style_key)
        if not template: await interaction.followup.send(f"❌ Style '{style_key}' introuvable.", ephemeral=True); return

        base_name = (nom_base or target.name).strip()
        if not base_name: await interaction.followup.send("❌ Le nom de base est vide.", ephemeral=True); return
        
        if style_key == "title_upper" and isinstance(target, discord.CategoryChannel): new_name = base_name.upper()
        else: new_name = template.format(name=base_name)

        if len(new_name) > 100:
            await interaction.followup.send(f"❌ Nom trop long ({len(new_name)}/100).", ephemeral=True); return

        original_name = target.name
        try:
            await target.edit(name=new_name, reason=f"Design par {interaction.user}")
            await interaction.followup.send(f"✅ Design appliqué !\n**Avant :** `{original_name}`\n**Après :** `{new_name}`", ephemeral=True)
        except discord.Forbidden: await interaction.followup.send(f"❌ Permission refusée pour renommer `{target.name}`.", ephemeral=True)
        except Exception as e: await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True); traceback.print_exc()

    AnyTextChannel = Union[discord.TextChannel, discord.ForumChannel, discord.StageChannel]
    AnyVoiceChannel = Union[discord.VoiceChannel, discord.StageChannel]

    @app_commands.command(name="design-textuel", description="Applique un style au nom d'un salon textuel.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.choices(style=create_choices(TEXT_CHANNEL_STYLES))
    async def design_textuel(self, interaction: discord.Interaction, salon: AnyTextChannel, style: str, nom_base: Optional[str] = None):
        await self._apply_design(interaction, salon, style, TEXT_CHANNEL_STYLES, nom_base)

    @app_commands.command(name="design-vocal", description="Applique un style au nom d'un salon vocal.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.choices(style=create_choices(VOICE_CHANNEL_STYLES))
    async def design_vocal(self, interaction: discord.Interaction, salon: AnyVoiceChannel, style: str, nom_base: Optional[str] = None):
        await self._apply_design(interaction, salon, style, VOICE_CHANNEL_STYLES, nom_base)

    @app_commands.command(name="design-categorie", description="Applique un style au nom d'une catégorie.")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.choices(style=create_choices(CATEGORY_STYLES))
    async def design_categorie(self, interaction: discord.Interaction, categorie: discord.CategoryChannel, style: str, nom_base: Optional[str] = None):
        await self._apply_design(interaction, categorie, style, CATEGORY_STYLES, nom_base)

# --- Setup du Cog ---
async def setup(bot: commands.Bot):
    await bot.add_cog(DesignCommandsCog(bot))
    print("Cog DesignCommands chargé.")