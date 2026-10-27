from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import PeerChannel
from helperFunc import getCA

# Telegram API credentials are loaded from .env (see config.py)
from config import API_ID as api_id, API_HASH as api_hash, BOT_TOKEN as bot_token

bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
# monitor messages and save CA

@bot.on(events.NewMessage(from_users='mvpscorp'))
async def newMessageHandler(event):
    message = event.message.text
    getCA(event)

    if message:
        chat = 'unknown'
        
        if event.message.fwd_from and isinstance(event.message.fwd_from.from_id, PeerChannel):
            channel_id = event.message.fwd_from.from_id.channel_id

            if channel_id:
                channel_name = await bot(GetFullChannelRequest(channel_id))
                chat = channel_name.chats[0].title
        