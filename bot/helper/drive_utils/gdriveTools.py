import os
import pickle
import re
import requests
import logging
import telegraph
import time
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram import InlineKeyboardMarkup
from bot.helper.telegram_helper import button_builder
from bot import DRIVE_NAME, DRIVE_ID, INDEX_URL, telegra_ph, HEROKU_INDEX_URL

LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
TELEGRAPH_PAGE_SIZE = 50
TELEGRAPH_MAX_NUMOFPAGE = 2
MAX_RETRY = 1
SLEEP_SEC = 5


class GoogleDriveHelper:
    def __init__(self, name=None, listener=None):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        self.__service = self.authorize()
        self.telegraph_content = []
        self.path = []
        self.num_of_path = 0
        self.telegraph_content_size = 0
        self.search_query = None
        self.retry_count = 0
        self.isDriveLink = True
        self.initial_res = None
        self.telegraph_page_size = TELEGRAPH_PAGE_SIZE

    def get_readable_file_size(self, size_in_bytes) -> str:
        if size_in_bytes is None:
            return '0B'
        index = 0
        size_in_bytes = int(size_in_bytes)
        while size_in_bytes >= 1024:
            size_in_bytes /= 1024
            index += 1
        try:
            return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
        except IndexError:
            return 'File too large'

    def authorize(self):
        # Get credentials
        credentials = None
        if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
            with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.__OAUTH_SCOPE)
                LOGGER.info(flow)
                credentials = flow.run_console(port=0)

            # Save the credentials for the next run
            with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                pickle.dump(credentials, token)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def get_recursive_list(self, file, rootid="root"):
        rtnlist = []
        if not rootid:
            rootid = file.get('teamDriveId')
        if rootid == "root":
            rootid = self.__service.files().get(fileId='root', fields="id").execute().get('id')
        x = file.get("name")
        y = file.get("id")
        while y != rootid:
            rtnlist.append(x)
            file = self.__service.files().get(
                fileId=file.get("parents")[0],
                supportsAllDrives=True,
                fields='id, name, parents'
            ).execute()
            x = file.get("name")
            y = file.get("id")
        rtnlist.reverse()
        return rtnlist

    def drive_query(self, parent_id, search_type, fileName, quality_check):
        try:
            query = ""
            if search_type is not None:
                if search_type == '-d':
                    query += "mimeType = 'application/vnd.google-apps.folder' and "
                elif search_type == '-f':
                    query += "mimeType != 'application/vnd.google-apps.folder' and "
            var = re.split('[ ._,\\[\\]-]', fileName)
            for text in var:
                if quality_check and re.search(quality_check, text):
                    continue
                query += f"name contains '{text}' and "
            query += "trashed=false"
            if parent_id != "root":
                response = self.__service.files().list(supportsTeamDrives=True,
                                                       includeTeamDriveItems=True,
                                                       teamDriveId=parent_id,
                                                       q=query,
                                                       corpora='drive',
                                                       spaces='drive',
                                                       pageSize=TELEGRAPH_PAGE_SIZE,
                                                       fields='files(id, name, mimeType, size, teamDriveId, parents)',
                                                       orderBy='folder, modifiedTime desc').execute()["files"]
            else:
                response = self.__service.files().list(q=query + " and 'me' in owners",
                                                       pageSize=TELEGRAPH_PAGE_SIZE,
                                                       spaces='drive',
                                                       fields='files(id, name, mimeType, size, parents)',
                                                       orderBy='folder, modifiedTime desc').execute()["files"]
            return response
        except Exception as err:
            err = str(err).replace('>', '').replace('<', '')
            LOGGER.error(err)
            return "listErr"

    def edit_telegraph(self):
        nxt_page = 1
        prev_page = 0
        for content in self.telegraph_content:
            if nxt_page == 1:
                content += f'<b><a href="https://telegra.ph/{self.path[nxt_page]}">Next</a></b> ▶️'
                nxt_page += 1
            else:
                if prev_page <= self.num_of_path:
                    content += f'◀️ <b><a href="https://telegra.ph/{self.path[prev_page]}">Previous</a></b>'
                    prev_page += 1
                if nxt_page < self.num_of_path:
                    content += f'<b> | <a href="https://telegra.ph/{self.path[nxt_page]}">Next</a></b> ▶️'
                    nxt_page += 1
            telegra_ph.edit_page(path=self.path[prev_page],
                                 title='Gdrive Search',
                                 author_name='CyberSpace',
                                 author_url='https://github.com/sachinOraon',
                                 html_content=content)
        return

    def retry_drive_list(self):
        time.sleep(SLEEP_SEC)
        self.telegraph_content.clear()
        self.path.clear()
        self.retry_count += 1
        return self.drive_list(self.search_query)

    def drive_list(self, fileName):
        if self.search_query is None:
            self.search_query = fileName
        search_type = None
        quality_check = None
        chars = ['\\', "'", '"', r'\a', r'\b', r'\f', r'\n', r'\r', r'\s', r'\t']
        for char in chars:
            fileName = fileName.replace(char, ' ')
        if re.search("^-d ", fileName, re.IGNORECASE):
            search_type = '-d'
            fileName = fileName[2: len(fileName)]
        elif re.search("^-f ", fileName, re.IGNORECASE):
            search_type = '-f'
            fileName = fileName[2: len(fileName)]
        if re.search("2160", fileName):
            quality_check = "2160"
        elif re.search("1080", fileName):
            quality_check = "1080"
        elif re.search("720", fileName):
            quality_check = "720"
        elif re.search("480", fileName):
            quality_check = "480"
        if len(fileName) > 2:
            remove_list = ['A', 'a', 'X', 'x']
            if fileName[1] == ' ' and fileName[0] in remove_list:
                fileName = fileName[2: len(fileName)]
        msg = ''
        INDEX = -1
        content_count = 0
        all_contents_count = 0
        add_title_msg = True
        for parent_id in DRIVE_ID:
            add_drive_title = True
            INDEX += 1
            if all_contents_count > (self.telegraph_page_size * TELEGRAPH_MAX_NUMOFPAGE) and not self.isDriveLink:
                break
            response = self.drive_query(parent_id, search_type, fileName, quality_check)
            if response == "listErr":
                LOGGER.error(f"Error while searching: {fileName} in: {DRIVE_NAME[INDEX]}")
                continue
            else:
                for file in response:
                    if quality_check and not re.search(quality_check, file.get('name')):
                        continue
                    if add_title_msg:
                        msg = f'<h4>Search Results For: {fileName}</h4><br>'
                        add_title_msg = False
                    if add_drive_title:
                        msg += f"╾────────────╼<br><b>{DRIVE_NAME[INDEX]}</b><br>╾────────────╼<br>"
                        add_drive_title = False
                    # Detect Whether Current Entity is a Folder or File.
                    if file.get('mimeType') == "application/vnd.google-apps.folder":
                        msg += f"📁 <code>{file.get('name')}<br>(folder)</code><br>"
                        if INDEX_URL[INDEX] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            url = f'{INDEX_URL[INDEX]}/{url_path}/'
                            msg += f' ⚡️ <b><a href="{url}">Index Link</a></b>'
                    elif file.get('mimeType') == 'application/vnd.google-apps.shortcut' and self.isDriveLink:
                        msg += f"♻️ <a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                               f"</a> (shortcut)"
                        # Excluded index link as indexes cant download or open these shortcuts
                    else:
                        try:
                            msg += f"📌 <code>{file.get('name')} ({self.get_readable_file_size(int(file.get('size')))})</code><br>"
                        except TypeError:
                            msg += f"📌 <code>{file.get('name')}</code><br>"
                        if INDEX_URL[INDEX] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            iurl = f'{INDEX_URL[INDEX]}/{url_path}?a=view'
                            msg += f' ⚡️ <b><a href="{iurl}">Index Link</a></b>'
                        if HEROKU_INDEX_URL is not None:
                            vurl = f'vlc://{HEROKU_INDEX_URL}/api/file/download/{file.get("id")}'
                            murl = f'intent:{HEROKU_INDEX_URL}/api/file/download/{file.get("id")}'
                            murl += f'#Intent;package=com.mxtech.videoplayer.ad;S.title={file.get("name")};end'
                            nurl = f'nplayer-{HEROKU_INDEX_URL}/api/file/download/{file.get("id")}'
                            msg += f' 📀 <b><a href="{vurl}">VLC</a></b>'
                            msg += f' 🌀 <b><a href="{murl}">MX Player</a></b>'
                            msg += f' 🔆 <b><a href="{nurl}">nPlayer</a></b>'
                    msg += '<br><br>'
                    content_count += 1
                    all_contents_count += 1
                    if content_count >= self.telegraph_page_size:
                        self.telegraph_content.append(msg)
                        msg = ""
                        content_count = 0

        LOGGER.info(f"Search: {fileName} Found: {all_contents_count}")
        if self.initial_res is None:
            self.initial_res = all_contents_count

        if msg != '':
            self.telegraph_content.append(msg)

        self.telegraph_content_size = len(self.telegraph_content)
        if self.telegraph_content_size == 0:
            return "", None

        try:
            for content in self.telegraph_content:
                self.path.append(telegra_ph.create_page(
                    title='Gdrive Search',
                    author_name='CyberSpace',
                    author_url='https://github.com/sachinOraon',
                    html_content=content
                )['path'])
        except telegraph.TelegraphException:
            LOGGER.error(f"Failed to create page for: {fileName}")
            if self.retry_count < MAX_RETRY:
                self.isDriveLink = False
                self.telegraph_page_size -= 10
                LOGGER.info(f"Retry search and page creation for: {fileName}")
                return self.retry_drive_list()
            else:
                if not self.isDriveLink:
                    LOGGER.error(f"Failed to create page for: {fileName} even after retrying")
                return "error", None
        except Exception as e:
            if self.retry_count < MAX_RETRY:
                LOGGER.error(f"Telegraph error for: {fileName} Retrying after 5 sec")
                self.isDriveLink = True
                return self.retry_drive_list()
            else:
                LOGGER.error(f"Telegraph error for: {fileName} msg: {str(e)}")
                return "error", None
        else:
            self.num_of_path = len(self.path)
            if self.num_of_path > 1:
                self.edit_telegraph()

            if self.isDriveLink:
                msg = f"💁🏻‍♂ <b>Found <code>{all_contents_count}</code> results for </b><i>{fileName}</i>"
            else:
                msg = f"💁🏻‍♂ <b>Found <code>{self.initial_res}</code> results for </b><i>{fileName}</i>"
                msg += "\n⚠️ Showing only top <code>"+str(all_contents_count) if self.initial_res > all_contents_count else str(self.initial_res)
                msg += "</code> results. Please refine your query to get appropriate results."

            buttons = button_builder.ButtonMaker()
            buttons.buildbutton("🔎 Tap here to view", f"https://telegra.ph/{self.path[0]}")
            return msg, InlineKeyboardMarkup(buttons.build_menu(1))
