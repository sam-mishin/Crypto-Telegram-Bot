import psycopg
import re
import requests

def connect_db():
    conn = psycopg.connect(
        host="10.0.0.173",
        dbname="crypto_coin_db",  # Replace with your server's IP if remote
        user="postgres",   # Replace with your PostgreSQL username
        password="s.mishin", 
        port=5432  # Replace with your PostgreSQL password
    )
    print('Connected to database...')
    return conn

async def async_connect_db():
    aconn = await psycopg.AsyncConnection.connect(
    host="10.0.0.173",
    dbname="crypto_coin_db",  # Replace with your server's IP if remote
    user="postgres",   # Replace with your PostgreSQL username
    password="s.mishin", 
    port=5432  # Replace with your PostgreSQL password
    )
    print('Connected to database...')
    return aconn

async def getCA(message):  
    if message:
        dexLinkPattern = r"https://dexscreener\.com/[^\s]+"
        urls = re.findall(dexLinkPattern, message)

        foundCA = None
        
        if urls:  # Handles a dexscreener link
            for url in urls:
                CA = url.split('/')[-1]
                network = url.split('/')[-2]
                foundCA = CA
            fromLink = True
            return foundCA, network, fromLink

        else:  # Handles if just the CA is in message
            fromLink = False
            network = 'solana'

            message = message.replace('\n', ' ')  # Remove newline characters
            words = message.split(' ')

            for word in words:
                CA_correct = False
                copyableText = re.findall(r"`([^`]+)`", word)  # Apply regex to each word
                if len(copyableText) == 1:
                    word = copyableText[0]

                if len(word) in [43, 44]:
                    print('CA better not be none')
                    CA_correct = all(char not in 'O0lI' for char in word)
                if CA_correct:
                    foundCA = word
                    break
                if not CA_correct:
                    url = f'https://api.dexscreener.com/tokens/v1/{network}/{word}'
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if len(data) == 0:
                            url = f'https://api.dexscreener.com/latest/dex/pairs/{network}/{word}'
                            response = requests.get(url)

                            if response.status_code == 200:
                                CA_correct = True
                if CA_correct:
                    foundCA = word
                    break

            return foundCA, network, fromLink

        