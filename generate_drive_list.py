import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


CRED_JSON_FILE = "credentials.json"
TOKEN_PICKLE_FILE = "token.pickle"
GDRIVE_API_URL = "https://www.googleapis.com/auth/drive"
INDEX_URLS = [
    "https://1.workers.dev/",
    "https://2.workers.dev/",
    "https://3.workers.dev/",
    "https://4.workers.dev/",
    "https://5.workers.dev/",
    "https://6.workers.dev/"
]
BATCH_SIZE = 10


def authorize():
    print(f"{TOKEN_PICKLE_FILE} not found..calling flow")
    if os.path.exists(CRED_JSON_FILE):
        flow = InstalledAppFlow.from_client_secrets_file(CRED_JSON_FILE, [GDRIVE_API_URL])
        creds = flow.run_console(port=0)
        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            print("dumping credentials for next run")
            pickle.dump(creds, token)
        return creds
    else:
        print(f"{CRED_JSON_FILE} not found..exiting")
        exit()


def get_drives_list(credential):
    try:
        print("building service: drive")
        service = build('drive', 'v3', credentials=credential, cache_discovery=False)
        collection = service.drives().list(pageSize=100, pageToken=None, q=None, useDomainAdminAccess=None)
        drives_list = collection.execute()["drives"]
        file1 = open("file1.txt", "w")
        file2 = open("file2.txt", "w")
        print("writing data to files")
        idx = 0
        drv_idx = 0
        new_line = False
        for index, drive in enumerate(drives_list):
            if (index + 1) % BATCH_SIZE == 0:
                idx += 1
                drv_idx = 0
                new_line = True
            data1 = f'Drive_{index} {drive["id"]} {INDEX_URLS[idx]}{drv_idx}:\n'
            data2 = f'{{"name": "Drive_{index}", "id": "{drive["id"]}", "protect_file_link": false}},'
            file1.write(data1)
            if new_line:
                file2.write("\n" + data2)
                new_line = False
            else:
                file2.write(data2)
            drv_idx += 1
    except Exception as err:
        print(f"ERROR: {str(err)}")
    else:
        file1.close()
        file2.close()


credentials = None
if os.path.exists(TOKEN_PICKLE_FILE):
    with open(TOKEN_PICKLE_FILE, 'rb') as f:
        credentials = pickle.load(f)
        if credentials and credentials.expired and credentials.refresh_token:
            print("credentials expired..refreshing")
            credentials.refresh(Request())
else:
    credentials = authorize()
get_drives_list(credentials)
