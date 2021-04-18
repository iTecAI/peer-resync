from socket import *
from peerbase import Node, ip
from fastapi import FastAPI, staticfiles, responses, status
from pydantic import BaseModel, ConfigError
import threading
import time
import json
import sys
import os
import logging
from logging import debug, info, warning, error, critical
from starlette.responses import FileResponse, Response
from starlette.status import HTTP_404_NOT_FOUND
import uvicorn
import os
from sync import scan_folder

from pydantic.errors import ConfigError
from uvicorn.config import LOG_LEVELS


class Database:
    def __init__(self, path):
        self.path = path

    def _open(self):
        with open(self.path, 'r') as f:
            return json.load(f)

    def _save(self, data):
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=4)

    def __len__(self):
        return len(self._open().keys())

    def __getitem__(self, key):
        return self._open()[key]

    def __setitem__(self, key, value):
        dct = self._open()
        dct[key] = value
        self._save(dct.copy())

    def __delitem__(self, key):
        dct = self._open()
        del dct[key]
        self._save(dct.copy())

    def keys(self):
        return self._open().keys()

    def values(self):
        return self._open().values()
    
    def __dict__(self):
        return self._open()

    def set(self, keys, value):
        if len(keys) == 1:
            self[keys[0]] = value
            return
        dct = self._open()
        jned = '"]["'.join(keys[1:])
        exec(f'dct[keys.pop(0)]["{jned}"] = value',{'dct':dct,'keys':keys,'value':value})
        self._save(dct)
    def delete(self, keys):
        if len(keys) == 1:
            del self[keys[0]]
        else:
            dct = self._open()
            jned = '"]["'.join(keys[1:])
            exec(f'del dct[keys.pop(0)]["{jned}"]',{'dct':dct,'keys':keys})
            self._save(dct)


def dval(dct, test):
    for k in test.keys():
        if not k in dct.keys():
            return False
        if type(test[k]) == dict:
            if not dval(dct[k], test[k]):
                return False
        else:
            if not test[k] == type(dct[k]):
                return False
    return True


config_match = {
    'ports': {
        'dashboard': int,
        'node': int,
        'advertiser': int
    },
    'node': {
        'network': str,
        'key': str,
        'name': str,
        'remotes': list
    },
    'logLevel': str,
    'databasePath': str,
    'syncInterval': int,
    'syncFileSystemTop': str
}

LOGLEVELS = {
    'notset': 0,
    'debug': 10,
    'info': 20,
    'warning': 30,
    'error': 40,
    'critical': 50
}

if len(sys.argv) >= 2:
    if os.path.exists(sys.argv[1]):
        with open(sys.argv[1], 'r') as f:
            try:
                conf = json.load(f)
            except json.JSONDecodeError:
                raise ValueError(f'{sys.argv[1]} is an invalid JSON file.')
    else:
        raise OSError(f'Config file not found at {sys.argv[1]}.')
else:
    raise OSError(
        f'Please specify a config file in your command line arguments, such as "python {sys.argv[0]} config.json".')

if not dval(conf, config_match):
    raise ConfigError('Invalid config file.')

logging.basicConfig(level=LOGLEVELS[conf['logLevel'].lower(
)], format='%(levelname)s @ %(threadName)s [%(asctime)s] > %(message)s')
info(f'Loaded configuration file {sys.argv[1]}.')

node_name = conf['node']['name'].format(host=gethostname()).replace(
    '.', '-').replace(':', '-').replace('|', '-')
db_path = os.path.join(*conf['databasePath'].split('/'))
if not os.path.exists(db_path):
    with open(db_path, 'w') as f:
        json.dump({
            "peers": {
                "local": {},
                "remote": {}
            },
            "folders": {}
        }, f)
database = Database(db_path)

node = Node(
    node_name,
    conf['node']['network'],
    conf['node']['key'],
    ports=[conf['ports']['node'], conf['ports']['advertiser']],
    servers=conf['node']['remotes']
)

