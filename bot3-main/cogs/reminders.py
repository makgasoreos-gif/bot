import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import DB_PATH
from cogs.giveaways import parse_duration
import aiosqlite


class Reminders(commands.Cog):
    """Personal reminders — /remindme 30m take the pizza out."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @app_commands.command(name="remindme", description="Set a personal reminder, e.g. /remindme 30m stretch")
    async def remindme(self, interaction: discord.Interaction, duration: str, text: str):
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        remind_at = time.time() + seconds
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO reminders (user_id, channel_id, guild_id, remind_at, text) VALUES (?, ?, ?, ?, ?)",
                (interaction.user.id, interaction.channel_id, interaction.guild_id, remind_at, text),
            )
            await db.commit()

        await interaction.response.send_message(
            f"⏰ Got it — I'll remind you <t:{int(remind_at)}:R>.", ephemeral=True
        )

    @app_commands.command(name="reminders", description="List your pending reminders")
    async def reminders(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM reminders WHERE user_id = ? AND done = 0 ORDER BY remind_at",
                (interaction.user.id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("You have no pending reminders.", ephemeral=True)
            return
        lines = [f"**#{r['id']}** <t:{int(r['remind_at'])}:R> — {r['text']}" for r in rows]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="cancelreminder", description="Cancel a pending reminder by ID")
    async def cancelreminder(self, interaction: discord.Interaction, reminder_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, interaction.user.id),
            )
            await db.commit()
        await interaction.response.send_message("✅ Reminder cancelled.", ephemeral=True)

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = time.time()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM reminders WHERE done = 0 AND remind_at <= ?", (now,))
            rows = await cur.fetchall()
            for row in rows:
                await db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (row["id"],))
            await db.commit()

        for row in rows:
            channel = self.bot.get_channel(row["channel_id"])
            user = self.bot.get_user(row["user_id"])
            if channel and user:
                try:
                    await channel.send(f"⏰ {user.mention}, reminder: {row['text']}")
                    continue
                except discord.Forbidden:
                    pass
            if user:
                try:
                    await user.send(f"⏰ Reminder: {row['text']}")
                except discord.Forbidden:
                    pass

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminders(bot))
