import os
import secrets
import time
import datetime

import discord
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from dashboard import oauth
from utils import state
from utils.db import get_config, update_config, DB_PATH
import aiosqlite

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", secrets.token_hex(32)))


def _get_bot():
    return state.get_bot()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login")
async def login(request: Request):
    oauth_state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = oauth_state
    return RedirectResponse(oauth.get_authorize_url(oauth_state))


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


@app.get("/callback")
async def callback(request: Request, code: str = None, state: str = None):
    if not code:
        return RedirectResponse("/")

    expected_state = request.session.get("oauth_state")
    if not state or state != expected_state:
        return RedirectResponse("/login")

    token_data = await oauth.exchange_code(code)
    access_token = token_data["access_token"]
    user = await oauth.fetch_user(access_token)
    guilds = await oauth.fetch_user_guilds(access_token)

    request.session["user"] = {"id": user["id"], "username": user.get("username", "user")}
    request.session["manageable_guild_ids"] = [g["id"] for g in guilds if oauth.can_manage(g)]
    return RedirectResponse("/dashboard")


def _require_login(request: Request):
    return request.session.get("user")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = _require_login(request)
    if not user:
        return RedirectResponse("/login")

    bot = _get_bot()
    manageable_ids = set(request.session.get("manageable_guild_ids", []))
    guilds = []
    if bot:
        for g in bot.guilds:
            if str(g.id) in manageable_ids:
                guilds.append({"id": g.id, "name": g.name})

    return templates.TemplateResponse("guilds.html", {"request": request, "user": user, "guilds": guilds})


def _check_guild_access(request: Request, guild_id: int):
    user = _require_login(request)
    if not user:
        return None, None
    manageable_ids = set(request.session.get("manageable_guild_ids", []))
    if str(guild_id) not in manageable_ids:
        return None, None
    bot = _get_bot()
    guild = bot.get_guild(guild_id) if bot else None
    if not guild:
        return None, None
    return user, guild


@app.get("/dashboard/{guild_id}", response_class=HTMLResponse)
async def guild_settings(request: Request, guild_id: int, saved: bool = False):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard")

    cfg = await get_config(guild_id)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM custom_commands WHERE guild_id = ? ORDER BY name", (guild_id,))
        custom_commands = [dict(r) for r in await cur.fetchall()]

        cur = await db.execute("SELECT * FROM scheduled_announcements WHERE guild_id = ?", (guild_id,))
        raw_announcements = [dict(r) for r in await cur.fetchall()]

    announcements = []
    for a in raw_announcements:
        channel = guild.get_channel(a["channel_id"])
        a["channel_name"] = channel.name if channel else str(a["channel_id"])
        announcements.append(a)

    prefix = os.getenv("PREFIX", "!")

    return templates.TemplateResponse("guild_settings.html", {
        "request": request,
        "user": user,
        "guild": guild,
        "cfg": cfg,
        "text_channels": guild.text_channels,
        "categories": guild.categories,
        "roles": [r for r in guild.roles if not r.is_default()],
        "custom_commands": custom_commands,
        "announcements": announcements,
        "prefix": prefix,
        "saved": saved,
    })


@app.post("/dashboard/{guild_id}/config")
async def save_config(request: Request, guild_id: int):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    form = await request.form()

    def to_int_or_none(value):
        return int(value) if value else None

    fields = {
        "welcome_channel_id": to_int_or_none(form.get("welcome_channel_id")),
        "welcome_message": form.get("welcome_message") or None,
        "autorole_id": to_int_or_none(form.get("autorole_id")),
        "leave_channel_id": to_int_or_none(form.get("leave_channel_id")),
        "leave_message": form.get("leave_message") or None,
        "mod_log_channel_id": to_int_or_none(form.get("mod_log_channel_id")),
        "ticket_category_id": to_int_or_none(form.get("ticket_category_id")),
        "ticket_support_role_id": to_int_or_none(form.get("ticket_support_role_id")),
        "ticket_log_channel_id": to_int_or_none(form.get("ticket_log_channel_id")),
        "antiraid_enabled": int(form.get("antiraid_enabled") or 0),
        "antiraid_threshold": int(form.get("antiraid_threshold") or 5),
        "antiraid_window_seconds": int(form.get("antiraid_window_seconds") or 10),
        "birthday_channel_id": to_int_or_none(form.get("birthday_channel_id")),
        "suggestions_channel_id": to_int_or_none(form.get("suggestions_channel_id")),
    }
    await update_config(guild_id, **fields)
    return RedirectResponse(f"/dashboard/{guild_id}?saved=true", status_code=303)


@app.post("/dashboard/{guild_id}/customcommands/add")
async def add_custom_command(request: Request, guild_id: int, name: str = Form(...), response: str = Form(...)):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO custom_commands (guild_id, name, response) VALUES (?, ?, ?)",
            (guild_id, name.lower().strip(), response),
        )
        await db.commit()
    return RedirectResponse(f"/dashboard/{guild_id}", status_code=303)


@app.post("/dashboard/{guild_id}/customcommands/delete")
async def delete_custom_command(request: Request, guild_id: int, name: str = Form(...)):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM custom_commands WHERE guild_id = ? AND name = ?", (guild_id, name))
        await db.commit()
    return RedirectResponse(f"/dashboard/{guild_id}", status_code=303)


@app.post("/dashboard/{guild_id}/announcements/add")
async def add_announcement(request: Request, guild_id: int, channel_id: int = Form(...),
                            message: str = Form(...), interval_minutes: int = Form(...)):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    import time
    next_run = time.time() + interval_minutes * 60
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO scheduled_announcements (guild_id, channel_id, message, interval_minutes, next_run) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, channel_id, message, interval_minutes, next_run),
        )
        await db.commit()
    return RedirectResponse(f"/dashboard/{guild_id}", status_code=303)


