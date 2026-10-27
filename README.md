# Crypto Call Tracker: Telegram Bot

A Telegram bot that watches crypto chats you follow for new coin "calls." When a token contract address or DexScreener link shows up, it pulls live market data from the DexScreener API and posts a summary to your own group chat.

Written in Python with Telethon, PostgreSQL and the DexScreener API.

## What it does

- **Watches chats you pick.** Users add the Telegram channels they want monitored with `/add`, and the bot listens for new messages in them.
- **Spots coin calls.** It finds DexScreener links or raw Solana contract addresses in a message, including addresses inside code blocks, and checks them against DexScreener to filter out false matches.
- **Posts the coin's stats.** For each call it sends the token name, market cap, 24h volume, active boosts and contract address to the user's chosen group chat.
- **Counts repeat calls.** It tracks how many times each coin is called and when it was first seen.
- **Tracks volume.** A separate job (`volumeTracker.py`) checks DexScreener's newest Solana token profiles every 5 minutes, keeps tokens above set volume and market cap limits, and records changes in volume over time.
- **Updates live.** Monitored-chat lists are kept in PostgreSQL, and the scraper uses `LISTEN/NOTIFY` to pick up changes without restarting.

## Bot commands

| Command | Description |
| --- | --- |
| `/start` | Register and see setup instructions |
| `/help` | List all commands |
| `/add <chat>` | Monitor a chat (name from its invite link) |
| `/remove <chat>` | Stop monitoring a chat |
| `/chats` | Show the chats you're monitoring |
| `/gc <group>` | Set the group chat that receives alerts |
| `/key <api_id>` and `/hash <api_hash>` | Save your Telegram API credentials |
| `/login`, `/phone`, `/code`, `/password` | Sign in to your Telegram account so the bot can read your chats |

## How it's built

```
Telegram chats ──▶ chat_scraper.py ──▶ helperFunc.getCA() ──▶ DexScreenerAPI.py
                         │                                         │
                         ▼                                         ▼
                   PostgreSQL  ◀──── welcomeBot.py         alert to your group chat
               (users, chats, coins)   (commands)
```

| File | Role |
| --- | --- |
| `welcomeBot.py` | Command handling and user setup |
| `chat_scraper.py` | Per-user Telegram sessions, login flow, call detection and alerts |
| `helperFunc.py` | Database connections and contract-address detection |
| `DexScreenerAPI.py` | Fetches token and pair data from DexScreener |
| `volumeTracker.py` | Watches volume on newly listed Solana tokens |
| `messageForwarder.py` | Forwards messages from monitored chats to the bot |
| `config.py` | Loads credentials and database settings from `.env` |
| `start_scripts.py` | Starts the forwarder and scraper together |

## Setup

1. Install Python 3.10+ and PostgreSQL.
2. Install dependencies:
   ```bash
   pip install telethon "psycopg[binary]" requests psutil python-dotenv
   ```
3. Create a bot with [@BotFather](https://t.me/BotFather), and get an API ID and hash at [my.telegram.org](https://my.telegram.org).
4. Copy `.env.example` to `.env` and fill in your bot token, API ID/hash and database settings. `config.py` loads them, and `.env` is git-ignored.
5. Create the `user_chats` and `coin_table` tables in PostgreSQL.
6. Run the bot:
   ```bash
   python welcomeBot.py
   ```

## Tech

Python · Telethon · PostgreSQL (psycopg 3, LISTEN/NOTIFY) · DexScreener REST API · asyncio
