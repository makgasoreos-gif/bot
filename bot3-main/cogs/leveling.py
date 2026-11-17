import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import DB_PATH
import aiosqlite

XP_COOLDOWN_SECONDS = 60
XP_MIN, XP_MAX = 10, 20


def xp_for_level(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


class Leveling(commands.Cog):
    """Gains XP from chatting, tracks levels, and shows a leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
                (message.guild.id, message.author.id),
            )
            row = await cur.fetchone()
            now = time.time()

            if row and now - row["last_message_at"] < XP_COOLDOWN_SECONDS:
                return

            xp_gain = random.randint(XP_MIN, XP_MAX)
            if row:
                new_xp = row["xp"] + xp_gain
                level = row["level"]
                leveled_up = False
                while new_xp >= xp_for_level(level):
                    new_xp -= xp_for_level(level)
                    level += 1
                    leveled_up = True
                await db.execute(
                    "UPDATE levels SET xp = ?, level = ?, last_message_at = ? WHERE guild_id = ? AND user_id = ?",
                    (new_xp, level, now, message.guild.id, message.author.id),
                )
            else:
                level = 0
                new_xp = xp_gain
                leveled_up = False
                await db.execute(
                    "INSERT INTO levels (guild_id, user_id, xp, level, last_message_at) VALUES (?, ?, ?, ?, ?)",
                    (message.guild.id, message.author.id, new_xp, level, now),
                )
            await db.commit()

        if leveled_up:
            try:
                await message.channel.send(
                    f"🎉 {message.author.mention} leveled up to **level {level}**!"
                )
            except discord.Forbidden:
                pass

    @app_commands.command(name="rank", description="Show your (or someone else's) level and XP")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, member.id),
            )
            row = await cur.fetchone()
        if not row:
            await interaction.response.send_message(f"{member.mention} hasn't earned any XP yet.")
            return
        needed = xp_for_level(row["level"])
        embed = discord.Embed(title=f"Rank — {member.display_name}", color=discord.Color.blurple())
        embed.add_field(name="Level", value=str(row["level"]))
        embed.add_field(name="XP", value=f"{row['xp']} / {needed}")
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the server's XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
                (interaction.guild_id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No one has earned XP yet.")
            return
        lines = []
        for i, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"**{i}.** {name} — Level {row['level']} ({row['xp']} XP)")
        embed = discord.Embed(title="🏆 Leaderboard", description="\n".join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
