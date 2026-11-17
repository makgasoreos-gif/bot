import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_config, update_config, DB_PATH
import aiosqlite


async def log_action(bot, guild: discord.Guild, embed: discord.Embed):
    cfg = await get_config(guild.id)
    channel_id = cfg.get("mod_log_channel_id")
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)


class Moderation(commands.Cog):
    """Kick, ban, mute (timeout), warn, clear, and mod-log setup."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="mod", description="Moderation commands")

    @group.command(name="setlog", description="Set the channel where moderation actions are logged")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setlog(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await update_config(interaction.guild_id, mod_log_channel_id=channel.id)
        await interaction.response.send_message(f"✅ Mod-log set to {channel.mention}", ephemeral=True)

    @group.command(name="kick", description="Kick a member")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange(),
                               timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=str(interaction.user), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction.guild, embed)

    @group.command(name="ban", description="Ban a member")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red(),
                               timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=str(interaction.user), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction.guild, embed)

    @group.command(name="unban", description="Unban a user by ID")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ Unbanned user `{user_id}`")

    @group.command(name="mute", description="Timeout a member for a number of minutes")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int,
                   reason: str = "No reason provided"):
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.dark_orange(),
                               timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="Moderator", value=str(interaction.user), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction.guild, embed)

    @group.command(name="unmute", description="Remove timeout from a member")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"✅ {member.mention} has been unmuted.")

    @group.command(name="warn", description="Warn a member (stored in the database)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
                (interaction.guild_id, member.id, interaction.user.id, reason),
            )
            await db.commit()
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.gold(),
                               timestamp=datetime.datetime.utcnow())
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=str(interaction.user), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, interaction.guild, embed)

    @group.command(name="warnings", description="List a member's warnings")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
                (interaction.guild_id, member.id),
            )
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.gold())
        for row in rows[:15]:
            embed.add_field(
                name=f"#{row['id']} — {row['created_at']}",
                value=f"By <@{row['moderator_id']}>: {row['reason']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
                (interaction.guild_id, member.id),
            )
            await db.commit()
        await interaction.response.send_message(f"✅ Cleared warnings for {member.mention}")

    @group.command(name="clear", description="Bulk delete messages in this channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Deleted {len(deleted)} message(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
