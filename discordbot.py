import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime, timezone
import psycopg2

TOKEN = os.getenv("DISCORD_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
if not TOKEN or not DB_URL:
    raise RuntimeError("DISCORD_TOKENとDATABASE_URL要る")

GUILD_ID = 1001
PROFILE_WATCH_CHANNEL_ID = 1002
PROFILE_FORWARD_CHANNEL_ID = 1003
PROFILE_MENTION_ROLE_ID = 1004
ALLOWED_USER_IDS = {2001, 2002}

def db():
    import urllib.parse
    u = urllib.parse.urlparse(DB_URL)
    return psycopg2.connect(
        dbname=u.path[1:], user=u.username, password=u.password, host=u.hostname, port=u.port, sslmode="require"
    )

def save_first_post(user_id, dt):
    conn = db()
    with conn.cursor() as c:
        c.execute('INSERT INTO first_post_log (user_id, timestamp) VALUES (%s, %s) ON CONFLICT DO NOTHING', (user_id, dt))
    conn.commit(); conn.close()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

class JudgeBtns(View):
    def __init__(self): super().__init__(timeout=None); self.add_item(FwdBtn()); self.add_item(KickBtn())
class FwdBtn(Button):
    def __init__(self): super().__init__(label="転送", style=discord.ButtonStyle.success)
    async def callback(self, i):
        if i.user.id not in ALLOWED_USER_IDS: await i.response.send_message("管理者だけ", ephemeral=True); return
        rid = i.message.reference.message_id if i.message.reference else None
        if not rid: await i.response.send_message("参照なし", ephemeral=True); return
        wch = i.guild.get_channel(PROFILE_WATCH_CHANNEL_ID)
        fch = i.guild.get_channel(PROFILE_FORWARD_CHANNEL_ID)
        src = await wch.fetch_message(rid)
        e = discord.Embed(description=src.content)
        await fch.send(content=f"<@&{PROFILE_MENTION_ROLE_ID}>", embed=e)
        await i.response.send_message("転送", ephemeral=True)
        try: await i.message.edit(view=None)
        except: pass
class KickBtn(Button):
    def __init__(self): super().__init__(label="キック", style=discord.ButtonStyle.danger)
    async def callback(self, i):
        if i.user.id not in ALLOWED_USER_IDS: await i.response.send_message("管理者だけ", ephemeral=True); return
        rid = i.message.reference.message_id if i.message.reference else None
        if not rid: await i.response.send_message("参照なし", ephemeral=True); return
        wch = i.guild.get_channel(PROFILE_WATCH_CHANNEL_ID)
        src = await wch.fetch_message(rid)
        mem = i.guild.get_member(src.author.id)
        if mem and not mem.bot:
            try: await mem.kick(reason="管理"); await i.response.send_message("キック", ephemeral=True)
            except: await i.response.send_message("失敗", ephemeral=True)
        else: await i.response.send_message("いない", ephemeral=True)
        try: await i.message.edit(view=None)
        except: pass

@bot.event
async def on_ready():
    print("Bot on")
    try:
        conn = db()
        with conn.cursor() as c:
            c.execute('CREATE TABLE IF NOT EXISTS first_post_log (user_id BIGINT PRIMARY KEY, timestamp TIMESTAMP);')
        conn.commit(); conn.close()
    except: pass
    bot.add_view(JudgeBtns())

@bot.event
async def on_message(m):
    if m.author.bot: return
    if m.channel.id == PROFILE_WATCH_CHANNEL_ID:
        save_first_post(m.author.id, m.created_at)
        await m.channel.send("▼管理", view=JudgeBtns(), reference=m)
    await bot.process_commands(m)

if __name__ == "__main__":
    bot.run(TOKEN)
