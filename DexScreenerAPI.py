import requests
import pprint

def getDexInfo(network, CA, fromLink):
    if fromLink:
        url = f'https://api.dexscreener.com/tokens/v1/{network}/{CA}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()

            if len(data) == 0:
                url = f'https://api.dexscreener.com/latest/dex/pairs/{network}/{CA}'
                response = requests.get(url)

                if response.status_code == 200:
                    data = response.json()
                    name = data['pair']['baseToken']['symbol']
                    vol24 = data['pair']['volume']['h24']
                    MC = data['pair']['marketCap']
                    CA = data['pair']['baseToken']['address']

                    pairAddress = data['pair']['pairAddress']

                    vol24 = "{:,}".format(vol24)
                    MC = "{:,}".format(MC)

                    #handles possibility of no boosts being active
                    for pair in data['pairs']:
                        if 'boosts' in pair:
                            boosts = data['pair']['boosts']['active']
                            boosts = "{:,}".format(boosts)
                        else:
                            boosts = 'No Boosts'
                    
                    url = f'https://dexscreener.com/{network}/{CA}'

                    if CA == pairAddress:
                        isPairAddress = True
                    else:
                        isPairAddress = False

                    return name, vol24, MC, boosts, CA, url, isPairAddress, pairAddress

            if len(data) >= 1:

                name = data[0]['baseToken']['symbol']
                vol24 = data[0]['volume']['h24']
                MC = data[0]['marketCap']

                vol24 = "{:,}".format(vol24)
                MC = "{:,}".format(MC)

                #handles possibility of no boosts being active
                if data[0]['boosts']:
                    boosts = data[0]['boosts']['active']
                    boosts = "{:,}".format(boosts)
                else:
                    boosts = 'No Boosts'

                return name, vol24, MC, boosts      
    else:
        url = f'https://api.dexscreener.com/tokens/v1/{network}/{CA}'

        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            lenData = len(data)

            #handles getting CA instead of a pair address
            if lenData == 0:
                url = f'https://api.dexscreener.com/latest/dex/pairs/{network}/{CA}'
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()  
                    
                    name = data['pair']['baseToken']['symbol']
                    vol24 = data['pair']['volume']['h24']
                    MC = data['pair']['marketCap']
                    pairAddress = data['pair']['pairAddress']

                    vol24 = "{:,}".format(vol24)
                    MC = "{:,}".format(MC)

                    #handles possibility of no boosts being active
                    for pair in data['pairs']:
                        if 'boosts' in pair:
                            boosts = data['pair']['boosts']['active']
                            boosts = "{:,}".format(boosts)
                        else:
                            boosts = 'No Boosts'
                    
                    url = f'https://dexscreener.com/{network}/{CA}'


                    if CA == pairAddress:
                        isPairAddress = True
                        CA = data['pair']['baseToken']['address']
                    else:
                        isPairAddress = False

                    return name, vol24, MC, boosts, CA, url, isPairAddress, pairAddress

            #handles a pair address instead of a CA
            if len(data) >= 1:
                name = data[0]['baseToken']['symbol']
                vol24 = data[0]['volume']['h24']
                MC = data[0]['marketCap']

                url = data[0]['url']
                pairAddress = data[0]['pairAddress']

                vol24 = "{:,}".format(vol24)
                MC = "{:,}".format(MC)

                #handles possibility of no boosts being active
                for pair in data[0]:
                    if 'boosts' in pair:
                        boosts = data[0]['boosts']['active']
                        boosts = "{:,}".format(boosts)
                    else:
                        boosts = 'No Boosts'

                if CA == pairAddress:
                    isPairAddress = True
                    CA = data[0]['baseToken']['address']
                else:
                    isPairAddress = False

                return name, vol24, MC, boosts, CA, url, isPairAddress, pairAddress