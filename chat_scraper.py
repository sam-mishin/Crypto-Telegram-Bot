import asyncio
import os
import sys
import datetime
import pprint
from asyncio import WindowsSelectorEventLoopPolicy  # Import the policy for Windows

# Set the event loop policy for Windows compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from psycopg import sql
from helperFunc import getCA, async_connect_db
from DexScreenerAPI import getDexInfo

# Access the API credentials
api_id = ''
api_hash = ""
bot_token = ''

bot = TelegramClient('chat_scraper', api_id, api_hash).start(bot_token=bot_token)

# Folder to store session files
SESSION_FOLDER = "sessions"
os.makedirs(SESSION_FOLDER, exist_ok=True)

# Store active user sessions {user_id: TelegramClient}
user_sessions = {}
timeout_tasks = {}

async def fetch_user_chat_gc():
    conn = await async_connect_db()
    cur = conn.cursor()

    await cur.execute("SELECT user_id, chat_ids, gc_name FROM user_chats WHERE gc_name IS NOT NULL")
    user_data = await cur.fetchall()

    monitored_users = {
        user_id: {"chats": set(chat_ids), "gc": gc_name}
        for user_id, chat_ids, gc_name in user_data if chat_ids
    } if user_data else {}

    await cur.close()
    await conn.close()

    return monitored_users

async def abort_session(client, user_id):
    print(f"Starting abort_session for user {user_id}")

    try:
        await asyncio.sleep(110)  # Wait for 110 seconds
        print(f"Timeout reached for user {user_id}. Aborting login process.")
        await bot.send_message(user_id, "Session timed out. Aborting login process. Please try again.")
        
        # Log out and delete session
        await client.log_out()
        await client.disconnect()
        
        session_path = os.path.join(SESSION_FOLDER, f"user_{user_id}.session")
        if os.path.exists(session_path):
            os.remove(session_path)
            print("Session file deleted.")
    except asyncio.CancelledError:
        print(f"abort_session canceled for user {user_id}")
    except Exception as e:
        print(f"Error in abort_session for user {user_id}: {e}")

async def fetch_user_api_credentials(user_id):
    """Fetch the API key and hash for a user from the database."""
    conn = await async_connect_db()
    cur = conn.cursor()
    await cur.execute("SELECT api_key, api_hash FROM user_chats WHERE user_id = %s", (user_id,))
    result = await cur.fetchone()
    await cur.close()
    await conn.close()
    return result if result else (None, None)

async def get_user_session(user_id):
    """Get or create a TelegramClient session for the user."""
    if user_id in user_sessions:
        return user_sessions[user_id]  # Return existing session

    # Fetch API credentials from the database
    api_key, api_hash = await fetch_user_api_credentials(user_id)
    if not api_key or not api_hash:
        print(f"API credentials not found for user {user_id}.")
        await bot.send_message(user_id, "API credentials not found. Please set them using the bot commands.")
        return None

    session_path = os.path.join(SESSION_FOLDER, f"user_{user_id}.session")
    client = TelegramClient(session_path, api_key, api_hash)

    # Check if the session file exists and try to connect
    if os.path.exists(session_path):
        try:
            await client.connect()
            if await client.is_user_authorized():
                user_sessions[user_id] = client
                return client  # Return the authorized client
        except Exception as e:
            print(f"Error connecting to session for user {user_id}: {e}")
    else:
        print(f"No session found for user {user_id}. Proceeding with login.")

    # If no valid session, prompt the uer to log in
    await bot.send_message(user_id, "No valid session found. Please log in using the /login command.")
    return None

