import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_config, update_config, DB_PATH
import aiosqlite

UPVOTE = "👍"
DOWNVOTE = "👎"


class Suggestions(commands.Cog):
    """Members submit suggestions that get posted for the server to vote on."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="suggestions", description="Suggestions system setup")

    @group.command(name="setchannel", description="Set the channel where suggestions are posted")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_config(interaction.guild_id, suggestions_channel_id=channel.id)
        await interaction.response.send_message(f"✅ Suggestions will be posted in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="suggest", description="Submit a suggestion for the server to vote on")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        cfg = await get_config(interaction.guild_id)
        channel_id = cfg.get("suggestions_channel_id")
        if not channel_id:
            await interaction.response.send_message(
                "Suggestions aren't set up yet. Ask an admin to run `/suggestions setchannel`.", ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Configured suggestions channel no longer exists.", ephemeral=True)
            return

        embed = discord.Embed(description=suggestion, color=discord.Color.blurple())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Pending")
        message = await channel.send(embed=embed)
        await message.add_reaction(UPVOTE)
        await message.add_reaction(DOWNVOTE)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO suggestions (guild_id, message_id, user_id, content) VALUES (?, ?, ?, ?)",
                (interaction.guild_id, message.id, interaction.user.id, suggestion),
            )
            await db.commit()

        await interaction.response.send_message(f"✅ Suggestion posted in {channel.mention}!", ephemeral=True)

    @app_commands.command(name="resolve", description="Mark a suggestion as approved or rejected")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(status=[
        app_commands.Choice(name="approved", value="approved"),
        app_commands.Choice(name="rejected", value="rejected"),
    ])
    async def resolve(self, interaction: discord.Interaction, message_id: str, status: app_commands.Choice[str]):
        cfg = await get_config(interaction.guild_id)
        channel_id = cfg.get("suggestions_channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else None

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE suggestions SET status = ? WHERE guild_id = ? AND message_id = ?",
                (status.value, interaction.guild_id, int(message_id)),
            )
            await db.commit()

        if channel:
            try:
                message = await channel.fetch_message(int(message_id))
                embed = message.embeds[0]
                color = discord.Color.green() if status.value == "approved" else discord.Color.red()
                embed.color = color
                embed.set_footer(text=f"{status.name.capitalize()} by {interaction.user}")
                await message.edit(embed=embed)
            except (discord.NotFound, IndexError):
                pass

        await interaction.response.send_message(f"✅ Suggestion marked as **{status.name}**.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
