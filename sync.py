import hashlib, os, math
from concurrent.futures import ThreadPoolExecutor

def scan_block(block,blocksize):
    with open(block['path'],'rb') as f:
        f.seek(block['start'])
        block['hash'] = hashlib.sha256(f.read(blocksize)).hexdigest()
    return block

def scan_folder(tld,last_blocks,blocksize=65536,max_threads=256):
    walk = os.walk(tld)
    paths = []
    for d in walk:
        paths.extend([os.path.join(d[0],i) for i in d[2]])
    
    files_to_process = {}
    to_remove = [p for p in last_blocks.keys() if not p in paths]
    for p in paths:
        stats = os.stat(p)
        if not p in last_blocks.keys():
            files_to_process[p] = {
                'atime':stats.st_mtime,
                'blocks':[{
                    'blksize':blocksize,
                    'start':x*blocksize,
                    'hash':''
                } for x in range(math.ceil(stats.st_size/blocksize))]
            }
        else:
            if last_blocks[p]['atime'] != stats.st_mtime:
                files_to_process[p] = {
                    'atime':last_blocks[p]['atime'],
                    'blocks':[{
                        'blksize':blocksize,
                        'start':x*blocksize,
                        'hash':''
                    } for x in range(math.ceil(stats.st_size/blocksize))]
                }

    blocks = []
    for f in files_to_process.keys():
        blocks.extend([{
            'path':f,
            'blksize':k['blksize'],
            'start':k['start'],
            'hash':k['hash']
        } for k in files_to_process[f]['blocks']])
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(scan_block,block,blocksize) for block in blocks]
    blocks = [future.result() for future in futures]
    new_files = {i:last_blocks[i] for i in last_blocks.keys() if not i in files_to_process.keys()}
    new_blocks = []
    for b in blocks:
        tb = {
            'blksize':b['blksize'],
            'start':b['start'],
            'hash':b['hash']
        }
        if not b['path'] in new_files.keys():
            if b['path'] in last_blocks.keys():
                lbat = last_blocks[b['path']]['atime']
                if any([True for x in last_blocks[b['path']]['blocks'] if x['hash'] == b['hash']]):
                    new_blocks.append(b.copy())
            else:
                lbat = files_to_process[b['path']]['atime']
                new_blocks.append(b.copy())
            new_files[b['path']] = {
                'atime':lbat,
                'blocks':[]
            }
        new_files[b['path']]['blocks'].append(tb.copy())
    
    cmds = [{
    'command':'MOD',
    'block':i
    } for i in new_blocks]
    cmds.extend([{
        'command':'DEL',
        'path':i
    } for i in to_remove])

    return new_files, cmds