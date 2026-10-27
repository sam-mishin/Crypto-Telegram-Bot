from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from helperFunc import connect_db
import psycopg
import time
import subprocess
import psutil
import os
import signal

# Telegram API credentials are loaded from .env (see config.py)
from config import API_ID as api_id, API_HASH as api_hash, BOT_TOKEN as bot_token

while True:
    try:
        bot = TelegramClient('welcome_bot_session', api_id, api_hash).start(bot_token=bot_token)
        break
    except FloodWaitError as e:
        print(f"FloodWaitError: Waiting for {e.seconds} seconds before retrying...")
        time.sleep(e.seconds)

conn = connect_db()
cur = conn.cursor()


# Function to start chat scraper with gc_name
def start_chat_scraper():
    # Terminate any existing chatScraper.py process
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmdline = proc.info['cmdline']
        if cmdline and 'chat_scraper.py' in cmdline:
            return  # chatScraper.py is already running

    # Start a new chatScraper.py process with gc_name
    try:
        subprocess.Popen(['python', 'chat_scraper.py'])
        print(f"Started chat_scraper.py process...")
    except Exception as e:
        print(f"Error starting chat_scraper.py process: {e}")

# Global variables to store user-specific API key and hash
user_api_keys = {}

# Handler for the /start command
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond(f'Hello! I am a telegram bot that monitors crypto channels for meme coin calls. Once a coin is called in one of the monitored chats, it sends a message to a groupchat you add it in with information about the coin.\n\n'
                        f'To add chats to monitor, type "/add chat-name" and replace chat-name with chat name as found in the chat invite link. \n\n'
                        f'To see a list of all commands type "/help".\n\n'
                        f'NOTE: You will need to add the bot to a group chat and tell the bot which groupchat to send messages to using "/gc _gc_name_", otherwise the bot will not work properly. Addtionally, you will need to' 
                        f'get an API key and an API hash from telegram. Here is a link to the telegram page where you can get your key and hash: https://core.telegram.org/api')
    
    current_user_id = event.sender_id

    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()

    # if the user is not in the database, add them
    if len(user_array) == 0:
        print("add user to database")
        cur.execute("INSERT INTO user_chats (user_id, chat_ids) VALUES (%s, ARRAY[]::text[]) ON CONFLICT (user_id) DO NOTHING;", (current_user_id,))
        conn.commit()

    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()

    print(len(user_array))
    print(len(user_array[0][2]))

    start_chat_scraper()

    #if len(user_array) > 0 and len(user_array[0][2]) != 0:
        #ensure_message_forwarder_running()

# Handler for the /help command
@bot.on(events.NewMessage(pattern='/help'))
async def help(event):
    help_text = (
        "Here are the commands you can use:\n\n"
        "/start - Start the bot\n"
        "/login - Start login process to start monitoring messages. This is essential to run the bot properly.\n"
        "/code - Use this to send the code telegram sends after attempting to log in. You will need to put 'aa' before otherwise telegram will expire the code.\n"
        "/password - If 2 factor authentication is enabled, use this command to enter your password.\n"
        "/gc - Tell the bot which chat to send messages to\n"
        "/chats - Get a list of monitored chats\n"
        "/add '_chat-name_' - Add a chat to be monitored. Replace chat-name with the name of the chat (from an invite link) you wish to add.\n"
        "/remove '_chat-name_' - Stop monitoring a chat.\n"
        "/help - Get a list of all commands information\n"
        "/info - Get information about the bot\n"
        "/how -  Get a deeper explanation about how to use the bot and its capabilities\n"
    )
    await event.respond(help_text)

# Handler for the /add command
@bot.on(events.NewMessage(pattern='/add (.+)'))
async def addChat(event):
    chat_name = event.pattern_match.group(1)
    current_user_id = event.sender_id

    try:
        await bot.get_input_entity(chat_name)  # Check if the chat exists
    except ValueError:
        await event.respond(f'Error: The chat "{chat_name}" does not exist or cannot be accessed.')
        return

    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()

    if not (chat_name in user_array[0][2]):
        await event.respond(f'Added {chat_name}...')
        cur.execute("UPDATE user_chats SET chat_ids = ARRAY(SELECT DISTINCT unnest(chat_ids || %s)) WHERE user_id = %s;", ([chat_name], current_user_id))
        conn.commit()
        
    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()
    print(user_array)

    # Restart the message forwarder
    #ensure_message_forwarder_running()

# Handler for the /remove command
@bot.on(events.NewMessage(pattern='/remove (.+)'))
async def removeChat(event):
    chat_name = event.pattern_match.group(1)
    current_user_id = event.sender_id

    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()
    
    if chat_name in user_array[0][2]:
        await event.respond(f'Removed {chat_name}...')
        cur.execute("UPDATE user_chats SET chat_ids = array_remove(chat_ids, %s) WHERE user_id = %s;", (chat_name, current_user_id))
        conn.commit()
        
        #ensure_message_forwarder_running()

    elif not (chat_name in user_array[0][2]):
        await event.respond(f'{chat_name} is not in the monitored chats...')

# Handler for the /chats command
@bot.on(events.NewMessage(pattern='/chats'))
async def listChats(event):
    current_user_id = event.sender_id

    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()

    chat_array = user_array[0][2]
    
    if len(chat_array) == 0:
        await event.respond(f'There are no chats being monitored...\n\n' 
                            f'Did you enter the chat name correctly? If you need help type "/how".')
    else:
        chats = "\n".join(chat_array)
        await event.respond(f'These are the chats that are being monitored: \n\n{chats}')

# Handler for the /gc command
@bot.on(events.NewMessage(pattern='/gc (.+)'))
async def gc(event):
    gc_name = event.pattern_match.group(1)
    current_user_id = event.sender_id

    try:
        await bot.get_input_entity(gc_name)  # Check if the chat exists
    except ValueError:
        await event.respond(f'Error: The chat "{gc_name}" does not exist or cannot be accessed.')
        return
    
    cur.execute("UPDATE user_chats SET gc_name = (%s) WHERE user_id = %s;", (gc_name, current_user_id))
    conn.commit()

    
    cur.execute("SELECT * FROM user_chats WHERE user_id = %s", (current_user_id,))
    user_array = cur.fetchall()

    print(user_array)

    await event.respond(f'Now sending messages to {gc_name}')

# Handler for the /key command
@bot.on(events.NewMessage(pattern='/key (.+)'))
async def set_api_key(event):
    api_key = event.pattern_match.group(1)
    current_user_id = event.sender_id

    if current_user_id not in user_api_keys:
        user_api_keys[current_user_id] = {}

    user_api_keys[current_user_id]['api_key'] = api_key

    # Save API key to the database
    cur.execute("UPDATE user_chats SET api_key = %s WHERE user_id = %s;", (api_key, current_user_id))
    conn.commit()

    await event.respond(f"API key set successfully for your session.")

# Handler for the /hash command
@bot.on(events.NewMessage(pattern='/hash (.+)'))
async def set_api_hash(event):
    api_hash = event.pattern_match.group(1)
    current_user_id = event.sender_id

    if current_user_id not in user_api_keys:
        user_api_keys[current_user_id] = {}

    user_api_keys[current_user_id]['api_hash'] = api_hash

    # Save API hash to the database
    cur.execute("UPDATE user_chats SET api_hash = %s WHERE user_id = %s;", (api_hash, current_user_id))
    conn.commit()

    await event.respond(f"API hash set successfully for your session.")

print("Welcome Bot is running...")
bot.start()
bot.run_until_disconnected()