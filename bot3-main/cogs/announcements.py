import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import DB_PATH
import aiosqlite


class Announcements(commands.Cog):
    """Recurring scheduled announcements, e.g. every Monday at a set interval."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_announcements.start()

    def cog_unload(self):
        self.check_announcements.cancel()

    group = app_commands.Group(name="announce", description="Scheduled recurring announcements")

    @group.command(name="add", description="Add a recurring announcement")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str,
                  interval_minutes: app_commands.Range[int, 5, 43200]):
        next_run = time.time() + interval_minutes * 60
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "INSERT INTO scheduled_announcements (guild_id, channel_id, message, interval_minutes, next_run) "
                "VALUES (?, ?, ?, ?, ?)",
                (interaction.guild_id, channel.id, message, interval_minutes, next_run),
            )
            await db.commit()
            new_id = cur.lastrowid
        await interaction.response.send_message(
            f"✅ Announcement `#{new_id}` will post in {channel.mention} every **{interval_minutes} minutes**.",
            ephemeral=True,
        )

    @group.command(name="remove", description="Remove a scheduled announcement by ID")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove(self, interaction: discord.Interaction, announcement_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM scheduled_announcements WHERE id = ? AND guild_id = ?",
                (announcement_id, interaction.guild_id),
            )
            await db.commit()
        await interaction.response.send_message("✅ Removed.", ephemeral=True)

    @group.command(name="list", description="List scheduled announcements")
    async def list_announcements(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM scheduled_announcements WHERE guild_id = ?", (interaction.guild_id,)
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No scheduled announcements.", ephemeral=True)
            return
        lines = []
        for row in rows:
            channel = interaction.guild.get_channel(row["channel_id"])
            chan_name = channel.mention if channel else f"#{row['channel_id']}"
            lines.append(f"**#{row['id']}** {chan_name} every {row['interval_minutes']}min — {row['message'][:50]}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @tasks.loop(seconds=60)
    async def check_announcements(self):
        now = time.time()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM scheduled_announcements WHERE next_run <= ?", (now,))
            rows = await cur.fetchall()
            for row in rows:
                new_next_run = now + row["interval_minutes"] * 60
                await db.execute(
                    "UPDATE scheduled_announcements SET next_run = ? WHERE id = ?",
                    (new_next_run, row["id"]),
                )
            await db.commit()

        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])
            if channel:
                try:
                    await channel.send(row["message"])
                except discord.Forbidden:
                    pass

    @check_announcements.before_loop
    async def before_check_announcements(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Announcements(bot))
