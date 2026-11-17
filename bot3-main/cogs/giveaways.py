import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.db import DB_PATH
import aiosqlite

UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> int:
    """Parses '10m', '2h', '1d' into seconds."""
    text = text.strip().lower()
    unit = text[-1]
    if unit not in UNIT_SECONDS:
        raise ValueError("Duration must end in m (minutes), h (hours), or d (days), e.g. 30m, 2h, 1d")
    amount = int(text[:-1])
    return amount * UNIT_SECONDS[unit]


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="giveaway_enter_button")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM giveaways WHERE message_id = ? AND ended = 0",
                (interaction.message.id,),
            )
            giveaway = await cur.fetchone()
            if not giveaway:
                await interaction.response.send_message("This giveaway has ended.", ephemeral=True)
                return

            cur = await db.execute(
                "SELECT 1 FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
                (interaction.message.id, interaction.user.id),
            )
            already = await cur.fetchone()
            if already:
                await db.execute(
                    "DELETE FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
                    (interaction.message.id, interaction.user.id),
                )
                await db.commit()
                await interaction.response.send_message("❌ You left the giveaway.", ephemeral=True)
                return

            await db.execute(
                "INSERT INTO giveaway_entries (message_id, user_id) VALUES (?, ?)",
                (interaction.message.id, interaction.user.id),
            )
            await db.commit()
        await interaction.response.send_message("🎉 You're entered! Click again to leave.", ephemeral=True)


class Giveaways(commands.Cog):
    """Button-based giveaways with automatic winner selection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(GiveawayView())
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, prize: str, duration: str,
                        winners: app_commands.Range[int, 1, 20] = 1):
        try:
            seconds = parse_duration(duration)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        end_time = time.time() + seconds
        embed = discord.Embed(
            title="🎉 Giveaway!",
            description=f"**Prize:** {prize}\n**Winners:** {winners}\n"
                        f"Ends: <t:{int(end_time)}:R>\n\nClick the button below to enter!",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Hosted by {interaction.user}")
        await interaction.response.send_message(embed=embed, view=GiveawayView())
        message = await interaction.original_response()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners_count, end_time, host_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (message.id, interaction.guild_id, interaction.channel_id, prize, winners, end_time, interaction.user.id),
            )
            await db.commit()

    @app_commands.command(name="giveawayend", description="End a giveaway early")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveawayend(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.send_message("Ending giveaway...", ephemeral=True)
        await self._finish_giveaway(int(message_id))

    async def _finish_giveaway(self, message_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE message_id = ? AND ended = 0", (message_id,))
            giveaway = await cur.fetchone()
            if not giveaway:
                return

            cur = await db.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (message_id,))
            entrants = [r["user_id"] for r in await cur.fetchall()]

            await db.execute("UPDATE giveaways SET ended = 1 WHERE message_id = ?", (message_id,))
            await db.commit()

        guild = self.bot.get_guild(giveaway["guild_id"])
        channel = guild.get_channel(giveaway["channel_id"]) if guild else None
        if not channel:
            return

        winners_count = min(giveaway["winners_count"], len(entrants))
        winners = random.sample(entrants, winners_count) if winners_count > 0 else []

        try:
            message = await channel.fetch_message(message_id)
            embed = message.embeds[0]
            embed.color = discord.Color.dark_grey()
            embed.title = "🎉 Giveaway Ended"
            await message.edit(embed=embed, view=None)
        except discord.NotFound:
            pass

        if winners:
            mentions = ", ".join(f"<@{w}>" for w in winners)
            await channel.send(f"🎉 Congratulations {mentions}! You won **{giveaway['prize']}**!")
        else:
            await channel.send(f"No one entered the giveaway for **{giveaway['prize']}**.")

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = time.time()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT message_id FROM giveaways WHERE ended = 0 AND end_time <= ?", (now,))
            rows = await cur.fetchall()
        for row in rows:
            await self._finish_giveaway(row["message_id"])

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
