from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from DexScreenerAPI import getDexInfo
from helperFunc import getCA
from helperFunc import connect_db
from psycopg import sql
import os
import asyncio
import datetime
import pprint


api_id = ''
api_hash = ""
bot_token = ''

bot = TelegramClient('chat_scraper', api_id, api_hash).start(bot_token=bot_token)

# Updated regex to capture the contract address
coinTracker = {}
network = 'solana'
name = None


user_chat_mapping = {}  # Stores {user_id: {"chats": set(chat_ids), "gc": group_chat}}

def fetch_monitored_chats():
    global user_chat_mapping
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT user_id, chat_ids, gc_name FROM user_chats WHERE gc_name IS NOT NULL")
    user_data = cur.fetchall()

    user_chat_mapping = {
        user_id: {"chats": set(chat_ids), "gc": gc_name}
        for user_id, chat_ids, gc_name in user_data if chat_ids
    }
    pprint.pprint(user_chat_mapping)

    cur.close()
    conn.close()

async def listen_for_changes():
    """Listen for PostgreSQL notifications and update monitored chats in real-time."""
    try:
        with connect_db() as conn:
            conn.autocommit = True
            listen_sql = sql.SQL("LISTEN {};").format(sql.Identifier("chat_update"))
            with conn.cursor() as cur:
                cur.execute(listen_sql)

            print("Listening for notifications...")

            gen = conn.notifies()
            for notification in gen:
                print("🔄 Received notification:", notification)
                fetch_monitored_chats()  # Refresh monitored chats

    except Exception as e:
        print("❌ Error:", e)


@bot.on(events.NewMessage())
async def newMessageHandler(event):
    message = event.message.text
    chat_id = event.message.chat.username
    result = await getCA(message)
    if result is None:
        return

    CA, network, fromLink = result
    currentTime = datetime.datetime.now()
    formattedTime = currentTime.strftime("%I:%M %p")

    if CA:
        # gets chat name 
        try:
            chat = event.message.forward.chat.title
        except:
            chat = 'unknown'
        
        # adds CA to coin tracker dictionary
    # Track the coin in the dictionary
    if CA:
        if CA in coinTracker:
            coinTracker[CA]['count'] += 1
        else:
            coinTracker[CA] = {'count': 1, 'time called': formattedTime}

    # Send message to the correct user's group chat
    for user_id, data in user_chat_mapping.items():
        if chat_id in data["chats"]:
            gc_name = data["gc"]  # Get the user's group chat
            print(f"Sending message to {gc_name} for user {user_id}")

            # Fetch token data
            dex_data = getDexInfo(network, CA, fromLink)
            if len(dex_data) == 4:
                name, vol24, MC, boosts = dex_data
            elif len(dex_data) == 8:
                name, vol24, MC, boosts, CA, url, isPairAddress, pairAddress = dex_data

            message_content = (
                f'💵 <b>{network.upper()}</b> Call 💵\n\n'
                f'Name: <b>${name}</b>\n'
                f'Market Cap: <b>{MC}</b>\n'
                f'24H Volume: <b>{vol24}</b>\n'
                f'Boosts: <b>{boosts}</b>\n\n'
                f'CA: <code>{CA}</code>\n\n'
                f'Called at: <b>{formattedTime}</b>\n'
                f'{url}'
            )

            await bot.send_message(gc_name, message_content, parse_mode="HTML", link_preview=False)

async def main():
    """Start the chat scraper bot."""
    fetch_monitored_chats()  # Load chat list at startup
    asyncio.create_task(listen_for_changes())
    print("Chat Scraper is running...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())  # ✅ Correct way to handle Telethon’s event loop


