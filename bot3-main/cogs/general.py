import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show everything this bot can do")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Bot Commands",
            color=discord.Color.blurple(),
            description="All commands are available as slash commands (`/`).",
        )
        embed.add_field(
            name="🛡️ Moderation",
            value="`/mod kick` `/mod ban` `/mod unban` `/mod mute` `/mod unmute`\n"
                  "`/mod warn` `/mod warnings` `/mod clearwarnings` `/mod clear` `/mod setlog`",
            inline=False,
        )
        embed.add_field(
            name="👋 Welcome & Auto-role",
            value="`/welcome setchannel` `/welcome setleave` `/welcome setautorole` `/welcome disable`",
            inline=False,
        )
        embed.add_field(
            name="📈 Leveling",
            value="`/rank` `/leaderboard`",
            inline=False,
        )
        embed.add_field(
            name="🎫 Tickets",
            value="`/ticket setup`",
            inline=False,
        )
        embed.add_field(
            name="⚙️ Custom Commands",
            value="`/cc add` `/cc remove` `/cc list`",
            inline=False,
        )
        embed.add_field(
            name="🚨 Anti-raid",
            value="`/antiraid enable` `/antiraid disable` `/antiraid settings` `/antiraid unlock`",
            inline=False,
        )
        embed.add_field(
            name="📨 Invite Tracker",
            value="`/invites` `/inviteleaderboard`",
            inline=False,
        )
        embed.add_field(
            name="🎂 Birthdays",
            value="`/birthday set` `/birthday remove` `/birthday setchannel` `/birthday list`",
            inline=False,
        )
        embed.add_field(
            name="🗳️ Suggestions",
            value="`/suggest` `/suggestions setchannel` `/resolve`",
            inline=False,
        )
        embed.add_field(
            name="🎉 Giveaways",
            value="`/giveaway` `/giveawayend`",
            inline=False,
        )
        embed.add_field(
            name="⏰ Reminders",
            value="`/remindme` `/reminders` `/cancelreminder`",
            inline=False,
        )
        embed.add_field(
            name="🎙️ Voice Activity",
            value="`/voicetime` `/voiceleaderboard`",
            inline=False,
        )
        embed.add_field(
            name="📅 Scheduled Announcements",
            value="`/announce add` `/announce remove` `/announce list`",
            inline=False,
        )
        embed.set_footer(text="Similar to Probot, with extra moderation, leveling, tickets, anti-raid, invites, birthdays, suggestions, giveaways, reminders, voice tracking & scheduled announcements.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`")


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
