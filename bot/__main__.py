import threading
from telegram.ext import CommandHandler, run_async
from bot import dispatcher, updater, app_cycling
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import *
from .helper.telegram_helper.filters import CustomFilters
from .modules import authorize, list


@run_async
def start(update, context):
    LOGGER.info('UID: {} - UN: {} - MSG: {}'.format(update.message.chat.id,update.message.chat.username,update.message.text))
    if update.message.chat.type == "private" :
        sendMessage(f"Hey <b>{update.message.chat.first_name}</b>,\nWelcome to <b>Google Drive Search Bot</b>. Use <code>/{BotCommands.ListCommand} query</code> to search.\n<i>You can use <code>/srch -d query</code> for searching tv/web series or append year of release to further refine the query.</i>", context.bot, update)
    else:
        sendMessage("I'm alive :)", context.bot, update)


@run_async
def log(update, context):
    sendLogFile(context.bot, update)


def main():

    start_handler = CommandHandler(BotCommands.StartCommand, start, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(log_handler)

    updater.start_polling()
    LOGGER.info("Yeah I'm running!")
    threading.Thread(target=app_cycling).start()
    updater.idle()


main()