app = FastAPI()
app.logger = None
app.mount('/dashboard', staticfiles.StaticFiles(directory='client'),
          name='dashboard')

# Request Models =======================================================================
class FolderModel(BaseModel):
    folder_path: str

class ExcludedFolderModel(BaseModel):
    folder_path: str
    excluded: str

# Endpoints ============================================================================
@app.get('/')
async def root():
    return {
        'timestamp': time.time(),
        'network': conf['node']['network'],
        'node_name': node_name
    }


@app.get('/dashboard')
async def get_dashboard():
    return responses.FileResponse(path=os.path.join('client', 'index.html'))


@app.get('/refresh')
async def get_refresh():
    db = dict(database)
    return {
        'peers': db['peers'].copy(),
        'folders': {i:{
            'display_path': db['folders'][i]['display_path'],
            'excluded_paths': db['folders'][i]['excluded_paths'],
            'commands': {
                'mods': len([x['command'] for x in db['folders'][i]['command_buffer'] if x['command'] == 'MOD']),
                'dels': len([x['command'] for x in db['folders'][i]['command_buffer'] if x['command'] == 'DEL'])
            }
        } for i in db['folders'].keys()}
    }

@app.post('/folders/new')
async def post_folder_new(model: FolderModel, response: Response):
    fp = os.path.join(conf['syncFileSystemTop'], os.path.join(*model.folder_path.split('/')))
    if os.path.exists(fp):
        database.set(['folders', model.folder_path.replace('\\','/')], {
            'system_path': fp,
            'display_path': model.folder_path.replace('\\','/'),
            'command_buffer': [],
            'last_blocks': {},
            'excluded_paths': []
        })
        return {'result':'success'}
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'result':f'path {fp} not found'}

@app.post('/folders/stop_tracking')
async def post_folder_stop_tracking(model: FolderModel, response: Response):
    if model.folder_path in database['folders'].keys():
        database.delete(['folders', model.folder_path])
        return {'result': 'success'}
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'result':f'folder {model.folder_path} is not being tracked'}

@app.post('/folders/excluded/add')
async def post_folder_excluded_add(model: ExcludedFolderModel, response: Response):
    if model.folder_path in database['folders'].keys():
        prev = dict(database)
        if not model.excluded.replace('\\','/') in prev['folders'][model.folder_path]['excluded_paths']:
            prev['folders'][model.folder_path]['excluded_paths'].append(model.excluded.replace('\\','/'))
        database._save(prev)
        return {'result': 'success'}
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'result':f'folder {model.folder_path} is not being tracked'}

@app.post('/folders/excluded/remove')
async def post_folder_excluded_remove(model: ExcludedFolderModel, response: Response):
    if model.folder_path in database['folders'].keys():
        prev = dict(database)
        if model.excluded.replace('\\','/') in prev['folders'][model.folder_path]['excluded_paths']:
            prev['folders'][model.folder_path]['excluded_paths'].remove(model.excluded.replace('\\','/'))
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {'result':f'folder {model.excluded} is not being excluded from {model.folder_path}'}
        database._save(prev)
        return {'result': 'success'}
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'result':f'folder {model.folder_path} is not being tracked'}

def peerloop():
    while True:
        database['peers'] = {
            'local': node.peers,
            'remote': {i:list(node.remote_peers[i]) for i in node.remote_peers.keys()}
        }
        time.sleep(0.2)

def scan_folder_loop(path):
    while True:
        pass

if __name__ == "__main__":
    try:
        info(
            f"Starting PeerBase Node {node.name} in a separate thread ({node.name}.main)")
        node.start_multithreaded(thread_name=f'{node.name}.main')
        info(
            f"Starting dashboard at http://{ip()}:{conf['ports']['dashboard']}/dashboard.")
        threading.Thread(target=peerloop, daemon=True).start()
        uvicorn.run('main:app', host=ip(
        ), port=conf['ports']['dashboard'], log_level='warning', access_log=True)
    except KeyError:
        info('Stopping all servers.')
