import time
import collections

import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_config, update_config


class AntiRaid(commands.Cog):
    """Detects join spikes (raids) and auto-locks the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> deque of join timestamps
        self.join_times: dict[int, collections.deque] = collections.defaultdict(collections.deque)
        self.locked_guilds: set[int] = set()

    group = app_commands.Group(name="antiraid", description="Anti-raid protection settings")

    @group.command(name="enable", description="Enable anti-raid protection")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def enable(self, interaction: discord.Interaction):
        await update_config(interaction.guild_id, antiraid_enabled=1)
        await interaction.response.send_message("🛡️ Anti-raid protection **enabled**.", ephemeral=True)

    @group.command(name="disable", description="Disable anti-raid protection")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def disable(self, interaction: discord.Interaction):
        await update_config(interaction.guild_id, antiraid_enabled=0)
        await interaction.response.send_message("Anti-raid protection **disabled**.", ephemeral=True)

    @group.command(name="settings", description="Set the join-spike threshold that triggers lockdown")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings(self, interaction: discord.Interaction, joins: app_commands.Range[int, 2, 50],
                        seconds: app_commands.Range[int, 3, 120]):
        await update_config(interaction.guild_id, antiraid_threshold=joins, antiraid_window_seconds=seconds)
        await interaction.response.send_message(
            f"✅ Will lock the server if **{joins}** members join within **{seconds}s**.", ephemeral=True
        )

    @group.command(name="unlock", description="Manually lift a raid lockdown")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unlock(self, interaction: discord.Interaction):
        await self._unlock(interaction.guild)
        await interaction.response.send_message("🔓 Server unlocked.", ephemeral=True)

    async def _lockdown(self, guild: discord.Guild):
        self.locked_guilds.add(guild.id)
        everyone = guild.default_role
        try:
            perms = everyone.permissions
            perms.update(create_instant_invite=False)
            await everyone.edit(permissions=perms, reason="Anti-raid lockdown")
        except discord.Forbidden:
            pass

        cfg = await get_config(guild.id)
        if cfg.get("mod_log_channel_id"):
            channel = guild.get_channel(cfg["mod_log_channel_id"])
            if channel:
                embed = discord.Embed(
                    title="🚨 Raid Detected — Server Locked",
                    description="A large number of members joined in a short time. Invites have been paused.\n"
                                "Use `/antiraid unlock` once you've reviewed the new members.",
                    color=discord.Color.red(),
                )
                await channel.send(embed=embed)

    async def _unlock(self, guild: discord.Guild):
        self.locked_guilds.discard(guild.id)
        everyone = guild.default_role
        try:
            perms = everyone.permissions
            perms.update(create_instant_invite=True)
            await everyone.edit(permissions=perms, reason="Anti-raid unlock")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        cfg = await get_config(guild.id)
        if not cfg.get("antiraid_enabled"):
            return

        threshold = cfg.get("antiraid_threshold") or 5
        window = cfg.get("antiraid_window_seconds") or 10
        now = time.time()

        dq = self.join_times[guild.id]
        dq.append(now)
        while dq and now - dq[0] > window:
            dq.popleft()

        if len(dq) >= threshold and guild.id not in self.locked_guilds:
            await self._lockdown(guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
