import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv
import uvicorn

from utils.db import init_db
from utils import state

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!")
PORT = int(os.getenv("PORT", 8000))
ENABLE_DASHBOARD = os.getenv("ENABLE_DASHBOARD", "true").lower() != "false"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.invites = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
state.set_bot(bot)

INITIAL_COGS = [
    "cogs.moderation",
    "cogs.welcome",
    "cogs.leveling",
    "cogs.tickets",
    "cogs.customcommands",
    "cogs.antiraid",
    "cogs.invites",
    "cogs.birthdays",
    "cogs.suggestions",
    "cogs.giveaways",
    "cogs.reminders",
    "cogs.voice_activity",
    "cogs.announcements",
    "cogs.general",
]


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        log.error(f"Slash sync failed: {e}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | slash commands"))


async def run_dashboard():
    from dashboard.app import app as dashboard_app
    config = uvicorn.Config(dashboard_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await init_db()
    async with bot:
        for cog in INITIAL_COGS:
            try:
                await bot.load_extension(cog)
                log.info(f"Loaded {cog}")
            except Exception as e:
                log.error(f"Failed to load {cog}: {e}")

        tasks = [bot.start(TOKEN)]
        if ENABLE_DASHBOARD:
            tasks.append(run_dashboard())
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is missing. Set it in your .env or Railway variables.")
    asyncio.run(main())
