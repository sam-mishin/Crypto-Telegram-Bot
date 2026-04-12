import psycopg
import asyncio
from psycopg import sql
from telethon import TelegramClient, events
from helperFunc import connect_db

api_id = 22363106
api_hash = "5df0a9af86db1d36338032632b51c197"

bot_username = 'CryptoCoinFinderBot'

client = TelegramClient('forwarder', api_id, api_hash)

user_chat_mapping = {}

def fetch_monitored_chats():
    global user_chat_mapping
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT user_id, chat_ids FROM user_chats")
    user_data = cur.fetchall()
    user_chat_mapping = {user_id: set(chats) for user_id, chats in user_data if chats}
    print(user_chat_mapping)
    cur.close()
    conn.close()

def listen_notifications():
    """Listen for PostgreSQL notifications and update monitored chats in real-time."""
    try:
        with connect_db() as conn:
            conn.autocommit = True
            listen_sql = sql.SQL("LISTEN {};").format(sql.Identifier("chat_update"))
            conn.execute(listen_sql)

            print("Listening for notifications...")

            gen = conn.notifies()
            for notification in gen:
                print("Received notification:", notification)
                fetch_monitored_chats()  # Refresh monitored chats

    except Exception as e:
        print("Error:", e)
"""
def perform_health_check(conn, listen_sql):
    #Check if the database connection is still alive and restart LISTEN if needed
    try:
        print("Performing health check...")
        conn.execute("SELECT 1")  # Keep connection alive
        conn.execute(listen_sql)  # Restart LISTEN command
    except Exception as e:
        print("Health check failed:", e)
"""

@client.on(events.NewMessage())
async def forward_message(event):
    """Forwards messages to users monitoring the chat."""
    try:
        for user_id, monitored_chats in user_chat_mapping.items():
            if event.message.username in monitored_chats:
                await client.forward_messages(bot_username, event.message.id, event.chat_id)
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Start listening for chat updates and run the bot."""
    fetch_monitored_chats()  # Initial data load
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, listen_notifications)  # Run listener in a separate thread
    print("Message Forwarder is running...")
    await client.start()  # Start Telethon client
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
