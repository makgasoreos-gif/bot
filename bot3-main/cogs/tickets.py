import discord
from discord import app_commands
from discord.ext import commands

from utils.db import get_config, update_config, DB_PATH
import aiosqlite


class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Open a Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        await cog.create_ticket(interaction)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        await cog.close_ticket(interaction)


class Tickets(commands.Cog):
    """Button-based support ticket system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketButtonView())
        bot.add_view(CloseTicketView())

    group = app_commands.Group(name="ticket", description="Ticket system setup")

    @group.command(name="setup", description="Post the ticket-opening panel in this channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_panel(self, interaction: discord.Interaction, category: discord.CategoryChannel,
                           support_role: discord.Role, log_channel: discord.TextChannel = None):
        await update_config(
            interaction.guild_id,
            ticket_category_id=category.id,
            ticket_support_role_id=support_role.id,
            ticket_log_channel_id=log_channel.id if log_channel else None,
        )
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to open a private ticket with our team.",
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=TicketButtonView())
        await interaction.response.send_message("✅ Ticket panel posted.", ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        cfg = await get_config(guild.id)
        category_id = cfg.get("ticket_category_id")
        support_role_id = cfg.get("ticket_support_role_id")

        if not category_id:
            await interaction.response.send_message("Ticket system isn't configured yet.", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        support_role = guild.get_role(support_role_id) if support_role_id else None

        existing = discord.utils.get(category.channels, name=f"ticket-{interaction.user.name}".lower())
        if existing:
            await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket for {interaction.user.id}",
        )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO tickets (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
                (channel.id, guild.id, interaction.user.id),
            )
            await db.commit()

        embed = discord.Embed(
            title="🎫 New Ticket",
            description=f"{interaction.user.mention}, support will be with you shortly.\nClick below to close this ticket.",
            color=discord.Color.green(),
        )
        await channel.send(content=support_role.mention if support_role else None, embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        cfg = await get_config(interaction.guild_id)
        log_channel_id = cfg.get("ticket_log_channel_id")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (channel.id,))
            await db.commit()

        await interaction.response.send_message("🔒 Closing this ticket in 5 seconds...")

        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(f"Ticket `{channel.name}` closed by {interaction.user}.")

        import asyncio
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket closed by {interaction.user}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