async def get_user_session(user_id):
    if user_id in user_sessions:
        return user_sessions[user_id]  # Return existing session

    session_path = os.path.join(SESSION_FOLDER, f"user_{user_id}.session")
    client = TelegramClient(session_path, api_id, api_hash)

    # Check if the session file exists and try to connect
    if os.path.exists(session_path):
        try:
            await client.connect()

            if await client.is_user_authorized():
                user_sessions[user_id] = client
                return client  # Return the authorized client
        except Exception as e:
            print(f"Error connecting to session: {e}")
    else:
        print(f"No session found for user {user_id}. Proceeding with login.")

    try:
        @bot.on(events.NewMessage(pattern='/login'))
        async def login(event):
            await bot.send_message(user_id, f"🔑 You need to log in to telegram use this bot. We do not save any phone numbers or passwords. The purpose of the log in to provide a 'handshake' (i.e. a session) between the user and telegram so that the bot can monitor the chats your want monitored. \n\n"
                                            f"Once you log in once, you shouldn't need to login again. If the bot is not working properly, try logging in again. Once the login process is done, all messages related to the login are deleted to protect your information. \n\n"
                                            f"The commands you will need will be: \n\n"
                                            f"/phone (your phone number in the same format as you would log in to telegram) - just your phone number like this +1234567890\n"
                                            f"/code aa(code you recieve from telegram) - be sure to add 'aa' before otherwise Telegram will immediately expire it\n"
                                            f"/password - if you have 2 factor authentication enabled, use this to enter your password when prompted.")
            await bot.send_message(user_id, "📞 Please enter your phone number (e.g., +1234567890) like this '/phone +1234567890':")

            @bot.on(events.NewMessage(from_users=user_id, pattern=r'/phone \+(\d{10,15})'))
            async def handle_phone_number(event):
                global timeout_tasks

                if user_id in timeout_tasks:
                    timeout_tasks[user_id].cancel()
                    print(f"Previous timeout task for user {user_id} canceled.")
                timeout_task = asyncio.create_task(abort_session(client, user_id))
                timeout_tasks[user_id] = timeout_task  # Store the new task

                phone_strip = event.message.text.lstrip('/phone')
                phone = phone_strip.strip()

                print(phone)

                await event.respond("Sending login request... Please wait.")

                try:
                    result = await client.send_code_request(phone=phone)  # Telegram sends the code
                    phone_code_hash = result.phone_code_hash
                except:
                    await event.respond("The phone number entered is incorrect. Please try again.")

                await event.respond("A verification code has been sent.\n\nPlease enter it like this: '/code aa12345'.\n\nThe 'aa' is important otherwise telegram will expire the code.")

                @bot.on(events.NewMessage(from_users=user_id, pattern='/code aa(.+)'))
                async def handle_code(event):
                    code_strip = event.message.text.lstrip('/code aa')
                    code = code_strip.strip()
                    chat_id = event.chat_id
                    print(chat_id)

                    print(phone)
                    print(code)
                    print(phone_code_hash)

                    try:
                        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                        if await client.is_user_authorized():
                            if user_id in timeout_tasks:
                                timeout_tasks[user_id].cancel()
                                del timeout_tasks[user_id]  # Remove the task from the dictionary
                                print(f"Timeout task for user {user_id} canceled after successful login.")
                            await bot.send_message(user_id, "Login successful!")

                            await register_event_listener(client, user_id, await fetch_user_chat_gc())

                            user_sessions[user_id] = client  # Store session
                            return client
                    
                    except SessionPasswordNeededError:
                        await event.respond("2FA is enabled. Please enter your password.")

                        @bot.on(events.NewMessage(from_users=user_id, pattern='/password (.*)'))
                        async def handle_password(event):
                            password_strip = event.message.text.lstrip('/password')
                            password = password_strip.strip()

                            print(password)

                            await client.sign_in(phone=phone, password=password, phone_code_hash=phone_code_hash)

                            if await client.is_user_authorized():
                                if user_id in timeout_tasks:
                                    timeout_tasks[user_id].cancel()
                                    del timeout_tasks[user_id]  # Remove the task from the dictionary
                                    print(f"Timeout task for user {user_id} canceled after successful login.")
                                await event.respond("Login successful!")

                                await register_event_listener(client, user_id, await fetch_user_chat_gc())

                                user_sessions[user_id] = client  # Store session
                            return client
                    except:
                        await event.respond("The code is incorrect. Please reenter the code. Make sure the you add 'aa' before the code like this: '/code aa12345'.")
                
                return client
            
            return client

    except Exception as e:
        await bot.send_message(user_id, f"Login failed: {str(e)}")
        return None

