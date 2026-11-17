import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_config, update_config


class Welcome(commands.Cog):
    """Welcome / leave messages and auto-role on join."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="welcome", description="Welcome & auto-role setup")

    @group.command(name="setchannel", description="Set the welcome channel and message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel,
                          message: str = "Welcome {mention} to {server}! 🎉"):
        await update_config(interaction.guild_id, welcome_channel_id=channel.id, welcome_message=message)
        await interaction.response.send_message(
            f"✅ Welcome messages will be sent in {channel.mention}.\nPlaceholders: `{{mention}}`, `{{user}}`, `{{server}}`, `{{membercount}}`",
            ephemeral=True,
        )

    @group.command(name="setleave", description="Set the leave channel and message")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setleave(self, interaction: discord.Interaction, channel: discord.TextChannel,
                        message: str = "{user} has left the server."):
        await update_config(interaction.guild_id, leave_channel_id=channel.id, leave_message=message)
        await interaction.response.send_message(f"✅ Leave messages will be sent in {channel.mention}.", ephemeral=True)

    @group.command(name="setautorole", description="Set a role to auto-assign to new members")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        await update_config(interaction.guild_id, autorole_id=role.id)
        await interaction.response.send_message(f"✅ New members will receive {role.mention} automatically.", ephemeral=True)

    @group.command(name="disable", description="Disable welcome, leave, or autorole")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(feature=[
        app_commands.Choice(name="welcome", value="welcome_channel_id"),
        app_commands.Choice(name="leave", value="leave_channel_id"),
        app_commands.Choice(name="autorole", value="autorole_id"),
    ])
    async def disable(self, interaction: discord.Interaction, feature: app_commands.Choice[str]):
        await update_config(interaction.guild_id, **{feature.value: None})
        await interaction.response.send_message(f"✅ Disabled `{feature.name}`.", ephemeral=True)

    def _format(self, template: str, member: discord.Member) -> str:
        return template.format(
            mention=member.mention,
            user=str(member),
            server=member.guild.name,
            membercount=member.guild.member_count,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await get_config(member.guild.id)

        if cfg.get("autorole_id"):
            role = member.guild.get_role(cfg["autorole_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except discord.Forbidden:
                    pass

        if cfg.get("welcome_channel_id"):
            channel = member.guild.get_channel(cfg["welcome_channel_id"])
            if channel:
                text = self._format(cfg.get("welcome_message") or "Welcome {mention}!", member)
                embed = discord.Embed(description=text, color=discord.Color.green())
                embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = await get_config(member.guild.id)
        if cfg.get("leave_channel_id"):
            channel = member.guild.get_channel(cfg["leave_channel_id"])
            if channel:
                text = self._format(cfg.get("leave_message") or "{user} left.", member)
                embed = discord.Embed(description=text, color=discord.Color.red())
                await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
