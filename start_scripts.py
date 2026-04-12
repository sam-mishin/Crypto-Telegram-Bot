import subprocess
import time

def start_process(script_name):
    process = subprocess.Popen(['python', script_name])
    return process

def wait_for_process(process, script_name):
    while True:
        if process.poll() is None:
            break
        else:
            print(f"Waiting for {script_name} to start...")
            time.sleep(1)

# Start messageForwarder.py
message_forwarder_process = start_process('messageForwarder.py')
wait_for_process(message_forwarder_process, 'messageForwarder.py')

# Start chatScraper.py
chat_scraper_process = start_process('chatScraper.py')
wait_for_process(chat_scraper_process, 'chatScraper.py')


# Wait for all processes to complete
def startScripts():
    message_forwarder_process.wait()
    chat_scraper_process.wait()