async def listen_for_changes():
    """Listen for PostgreSQL notifications and update monitored chats dynamically."""
    try:
        aconn = await async_connect_db()  # ✅ Now using AsyncConnection
        aconn.set_autocommit == True
        listen_sql = sql.SQL("LISTEN {};").format(sql.Identifier("chat_update"))
        async with aconn.cursor() as acur:
            await acur.execute(listen_sql)

        print("Listening for chat updates...")

        gen = aconn.notifies()
        async for notification in gen:
            print("🔄 Received notification:", notification)

            monitored_users = fetch_user_chat_gc()

            for user_id in monitored_users.keys():
                if user_id not in user_sessions:  # New user detected
                    print(f"🆕 New user detected: {user_id}, initializing session...")
                    client = await get_user_session(user_id)  # Start session & register event handler
                    if client:
                        if not await client.is_user_authorized():
                            print(f"Client for user {user_id} is not authorized, prompting for login...")
                            await bot.send_message(
                                user_id,
                                "Your session is not authorized. Please log in again using the /login command."
                            )
                            continue
                        await register_event_listener(client, user_id, await fetch_user_chat_gc())

    except Exception as e:
        print("❌ Error in listen_for_changes:", e)

async def new_message_handler(event, user_id, monitored_users):
    message = event.message.text

    if event.message.from_id != None:
        if event.message.from_id.user_id == 8148880043:
            print("message from bot...canceling function")
            return

    try:
        chat_id = event.message.chat.username
    except:
        chat_id = 'unknown'

    result = await getCA(message)
    if result is None:
        return

    CA, network, fromLink = result
    currentTime = datetime.datetime.now()
    formattedTime = currentTime.strftime("%I:%M %p on %B %d, %Y")

    if CA != None:
        if chat_id in monitored_users[user_id]["chats"]:
            gc_name = monitored_users[user_id]["gc"]  # Get the user's group chat

            dex_data = getDexInfo(network, CA, fromLink)
            if len(dex_data) == 4:
                name, vol24, MC, boosts = dex_data
            elif len(dex_data) == 8:
                name, vol24, MC, boosts, CA, url, _, _ = dex_data

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
            print(f'sending to {gc_name}')
            await bot.send_message(gc_name, message_content, parse_mode="HTML", link_preview=False)

async def register_event_listener(client, user_id, monitored_users):
    """Register the NewMessage event listener for a specific user."""
    @client.on(events.NewMessage())
    async def handler(event, user_id=user_id):
        try:
            if event.message.from_id != None:
                if event.message.from_id.user_id == 8148880043:
                    print("Message from bot... canceling function")
                    return
            if event.message.text.startswith('💵') or event.message.text.startswith('🚨'):
                return
        except Exception as e:
            print(f"Error in handler for user {user_id}: {e}")

            # Handle session termination
            if "SessionRevokedError" in str(e) or "ConnectionError" in str(e):
                print(f"Session for user {user_id} has been terminated. Attempting to restart session...")
                try:
                    # Attempt to restart the session
                    client = await get_user_session(user_id)
                    if client:
                        print(f"Session for user {user_id} restarted successfully.")
                        await register_event_listener(client, user_id, monitored_users)  # Re-register the listener
                    else:
                        print(f"❌ Failed to restart session for user {user_id}.")
                except Exception as restart_error:
                    print(f"❌ Error while restarting session for user {user_id}: {restart_error}")
                return

        chat_username = event.message.chat.username
        print(f"New message received for user {user_id} from {chat_username}")
        await new_message_handler(event, user_id, await fetch_user_chat_gc())

async def start_user_sessions():
    """Start sessions for all monitored users."""
    monitored_users = await fetch_user_chat_gc()

    for user_id, data in monitored_users.items():
        try:
            client = await get_user_session(user_id)  # Start session if not already running

            if client is None:
                print(f"Login failed for user {user_id}, skipping...")
                continue

            # Ensure the client is connected
            if not client.is_connected():
                print(f"Client for user {user_id} was not connected, connecting now...")
                await client.connect()
            else:
                print(f"Client for user {user_id} is already connected.")

            # Ensure the user is authorized
            if not await client.is_user_authorized():
                print(f"Client for user {user_id} is not authorized, skipping...")
                continue  # Skip unauthorized users
            else:
                print(f"Client for user {user_id} is authorized.")

            await register_event_listener(client, user_id, monitored_users)

        except Exception as e:
            print(f"Error processing user {user_id}: {e}")
            continue  # Skip this user and move to the next one

async def main():
    try:
        await start_user_sessions()
        asyncio.create_task(listen_for_changes())
        await asyncio.gather(*[client.run_until_disconnected() for client in user_sessions.values()])
        
        print("Chat Scraper is running...")
        await bot.run_until_disconnected()
    except Exception as e:
        print(f"❌ Critical error in main: {e}")
        
if __name__ == "__main__":
    # Set the event loop policy for Windows compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())