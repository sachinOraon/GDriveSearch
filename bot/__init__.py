import logging
import os
import random
import string
import time

import telegram.ext as tg
from dotenv import load_dotenv

from telegraph import Telegraph

botStartTime = time.time()
if os.path.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)

load_dotenv('config.env')

def getConfig(name: str):
    return os.environ[name]

LOGGER = logging.getLogger(__name__)

try:
    if bool(getConfig('_____REMOVE_THIS_LINE_____')):
        logging.error('The README.md file there to be read! Exiting now!')
        exit()
except KeyError:
    pass

BOT_TOKEN = None
AUTHORIZED_CHATS = set()
if os.path.exists('authorized_chats.txt'):
    with open('authorized_chats.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            AUTHORIZED_CHATS.add(int(line.split()[0]))

# Generate Telegraph Token
try:
    sname = ''.join(random.SystemRandom().choices(string.ascii_letters, k=8))
    LOGGER.info("Generating TELEGRAPH_TOKEN using '" + sname + "' name")
    telegraph = Telegraph()
    telegraph.create_account(short_name=sname)
    telegraph_token = telegraph.get_access_token()
    telegra_ph = Telegraph(access_token=telegraph_token)
except Exception as err:
    LOGGER.error("Unable to generate token ", err)
    exit(1)

try:
    BOT_TOKEN = getConfig('BOT_TOKEN')
    OWNER_ID = int(getConfig('OWNER_ID'))
except KeyError as e:
    LOGGER.error("One or more env variables missing! Exiting now")
    exit(1)

DRIVE_NAME = []
DRIVE_ID = []
INDEX_URL = []

if os.path.exists('drive_folder'):
    with open('drive_folder', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().split()
            DRIVE_NAME.append(temp[0].replace("_", " "))
            DRIVE_ID.append(temp[1])
            try:
                INDEX_URL.append(temp[2])
            except IndexError as e:
                INDEX_URL.append(None)

if DRIVE_ID :
    pass
else :
    LOGGER.error("The README.md file there to be read! Exiting now!")
    exit(1)


updater = tg.Updater(token=BOT_TOKEN,use_context=True)
bot = updater.bot
dispatcher = updater.dispatcher


def app_cycling():
    RESET_MINS = 10
    WAIT_SEC = 10
    POLLING_INT = (int(RESET_MINS/2))*60
    LOGGER.info(f"App cycling func started..restarting app every {RESET_MINS} mins")
    while True:
        time.sleep(POLLING_INT)
        elapsed_secs = int(time.time() - botStartTime)
        mins_passed = int(elapsed_secs/60)
        if mins_passed >= RESET_MINS:
            LOGGER.info("Cycling started..Stopping tg updater")
            try:
                updater.stop()
                LOGGER.info(f"waiting for {WAIT_SEC} sec")
                time.sleep(WAIT_SEC)
                LOGGER.info("Starting tg updater")
                updater.start_polling()
            except Exception as e:
                LOGGER.error(f"Failed to cycle: {str(e)}")
            else:
                LOGGER.info("Cycling completed")

