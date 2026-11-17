"""Holds a reference to the running discord.py Bot so the dashboard (a
separate FastAPI app running in the same process) can read live guild/
channel/role data without importing bot.py directly (avoids circular imports).
"""

bot_instance = None


def set_bot(bot):
    global bot_instance
    bot_instance = bot


def get_bot():
    return bot_instance
