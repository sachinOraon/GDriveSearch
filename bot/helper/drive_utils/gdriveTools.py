import os
import pickle
import re
import requests
import logging
import telegraph
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram import InlineKeyboardMarkup
from bot.helper.telegram_helper import button_builder
from bot import DRIVE_NAME, DRIVE_ID, INDEX_URL, telegra_ph

LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
TELEGRAPHLIMIT = 50


class GoogleDriveHelper:
    def __init__(self, name=None, listener=None):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        self.__service = self.authorize()
        self.telegraph_content = []
        self.path = []
        self.num_of_path = 0

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
        while (y != rootid):
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

    def drive_query(self, parent_id, search_type, fileName):
        try:
            query = ""
            if search_type is not None:
                if search_type == '-d':
                    query += "mimeType = 'application/vnd.google-apps.folder' and "
                elif search_type == '-f':
                    query += "mimeType != 'application/vnd.google-apps.folder' and "
            var = re.split('[ ._,\\[\\]-]', fileName)
            for text in var:
                query += f"name contains '{text}' and "
            query += "trashed=false"
            if parent_id != "root":
                response = self.__service.files().list(supportsTeamDrives=True,
                                                       includeTeamDriveItems=True,
                                                       teamDriveId=parent_id,
                                                       q=query,
                                                       corpora='drive',
                                                       spaces='drive',
                                                       pageSize=TELEGRAPHLIMIT,
                                                       fields='files(id, name, mimeType, size, teamDriveId, parents)',
                                                       orderBy='folder, modifiedTime desc').execute()["files"]
            else:
                response = self.__service.files().list(q=query + " and 'me' in owners",
                                                       pageSize=TELEGRAPHLIMIT,
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

    def drive_list(self, fileName):
        search_type = None
        chars = ['\\', "'", '"', r'\a', r'\b', r'\f', r'\n', r'\r', r'\s', r'\t']
        for char in chars:
            fileName = fileName.replace(char, ' ')
        if re.search("^-d ", fileName, re.IGNORECASE):
            search_type = '-d'
            fileName = fileName[2: len(fileName)]
        elif re.search("^-f ", fileName, re.IGNORECASE):
            search_type = '-f'
            fileName = fileName[2: len(fileName)]
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
            response = self.drive_query(parent_id, search_type, fileName)
            if response == "listErr":
                LOGGER.error(f"Error while searching: {fileName} in: {DRIVE_NAME[INDEX]}")
                continue
            else:
                for file in response:
                    if add_title_msg:
                        msg = f'<h4>Search Results For: {fileName}</h4><br>'
                        add_title_msg = False
                    if add_drive_title:
                        msg += f"╾────────────╼<br><b>{DRIVE_NAME[INDEX]}</b><br>╾────────────╼<br>"
                        add_drive_title = False
                    if file.get('mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                        msg += f"📁 <code>{file.get('name')}<br>(folder)</code><br>" \
                               f"🌥️ <b><a href='https://drive.google.com/drive/folders/{file.get('id')}'>Drive Link</a></b>"
                        if INDEX_URL[INDEX] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            url = f'{INDEX_URL[INDEX]}/{url_path}/'
                            msg += f' ⚡️ <b><a href="{url}">Index Link</a></b>'
                    elif file.get('mimeType') == 'application/vnd.google-apps.shortcut':
                        msg += f"♻️ <a href='https://drive.google.com/drive/folders/{file.get('id')}'>{file.get('name')}" \
                               f"</a> (shortcut)"
                        # Excluded index link as indexes cant download or open these shortcuts
                    else:
                        msg += f"📌 <code>{file.get('name')} ({self.get_readable_file_size(int(file.get('size')))})</code><br>" \
                               f"🌥️ <b><a href='https://drive.google.com/uc?id={file.get('id')}&export=download'>Drive Link</a></b>"
                        if INDEX_URL[INDEX] is not None:
                            url_path = "/".join(
                                [requests.utils.quote(n, safe='') for n in self.get_recursive_list(file, parent_id)])
                            url = f'{INDEX_URL[INDEX]}/{url_path}'
                            vurl = f'{INDEX_URL[INDEX]}/{url_path}?a=view'
                            msg += f' ⚡️ <b><a href="{url}">Index Link</a></b>'
                            msg += f' 📀 <b><a href="{vurl}">View Link</a></b>'
                    msg += '<br><br>'
                    content_count += 1
                    all_contents_count += 1
                    if content_count >= TELEGRAPHLIMIT:
                        self.telegraph_content.append(msg)
                        msg = ""
                        content_count = 0

        LOGGER.info(f"Search query: {fileName} Found: {all_contents_count}")

        if msg != '':
            self.telegraph_content.append(msg)

        if len(self.telegraph_content) == 0:
            return "", None

        try:
            for content in self.telegraph_content:
                self.path.append(telegra_ph.create_page(
                    title='Gdrive Search',
                    author_name='CyberSpace',
                    author_url='https://github.com/sachinOraon',
                    html_content=content
                )['path'])
        except telegraph.TelegraphException as e:
            LOGGER.error("Failed to create telegraph page")
            return "telegraphException", None
        except Exception as e:
            LOGGER.error(e)
            return "error", None
        else:
            self.num_of_path = len(self.path)
            if self.num_of_path > 1:
                self.edit_telegraph()

            msg = f"💁🏻‍♂ <b>Found <code>{all_contents_count}</code> results for </b><i>{fileName}</i>"

            buttons = button_builder.ButtonMaker()
            buttons.buildbutton("🔎 Tap here to view", f"https://telegra.ph/{self.path[0]}")
            return msg, InlineKeyboardMarkup(buttons.build_menu(1))
