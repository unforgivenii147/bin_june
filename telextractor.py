#!/data/data/com.termux/files/usr/bin/python
import re
from telethon import TelegramClient
from dotenv import load_dotenv
from pathlib import Path
import sys
import os


env_path=Path.home() / ".env"
load_dotenv(env_path)

api_id = os.environ.get("API_ID")

api_hash = os.environ.get("API_HASH")

phone_number = '+989051708322'


channel_handle = 'https://t.me/pycode_hubb'
search_query = 'pdf'


async def main():
    client = TelegramClient('session_name', api_id, api_hash)
    await client.start(phone=phone_number)

    # Get the entity of the channel
    entity = await client.get_entity(channel_handle)

    # Regex to find URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    print(f"Searching for '{search_query}' in {channel_handle}...")

    # Iterate over messages in the channel
    async for message in client.iter_messages(entity, search=search_query):
        if message.text:
            urls = re.findall(url_pattern, message.text)
            if urls:
                print(f"Found link in message ID {message.id}: {urls}")
                # You could save these to a file here
                with open("links.txt", "a") as f:
                    for url in urls:
                        f.write(url + "\n")

    await client.disconnect()

import asyncio
if __name__ == '__main__':
    asyncio.run(main())
