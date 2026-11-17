import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import get_config, update_config, DB_PATH
import aiosqlite


class Birthdays(commands.Cog):
    """Lets members set their birthday and auto-announces it on the day."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()

    group = app_commands.Group(name="birthday", description="Birthday tracker")

    @group.command(name="set", description="Set your birthday (announced every year)")
    async def set_birthday(self, interaction: discord.Interaction, month: app_commands.Range[int, 1, 12],
                            day: app_commands.Range[int, 1, 31]):
        try:
            datetime.date(2024, month, day)  # validate, using a leap year
        except ValueError:
            await interaction.response.send_message("That's not a valid date.", ephemeral=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO birthdays (guild_id, user_id, month, day) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET month = excluded.month, day = excluded.day",
                (interaction.guild_id, interaction.user.id, month, day),
            )
            await db.commit()
        await interaction.response.send_message(f"🎂 Birthday set to **{month:02d}/{day:02d}**.", ephemeral=True)

    @group.command(name="remove", description="Remove your saved birthday")
    async def remove_birthday(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM birthdays WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, interaction.user.id),
            )
            await db.commit()
        await interaction.response.send_message("✅ Birthday removed.", ephemeral=True)

    @group.command(name="setchannel", description="Set the channel for birthday announcements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_config(interaction.guild_id, birthday_channel_id=channel.id)
        await interaction.response.send_message(f"✅ Birthdays will be announced in {channel.mention}.", ephemeral=True)

    @group.command(name="list", description="List upcoming birthdays this month")
    async def list_birthdays(self, interaction: discord.Interaction):
        today = datetime.date.today()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM birthdays WHERE guild_id = ? AND month = ? ORDER BY day",
                (interaction.guild_id, today.month),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No birthdays recorded this month.", ephemeral=True)
            return
        lines = []
        for row in rows:
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"**{row['day']:02d}/{row['month']:02d}** — {name}")
        embed = discord.Embed(title="🎂 Birthdays this month", description="\n".join(lines), color=discord.Color.pink())
        await interaction.response.send_message(embed=embed)

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        today = datetime.date.today()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM birthdays WHERE month = ? AND day = ? AND (last_announced_year IS NULL OR last_announced_year != ?)",
                (today.month, today.day, today.year),
            )
            rows = await cur.fetchall()

            for row in rows:
                guild = self.bot.get_guild(row["guild_id"])
                if not guild:
                    continue
                member = guild.get_member(row["user_id"])
                if not member:
                    continue
                cfg = await get_config(guild.id)
                channel_id = cfg.get("birthday_channel_id")
                if channel_id:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        embed = discord.Embed(
                            description=f"🎉🎂 Happy Birthday {member.mention}! Have a great day!",
                            color=discord.Color.pink(),
                        )
                        try:
                            await channel.send(embed=embed)
                        except discord.Forbidden:
                            pass
                await db.execute(
                    "UPDATE birthdays SET last_announced_year = ? WHERE guild_id = ? AND user_id = ?",
                    (today.year, row["guild_id"], row["user_id"]),
                )
            await db.commit()

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Birthdays(bot))
