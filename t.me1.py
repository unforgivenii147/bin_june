#!/data/data/com.termux/files/usr/bin/env python
import re
from telethon import TelegramClient

# Replace these with your own credentials
API_ID = "your_api_id"
API_HASH = "your_api_hash"
CHANNEL_USERNAME = "username_of_the_channel"  # e.g., 'coc_bases_channel'

# Regex pattern to match Clash of Clans base links
COC_LINK_PATTERN = r"https://link\.clashofclans\.com/[a-zA-Z0-9\?\=\&_]+"


async def main():
    # Create the client and connect
    async with TelegramClient("session_name", API_ID, API_HASH) as client:
        # Get the entity of the channel
        channel = await client.get_entity(CHANNEL_USERNAME)

        print(f"Searching for links in {channel.title}...")

        # Iterate through messages
        async for message in client.iter_messages(channel, limit=100):
            if message.text:
                # Find all matches in the message text
                links = re.findall(COC_LINK_PATTERN, message.text)

                if links:
                    for link in links:
                        print(f"Found link: {link}")


# Run the client
if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
