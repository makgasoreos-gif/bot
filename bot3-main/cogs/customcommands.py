import discord
from discord import app_commands
from discord.ext import commands

from utils.db import DB_PATH
import aiosqlite


class CustomCommands(commands.Cog):
    """Server-defined text-trigger commands, e.g. !rules -> posts the rules text."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="cc", description="Manage custom commands")

    @group.command(name="add", description="Add a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self, interaction: discord.Interaction, name: str, response: str):
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO custom_commands (guild_id, name, response) VALUES (?, ?, ?)",
                (interaction.guild_id, name, response),
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Custom command `{name}` added.", ephemeral=True)

    @group.command(name="remove", description="Remove a custom command")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, name: str):
        name = name.lower().strip()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM custom_commands WHERE guild_id = ? AND name = ?",
                (interaction.guild_id, name),
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Custom command `{name}` removed.", ephemeral=True)

    @group.command(name="list", description="List all custom commands")
    async def list_commands(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT name FROM custom_commands WHERE guild_id = ? ORDER BY name",
                (interaction.guild_id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No custom commands set up yet.", ephemeral=True)
            return
        names = ", ".join(f"`{r['name']}`" for r in rows)
        await interaction.response.send_message(f"Custom commands: {names}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        prefix = self.bot.command_prefix
        if isinstance(prefix, str) and message.content.startswith(prefix):
            trigger = message.content[len(prefix):].split()[0].lower() if message.content[len(prefix):] else ""
            if not trigger:
                return
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT response FROM custom_commands WHERE guild_id = ? AND name = ?",
                    (message.guild.id, trigger),
                )
                row = await cur.fetchone()
            if row:
                await message.channel.send(row["response"])


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomCommands(bot))
