import requests
import pprint
import time
import requests
import datetime
from telethon import TelegramClient
from DexScreenerAPI import getDexInfo
from helperFunc import connect_db

# Telegram API credentials are loaded from .env (see config.py)
from config import API_ID as api_id, API_HASH as api_hash, BOT_TOKEN as bot_token
bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

arrayOfCA = []
oldVol = 0
newVol = 0
caExists = 0

conn = connect_db()
cur = conn.cursor()

print("this works!")

async def volumeTracker():
    print("Volume Tracker is running...")
    count = 0
    while True:
        volLatestProfiles()
        updateDatabaseVol(count)
        await checkVolume()

        print(count)
        
        count += 1
        if count == 12:
            count = 0
        time.sleep(300)

def volLatestProfiles():
    latestProfilesList = f'https://api.dexscreener.com/token-profiles/latest/v1'
    response = requests.get(latestProfilesList)

    #gets latest token profiles and saves the CAs to an array
    if response.status_code == 200:
        data = response.json()

        for i in range(0, len(data)):
            if data[i]['chainId'] == 'solana':
                CA = data[i]['tokenAddress']
                arrayOfCA.insert(0, CA) 
    else:
        print("couldn't fetch data")

    i = 0
    #get the 24 hour volume of coin
    for item in arrayOfCA[:]:
        CA = item
        url = f'https://api.dexscreener.com/tokens/v1/solana/{CA}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            try:
                if (data[0]['priceChange']['h24'] == -100) or (data[0]['volume']['h24'] < 249000) or (data[0]['volume']['h1'] < 1000) or (data[0]['marketCap'] < 10000):
                    arrayOfCA.remove(item)    
            except:
                arrayOfCA.remove(item)            
        else:
            print("couldn't fetch dex screener data")
        i += 1

    #add CA to database
    for CA in arrayOfCA:
        url = f'https://api.dexscreener.com/tokens/v1/solana/{CA}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            oldVol = data[0]['volume']['h24']
            newVol = oldVol

            try:
                caExists = cur.execute("SELECT EXISTS(SELECT 1 FROM coin_table WHERE CA = (%s))", (CA,))
                caExists = cur.fetchone()[0]
            except: 
                caExists = False

            if not (caExists):
                cur.execute("INSERT INTO coin_table (CA, oldVol, newVol) VALUES (%s, %s, %s)", (CA, oldVol, newVol))
                print(f"added {CA} to database")
                conn.commit()
    

    arrayOfLatestCA = arrayOfCA

    return arrayOfLatestCA

def updateDatabaseVol(count):
    # update volume for all CAs in database
    cur.execute("SELECT * FROM coin_table")
    caData = cur.fetchall()
    
    for i in range(0, len(caData)):
        CA = caData[i][0]
        url = f'https://api.dexscreener.com/tokens/v1/solana/{CA}' 
        response = requests.get(url)
        
        #get new vol
        if response.status_code == 200:
            data = response.json()

            if len(data) == 0:
                try:
                    caUrl = f'https://api.dexscreener.com/latest/dex/pairs/solana/{CA}'
                    response = requests.get(caUrl)

                    if response.status_code == 200:
                        data = response.json()
                        oldVol = data['pair']['volume']['h24']
                        dexNewVol = data['pair']['volume']['h24']
                    else:
                        oldVol = 0
                except TypeError as e:
                    print(f"{e}")

            else:
                oldVol = data[0]['volume']['h24']
                dexNewVol = data[0]['volume']['h24']            
            
            newVol = oldVol

            try:
                priceChange = data[0]['priceChange']['h24']
            except:
                priceChange = -100

            if priceChange > -99:
                marketCap = data[0]['marketCap']
            else:
                marketCap = 0

            if count == 5:
                if dexNewVol > 249000 and priceChange > -80 and marketCap > 100000:
                    print(f"B old volume: {caData[i][1]}")
                    print(f"B new volume: {caData[i][2]}")

                    # get the current old volume and new volume values from the database
                    cur.execute("SELECT oldVol, newVol FROM coin_table WHERE CA = (%s)", (CA,))
                    volumeValues = cur.fetchone()
                    
                    if volumeValues:
                        _, newVol = volumeValues

                        updatedOldVol = newVol
                        updatedNewVol = dexNewVol

                        # update oldVol and newVol in the database
                        cur.execute("UPDATE coin_table SET oldVol = (%s), newVol = (%s) WHERE CA = (%s)", (updatedOldVol, updatedNewVol, CA))
                        conn.commit()

                        cur.execute("SELECT * FROM coin_table WHERE CA = (%s)", (CA,))
                        row = cur.fetchone()
                        print(f"A {row}")

                else: #if CA volume is below 250,000, remove it
                    cur.execute("DELETE FROM coin_table WHERE CA = (%s)", (CA,))
                    print("deleted CA")
                
        else:
            print("couldn't update database volume")

async def checkVolume():
    cur.execute("SELECT * FROM coin_table")
    caData = cur.fetchall()

    print('checked volume')

    for i in range(0, len(caData)):
        oldVol = caData[i][1]
        newVol = caData[i][2]

        print(f"Volume ratio for {caData[i][0]} is {newVol/oldVol}")

        if newVol/oldVol >= 1.5:
            await sendMessage(caData[i][0])

async def sendMessage(CA):
    isRugPull, warningLevel= checkRug(CA)

    if not isRugPull:
        network = 'solana'
        fromLink = False
        lenOfDexInfo = getDexInfo(network, CA, fromLink)

        if len(lenOfDexInfo) == 4:
            name, vol24, MC, _ = getDexInfo(network, CA, fromLink)
        if len(lenOfDexInfo) == 8: 
            name, vol24, MC, _, CA, url, _, _ = getDexInfo(network, CA, fromLink)

        currentTime = datetime.datetime.now()
        formattedTime = currentTime.strftime("%I:%M %p")

        await bot.send_message('sammyscryptocalls', 
                                f'🚨 <b>Volume Surge</b> 🚨\n\n'
                                f'Name: <b>${name}</b>\n'
                                f'Market Cap: <b>{MC}</b>\n'
                                f'24 Hour Volume: <b>{vol24}</b>\n\n'
                                f'RugCheck Warning Level: {warningLevel}\n\n'
                                f'CA: <code>{CA}</code>\n\n'
                                f'Called at: <b>{formattedTime}</b> on <b>{currentTime.month}/{currentTime.day}/{currentTime.year}</b>\n'
                                f'{url}',
                                parse_mode="HTML")
        
def checkRug(CA):
    url = f'https://api.rugcheck.xyz/v1/tokens/{CA}/report/summary'
    response = requests.get(url)
    
    level = 'Unknown'

    if response.status_code == 200:
        data = response.json()

        if len(data['risks']) != 0:
            level = data['risks'][0]['level']
        else:
            level = 'Unknown'

        if level == 'danger':
            cur.execute("DELETE FROM coin_table WHERE CA = (%s)", (CA,))
            return True, level
        else:
            return False, level 
    else:
        print("couldn't access rug check")
        return False, level


bot.loop.run_until_complete(volumeTracker())

