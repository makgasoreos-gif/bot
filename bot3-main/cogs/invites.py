import discord
from discord import app_commands
from discord.ext import commands

from utils.db import DB_PATH
import aiosqlite


class Invites(commands.Cog):
    """Tracks who invited whom and shows an invite leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache: dict[int, dict[str, int]] = {}  # guild_id -> {invite_code: uses}

    async def _cache_guild_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
            self.invite_cache[guild.id] = {inv.code: inv.uses or 0 for inv in invites}
        except discord.Forbidden:
            self.invite_cache[guild.id] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._cache_guild_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._cache_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        self.invite_cache.setdefault(invite.guild.id, {}).pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        before = self.invite_cache.get(guild.id, {})
        try:
            after_invites = await guild.invites()
        except discord.Forbidden:
            return

        used_invite = None
        for inv in after_invites:
            if inv.uses and inv.uses > before.get(inv.code, 0):
                used_invite = inv
                break

        self.invite_cache[guild.id] = {inv.code: inv.uses or 0 for inv in after_invites}

        if used_invite and used_invite.inviter:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO invite_uses (guild_id, inviter_id, uses) VALUES (?, ?, 1) "
                    "ON CONFLICT(guild_id, inviter_id) DO UPDATE SET uses = uses + 1",
                    (guild.id, used_invite.inviter.id),
                )
                await db.commit()

    @app_commands.command(name="invites", description="Show how many members someone has invited")
    async def invites(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT uses FROM invite_uses WHERE guild_id = ? AND inviter_id = ?",
                (interaction.guild_id, member.id),
            )
            row = await cur.fetchone()
        count = row["uses"] if row else 0
        await interaction.response.send_message(f"📨 {member.mention} has invited **{count}** member(s).")

    @app_commands.command(name="inviteleaderboard", description="Show the server's top inviters")
    async def invite_leaderboard(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM invite_uses WHERE guild_id = ? ORDER BY uses DESC LIMIT 10",
                (interaction.guild_id,),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message("No invite data yet.")
            return
        lines = []
        for i, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["inviter_id"])
            name = member.display_name if member else f"User {row['inviter_id']}"
            lines.append(f"**{i}.** {name} — {row['uses']} invite(s)")
        embed = discord.Embed(title="📨 Invite Leaderboard", description="\n".join(lines), color=discord.Color.teal())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Invites(bot))
