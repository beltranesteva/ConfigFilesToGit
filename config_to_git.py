import requests
import json
import logging.config
import gzip
import os
import re
import time
from datetime import datetime
from requests.exceptions import Timeout
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv(".env", verbose=True)

logging.config.fileConfig(fname=r'logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)

BASE_URL = os.environ.get('BASE_URL')
PROJECT_ID = os.environ.get('PROJECT_ID')

TOKEN = os.environ.get('PRIVATE-TOKEN')
PATH_TO_FILES = os.environ.get('PATH_TO_FILES')

HEADERS = {
    'Content-Type': 'application/json',
    'PRIVATE-TOKEN': TOKEN
}

# declaring error google chat webhook
GCHAT_WEBHOOK = os.environ.get('GCHAT_WEBHOOK')

# allow self signed certs
requests.packages.urllib3.disable_warnings()

# retry strategy
retry_strategy = Retry(
    total=3,
    status_forcelist=[408, 429, 500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "OPTIONS", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

# declaring error messages
error_msg = {
    "TimeOut": "Request timeout!",
    "HttpError": "Error status code recieved",
    "ConnectionError": "Connection error",
    "RequestException": "Request Exception error",
    "TypeError": "Type error",
    "UncaughtError": "Unexpected error"
}


def error_handler(fn):
    """
    Function to handle requests errors
    :param fn: any request
    :return: request output
    """
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Timeout:
            logger.exception('API REQUEST TIME OUT')
            error = {"text": error_msg['TimeOut']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'TimeOut'}, 408
        except requests.exceptions.HTTPError:
            logger.exception('ERROR STATUS CODE RECEIVED', exc_info=True)
            error = {"text": error_msg['HttpError']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'HttpError'}
        except requests.exceptions.ConnectionError:
            logger.exception('CONNECTION ERROR', exc_info=True)
            error = {"text": error_msg['ConnectionError']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'ConnectionError'}
        except requests.exceptions.RequestException:
            logger.exception('THERE WAS AN ERROR WHEN TRYING TO CONNECT TO THE API', exc_info=True)
            error = {"text": error_msg['RequestException']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'RequestException'}
        except TypeError:
            logger.exception('TYPE ERROR', exc_info=True)
            error = {"text": error_msg['TypeError']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'TypeError'}
        except Exception:
            logger.exception('UNCAUGHT ERROR', exc_info=True)
            error = {"text": error_msg['UncaughtError']}
            requests.post(url=GCHAT_WEBHOOK, data=json.dumps(error))
            return {'Message': 'UncaughtError'}

    return wrapper


class FileChangedHandler(FileSystemEventHandler):
    def on_created(self, event):
        """Function expects new .gz files to be created inside the given path. When found, it unzips it and uploaded it to git repo"""
        time.sleep(30)  # time sleep is key for this script to work, otherwise it cant read the file contents...dont ask why
        filename, file_extension = os.path.splitext(event.src_path)

        if file_extension == '.gz':
            logger.info('New file founded %s', event.src_path)
            # os.chmod(event.src_path, 0o6666)

            # unzipping the file and graving its contents
            with gzip.open(event.src_path, 'rt+', encoding="ISO-8859-1") as f:
                raw_config = f.read()

            # obtaining the device out of the filename in order to use it as repo name
            filename = filename.split('/')
            filename_split = filename[3].split()[0]
            device = re.split('_|-', filename_split)[0]  # since there might be devices with _ or - it gets slitted by both

            # logger.info('RAW CONFIG -> %s', raw_config[0:40])
            git = Git(project_id=PROJECT_ID, name=device)
            r = git.update_repo(raw_config)

            # repo may not be created hence we need to check if the initial api call response for in that case it must be first created and then uploaded
            if r.json()['message'] == 'A file with this name doesn\'t exist':
                logger.info('Status code when no repo with the given name -> %s', r.status_code)
                git.create_repo()
                time.sleep(1)
                r = git.update_repo(raw_config)

            logger.info(r.json())

            # if upload turns out ok, file gets deleted
            # if r.status_code == 201:
            #     os.remove(file)
            #     logger.info('FILE %s REMOVED!', file)


class Git:
    def __init__(self, project_id, name):
        self.project_id = project_id
        self.name = name
        self.url = f'{BASE_URL}/projects/{self.project_id}/repository/commits'

    @error_handler
    def create_repo(self):
        """Function to create a path or repository in the given project"""
        payload = {
          "branch": "master",
          "commit_message": str(datetime.utcnow()),
          "actions": [
            {
              "action": "create",
              "file_path": self.name,
              "content": "Initial commit"
            }
          ]
        }

        jpayload = json.dumps(payload)
        r = http.post(url=self.url, headers=HEADERS, data=jpayload, verify=False)
        return r

    @error_handler
    def update_repo(self, content):
        """Function to update the path or repository with the given content"""
        payload = {
          "branch": "master",
          "commit_message": str(datetime.utcnow()),
          "actions": [
            {
              "action": "update",
              "file_path": self.name,
              "content": content
            }
          ]
        }
        jpayload = json.dumps(payload)
        r = http.post(url=self.url, headers=HEADERS, data=jpayload, verify=False)
        return r


if __name__ == "__main__":

    observer = Observer()
    event_handler = FileChangedHandler()
    observer.schedule(event_handler, PATH_TO_FILES, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
