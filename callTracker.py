from helperFunc import connect_db, getCA
from telethon import TelegramClient, events

# Telegram API credentials
api_id = ''
api_hash = ""
bot_token = ''

bot = TelegramClient('chat_scraper', api_id, api_hash).start(bot_token=bot_token)

conn = connect_db()
cur = conn.cursor()

@bot.on(events.NewMessage())
async def checkMC(events):
    message = events.message.text
    result = await getCA(message)
    if result is None:
        return

    CA, _, _ = result

    cur.execute('SELECT FROM coin_table WHERE ca = %s', (CA,))
    coin_info = cur.fetchall()

    print(coin_info)



bot.run_until_disconnected()