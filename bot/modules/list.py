from telegram.ext import CommandHandler, run_async
from bot.helper.drive_utils.gdriveTools import GoogleDriveHelper
from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands

@run_async
def list_drive(update,context):
    try:
        search = update.message.text.split(' ', maxsplit=1)[1].strip()
        LOGGER.info(f"Searching: {search}")
        reply = sendMessage('🧐 <b>Searching...Please wait</b>', context.bot, update)
        gdrive = GoogleDriveHelper()
        msg, button = gdrive.drive_list(search)
        if button:
            editMessage(msg, reply, button)
        elif msg == "error":
            editMessage(f'😵 <b>Error occurred while searching. Please retry</b>❗\nYou can use <code>/srch -d query</code> for tv/web series or append year of release to further refine the query.', reply, button)
        else:
            editMessage(f'🙅‍♂ <b>No result found for</b> <i>{search}</i>❗', reply)
    except IndexError:
        sendMessage('😡 <b>Send a search query along with the command</b>❗\nYou can use <code>/srch -d query</code> for tv/web series or append year of release to further refine the query.', context.bot, update)
    except AttributeError as e:
        LOGGER.error(f"msg: {str(e)}")


list_handler = CommandHandler(BotCommands.ListCommand, list_drive,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(list_handler)
