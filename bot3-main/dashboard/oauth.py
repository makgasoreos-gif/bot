import os
import httpx

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DASHBOARD_REDIRECT_URI", "http://localhost:8000/callback")

AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
API_BASE = "https://discord.com/api/v10"

MANAGE_GUILD = 0x20


def get_authorize_url(state: str) -> str:
    params = (
        f"client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds"
        f"&state={state}"
    )
    return f"{AUTHORIZE_URL}?{params}"


async def exchange_code(code: str) -> dict:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_user(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/users/@me", headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_user_guilds(access_token: str) -> list:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/users/@me/guilds", headers=headers)
        resp.raise_for_status()
        return resp.json()


def can_manage(guild_entry: dict) -> bool:
    if guild_entry.get("owner"):
        return True
    perms = int(guild_entry.get("permissions", 0))
    return bool(perms & MANAGE_GUILD)