@app.post("/dashboard/{guild_id}/announcements/delete")
async def delete_announcement(request: Request, guild_id: int, announcement_id: int = Form(...)):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM scheduled_announcements WHERE id = ? AND guild_id = ?",
            (announcement_id, guild_id),
        )
        await db.commit()
    return RedirectResponse(f"/dashboard/{guild_id}", status_code=303)


# ---------------------------------------------------------------------------
# Members — kick / ban / mute / warn straight from the dashboard
# ---------------------------------------------------------------------------

async def _log_to_modlog(guild: discord.Guild, embed: discord.Embed):
    cfg = await get_config(guild.id)
    channel_id = cfg.get("mod_log_channel_id")
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass


@app.get("/dashboard/{guild_id}/members", response_class=HTMLResponse)
async def members_list(request: Request, guild_id: int, q: str = ""):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard")

    query = q.lower().strip()
    all_members = [m for m in guild.members if not m.bot]
    if query:
        matched = [m for m in all_members if query in m.name.lower() or query in m.display_name.lower()]
    else:
        matched = all_members
    matched = sorted(matched, key=lambda m: m.display_name.lower())[:50]

    return templates.TemplateResponse("members.html", {
        "request": request, "user": user, "guild": guild,
        "members": matched, "query": q, "total": len(all_members),
    })


@app.get("/dashboard/{guild_id}/members/{user_id}", response_class=HTMLResponse)
async def member_detail(request: Request, guild_id: int, user_id: int, done: str = ""):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard")

    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            (guild_id, user_id),
        )
        warnings = [dict(r) for r in await cur.fetchall()]

    return templates.TemplateResponse("member_detail.html", {
        "request": request, "user": user, "guild": guild,
        "member": member, "warnings": warnings, "done": done,
    })


@app.post("/dashboard/{guild_id}/members/{user_id}/warn")
async def member_warn(request: Request, guild_id: int, user_id: int, reason: str = Form("No reason provided")):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)
    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members", status_code=303)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, int(user["id"]), reason),
        )
        await db.commit()

    embed = discord.Embed(title="⚠️ Member Warned (via dashboard)", color=discord.Color.gold(),
                           timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Moderator", value=user["username"], inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    await _log_to_modlog(guild, embed)

    return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=warned", status_code=303)


@app.post("/dashboard/{guild_id}/members/{user_id}/mute")
async def member_mute(request: Request, guild_id: int, user_id: int, minutes: int = Form(...),
                       reason: str = Form("No reason provided")):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)
    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members", status_code=303)

    try:
        await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
    except discord.Forbidden:
        return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=no_permission", status_code=303)

    embed = discord.Embed(title="🔇 Member Muted (via dashboard)", color=discord.Color.dark_orange(),
                           timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Duration", value=f"{minutes} minute(s)", inline=False)
    embed.add_field(name="Moderator", value=user["username"], inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    await _log_to_modlog(guild, embed)

    return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=muted", status_code=303)


@app.post("/dashboard/{guild_id}/members/{user_id}/unmute")
async def member_unmute(request: Request, guild_id: int, user_id: int):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)
    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members", status_code=303)

    try:
        await member.timeout(None)
    except discord.Forbidden:
        return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=no_permission", status_code=303)

    return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=unmuted", status_code=303)


@app.post("/dashboard/{guild_id}/members/{user_id}/kick")
async def member_kick(request: Request, guild_id: int, user_id: int, reason: str = Form("No reason provided")):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)
    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members", status_code=303)

    try:
        await member.kick(reason=reason)
    except discord.Forbidden:
        return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=no_permission", status_code=303)

    embed = discord.Embed(title="👢 Member Kicked (via dashboard)", color=discord.Color.orange(),
                           timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Moderator", value=user["username"], inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    await _log_to_modlog(guild, embed)

    return RedirectResponse(f"/dashboard/{guild_id}/members?done=kicked", status_code=303)


@app.post("/dashboard/{guild_id}/members/{user_id}/ban")
async def member_ban(request: Request, guild_id: int, user_id: int, reason: str = Form("No reason provided")):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)
    member = guild.get_member(user_id)
    if not member:
        return RedirectResponse(f"/dashboard/{guild_id}/members", status_code=303)

    try:
        await member.ban(reason=reason)
    except discord.Forbidden:
        return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=no_permission", status_code=303)

    embed = discord.Embed(title="🔨 Member Banned (via dashboard)", color=discord.Color.red(),
                           timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Moderator", value=user["username"], inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    await _log_to_modlog(guild, embed)

    return RedirectResponse(f"/dashboard/{guild_id}/members?done=banned", status_code=303)


@app.post("/dashboard/{guild_id}/members/{user_id}/clearwarnings")
async def member_clearwarnings(request: Request, guild_id: int, user_id: int):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        await db.commit()

    return RedirectResponse(f"/dashboard/{guild_id}/members/{user_id}?done=warnings_cleared", status_code=303)


# ---------------------------------------------------------------------------
# Send a message / announcement right now from the dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard/{guild_id}/send", response_class=HTMLResponse)
async def send_message_page(request: Request, guild_id: int, sent: bool = False):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard")

    return templates.TemplateResponse("send.html", {
        "request": request, "user": user, "guild": guild,
        "text_channels": guild.text_channels, "sent": sent,
    })


@app.post("/dashboard/{guild_id}/send")
async def send_message_submit(request: Request, guild_id: int, channel_id: int = Form(...),
                               message: str = Form(...)):
    user, guild = _check_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/dashboard", status_code=303)

    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass

    return RedirectResponse(f"/dashboard/{guild_id}/send?sent=true", status_code=303)
