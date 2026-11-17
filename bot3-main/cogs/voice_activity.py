import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import DB_PATH
import aiosqlite


class VoiceActivity(commands.Cog):
    """Tracks time spent in voice channels and shows a leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # (guild_id, user_id) -> join timestamp
        self.sessions: dict[tuple[int, int], float] = {}

    async def _save_time(self, guild_id: int, user_id: int, seconds: int):
        if seconds <= 0:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO voice_time (guild_id, user_id, seconds) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET seconds = seconds + excluded.seconds",
                (guild_id, user_id, seconds),
            )
            await db.commit()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        key = (member.guild.id, member.id)

        if before.channel is None and after.channel is not None:
            self.sessions[key] = time.time()
        elif before.channel is not None and after.channel is None:
            start = self.sessions.pop(key, None)
            if start:
                await self._save_time(member.guild.id, member.id, int(time.time() - start))
        elif before.channel != after.channel and before.channel and after.channel:
            # Switched channels — session continues, no action needed.
            pass

    @app_commands.command(name="voicetime", description="Show time spent in voice channels")
    async def voicetime(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT seconds FROM voice_time WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, member.id),
            )
            row = await cur.fetchone()

        total = row["seconds"] if row else 0
        key = (interaction.guild_id, member.id)
        if key in self.sessions:
            total += int(time.time() - self.sessions[key])

        hours, remainder = divmod(total, 3600)
        minutes, _ = divmod(remainder, 60)
        await interaction.response.send_message(f"🎙️ {member.mention} has spent **{hours}h {minutes}m** in voice channels.")

    @app_commands.command(name="voiceleaderboard", description="Show the server's voice activity leaderboard")
    async def voiceleaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM voice_time WHERE guild_id = ? ORDER BY seconds DESC LIMIT 10",
                (interaction.guild_id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No voice activity recorded yet.")
            return
        lines = []
        for i, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            hours, remainder = divmod(row["seconds"], 3600)
            minutes, _ = divmod(remainder, 60)
            lines.append(f"**{i}.** {name} — {hours}h {minutes}m")
        embed = discord.Embed(title="🎙️ Voice Leaderboard", description="\n".join(lines), color=discord.Color.purple())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceActivity(bot))
