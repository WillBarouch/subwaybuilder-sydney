"""Minimal reader for the game's app.asar (to inspect the bundled JS)."""
import json, struct, sys

ASAR = '/mnt/c/Users/Willb/AppData/Local/Programs/Subway Builder/game/resources/app.asar'

def load(path=ASAR):
    f = open(path, 'rb')
    _, hsize = struct.unpack('<II', f.read(8))
    pickle = f.read(hsize)
    slen = struct.unpack('<I', pickle[4:8])[0]
    header = json.loads(pickle[8:8 + slen])
    return f, header, 8 + hsize

def files(header, prefix=''):
    for k, v in header.get('files', {}).items():
        p = f'{prefix}/{k}'
        if 'files' in v:
            yield from files(v, p)
        elif 'offset' in v:
            yield p, int(v['offset']), v['size']

def read(path_in_asar, asar=ASAR):
    f, h, base = load(asar)
    for p, o, s in files(h):
        if p == path_in_asar:
            f.seek(base + o)
            return f.read(s)
    raise KeyError(path_in_asar)

if __name__ == '__main__':
    f, h, base = load()
    for p, o, s in files(h):
        if len(sys.argv) < 2 or sys.argv[1] in p:
            print(f'{s:>10} {p}')
