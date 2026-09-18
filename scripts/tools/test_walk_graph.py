"""Check build_walk_graph.encode against the game's own encoder, and sanity-check
the built walk_graph.bin.gz.

The game's encoder is pulled out of the locally installed bundle at run time
into .scratch/ (it is the game's code, so it is not kept in this repo), then run
with Node on the same random graph as our Python port; the bytes must match.

    python scripts/tools/test_walk_graph.py
"""
import sys, os, re, json, gzip, glob, subprocess, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import numpy as np
import asar
from mapconfig import CITY_DIR
from build_walk_graph import encode

NODE = '/mnt/c/nvm4w/nodejs/node.exe'
SCRATCH = os.path.abspath('.scratch/game'); os.makedirs(SCRATCH, exist_ok=True)


def extract_game_encoder():
    f, h, base = asar.load()
    idx = next(p for p, o, s in asar.files(h) if re.match(r'/dist/renderer/public/index-.*\.js$', p))
    s = asar.read(idx).decode('utf8', 'replace')
    out = []
    for c in ['WALK_GRAPH_MAGIC', 'WALK_GRAPH_VERSION', 'WALK_GRAPH_HEADER_SIZE', 'WALK_GRAPH_COORD_SCALE']:
        out.append(f"const {c} = {re.search(c + r' = ([^,;]+)', s).group(1)};")
    for name in ['computeWalkGraphSectionOffsets', 'writeWalkGraphHeader', 'readWalkGraphHeader', 'encodeWalkGraphBinary']:
        i = s.find('function ' + name + '('); j = s.find('{', i); d = 0
        for k in range(j, len(s)):
            d += (s[k] == '{') - (s[k] == '}')
            if d == 0:
                out.append(s[i:k + 1]); break
    out.append('module.exports = { encodeWalkGraphBinary, readWalkGraphHeader, computeWalkGraphSectionOffsets };')
    path = os.path.join(SCRATCH, 'game_walkgraph.cjs')
    open(path, 'w').write('\n'.join(out) + '\n')
    return path


def win(p):
    return subprocess.run(['wslpath', '-w', p], capture_output=True, text=True).stdout.strip()


def main():
    mod = extract_game_encoder()
    rng = np.random.default_rng(1)
    n, m = 60, 150
    nodes = np.column_stack([151 + rng.random(n) * 0.1, -33.9 + rng.random(n) * 0.1])
    a = rng.integers(0, n, m); b = (a + 1 + rng.integers(0, n - 1, m)) % n
    lengths = rng.random(m) * 500
    geoms = [np.column_stack([151 + rng.random(k) * 0.1, -33.9 + rng.random(k) * 0.1]) for k in rng.integers(0, 4, m)]
    ours = encode(nodes, a, b, lengths, geoms)
    spec = {'nodes': nodes.tolist(), 'edges': [
        {'a': int(x), 'b': int(y), 'lengthM': float(L), **({'geometry': g.tolist()} if len(g) else {})}
        for x, y, L, g in zip(a, b, lengths, geoms)]}
    sp = os.path.join(SCRATCH, 'wg_spec.json'); json.dump(spec, open(sp, 'w'))
    gp = os.path.join(SCRATCH, 'wg_game.bin')
    js = (f"const g=require({json.dumps(win(mod))});const fs=require('fs');"
          f"const s=JSON.parse(fs.readFileSync({json.dumps(win(sp))},'utf8'));"
          f"fs.writeFileSync({json.dumps(win(gp))},Buffer.from(g.encodeWalkGraphBinary(s)));")
    subprocess.run([NODE, '-e', js], check=True)
    theirs = open(gp, 'rb').read()
    assert ours == theirs, f'encoder mismatch: {len(ours)} vs {len(theirs)} bytes'
    print(f'encoder: byte-identical to the game ({len(ours)} bytes, {m} edges)')

    # the real file: header via the game's reader, sizes, CSR consistency
    path = f'{CITY_DIR}/walk_graph.bin.gz'
    buf = gzip.open(path).read()
    raw = os.path.join(SCRATCH, 'wg_real.bin'); open(raw, 'wb').write(buf)
    js = (f"const g=require({json.dumps(win(mod))});const b=require('fs').readFileSync({json.dumps(win(raw))});"
          f"const ab=b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);const h=g.readWalkGraphHeader(new DataView(ab));"
          f"const L=g.computeWalkGraphSectionOffsets(h);console.log(JSON.stringify({{h,total:L.totalSize,len:ab.byteLength}}));")
    r = json.loads(subprocess.run([NODE, '-e', js], check=True, capture_output=True, text=True).stdout)
    h = r['h']
    assert r['total'] == r['len'], r
    n, m = h['nodeCount'], h['edgeCount']
    off = 56 + n * 8
    first = np.frombuffer(buf, '<u4', n + 1, off); off += (n + 1) * 4
    target = np.frombuffer(buf, '<u4', 2 * m, off); off += 8 * m
    ref = np.frombuffer(buf, '<u4', 2 * m, off); off += 8 * m
    length = np.frombuffer(buf, '<f4', m, off)
    assert first[0] == 0 and first[-1] == 2 * m and np.all(np.diff(first.astype(np.int64)) >= 1), 'isolated node or bad CSR'
    assert target.max() < n and (ref >> 1).max() < m
    assert np.all(length > 0), 'zero-length edge'
    print(f"{os.path.basename(path)}: game reader OK, {n:,} nodes, {m:,} edges, bbox "
          f"{h['minLon']:.3f},{h['minLat']:.3f} .. {h['maxLon']:.3f},{h['maxLat']:.3f}; "
          f"every node has an edge; edge lengths {length.min():.2f}-{length.max():.0f} m")


if __name__ == '__main__':
    main()
