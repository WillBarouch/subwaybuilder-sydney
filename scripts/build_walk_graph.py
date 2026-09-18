"""Walk graph (walk_graph.bin.gz, SBWG v1) and pedestrian roads for SYD.

Since 1.7.17 the game walks commuters to and from stations along a pedestrian
network instead of in straight lines, if the map ships one. This builds it from
the OSM ways a person can walk on (streets plus footpaths), and adds the
footpaths to roads.geojson as roadClass 'pedestrian' so they show on the map.

The binary is written here rather than with api.utils.walkGraph.encode, laid out
exactly as the game's encodeWalkGraphBinary does (1.7.17 bundle): a 56-byte
header, then node coords, a CSR adjacency (firstEdge / edgeTarget / edgeRef),
edge lengths, and per-edge interior geometry. tests in scripts/tools check it
byte for byte against the game's own encoder.

    python scripts/build_walk_graph.py
"""
import sys, os, gzip, json, math, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
import numpy as np
import osmium
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

SRC = f'{CITY_DIR}/walk/highways.osm.pbf'
OUT = f'{CITY_DIR}/walk_graph.bin.gz'
ROADS = f'{CITY_DIR}/roads.geojson'
ROADS_DEPOT = f'{CITY_DIR}/roads.depot.geojson'      # depot's original, kept so reruns start clean

# --- what counts as walkable -------------------------------------------------
WALK = {'trunk', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary',
        'tertiary_link', 'unclassified', 'residential', 'living_street', 'service', 'road',
        'pedestrian', 'footway', 'path', 'steps', 'cycleway', 'bridleway', 'track', 'corridor'}
# motorways and their ramps are closed to pedestrians in NSW; trunk links are
# mostly freeway-style ramps too, so they need an explicit foot tag
NEEDS_FOOT = {'trunk_link'}
FOOT_OK = {'yes', 'designated', 'permissive', 'official'}
BLOCKED = {'no', 'private'}
# drawn on the map as pedestrian ways (streets are already in depot's roads file)
PEDESTRIAN_CLASS = {'pedestrian', 'footway', 'path', 'steps', 'cycleway', 'bridleway', 'corridor'}

# The docs suggest skipping separately mapped sidewalks and crossings because the
# street centreline covers them. In Sydney that cuts off ~1,000 km of footpath
# networks (the airport precinct, Wolli Creek, new estates) that only reach the
# streets through sidewalks, so they are kept; collapsing degree-2 chains keeps
# the cost down.
KEEP_SIDEWALKS = os.environ.get('SB_WALK_SIDEWALKS', '1') == '1'
MARGIN = 0.02         # deg; ways must touch the map bbox grown by this much

SIMPLIFY_M = 2.0      # geometry only drives how walking dots follow curves
MAX_EDGE_M = 200.0    # demand points snap to NODES within 250 m, so keep nodes this close on long edges

WALK_GRAPH_MAGIC = 1196900947    # 'SBWG' little-endian
WALK_GRAPH_VERSION = 1
HEADER_SIZE = 56
COORD_SCALE = 1e7


def walkable(tags):
    hw = tags.get('highway')
    foot = tags.get('foot')
    if foot in BLOCKED:
        return False
    if hw in NEEDS_FOOT:
        return foot in FOOT_OK
    if hw not in WALK:
        return False
    if tags.get('access') in BLOCKED and foot not in FOOT_OK:
        return False
    if hw == 'service' and tags.get('service') == 'driveway':
        return False                       # hundreds of thousands of dead ends, nothing to walk to
    if not KEEP_SIDEWALKS and (tags.get('footway') in ('sidewalk', 'crossing')
                               or tags.get('path') in ('sidewalk', 'crossing')):
        return False
    return True


class Ways(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.refs, self.coords, self.ped = [], [], []

    def way(self, w):
        t = {k: v for k, v in w.tags}
        if not walkable(t):
            return
        try:
            ids = [n.ref for n in w.nodes]
            xy = [(n.lon, n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(ids) < 2:
            return
        if not any(BBOX[0] - MARGIN <= x <= BBOX[2] + MARGIN and BBOX[1] - MARGIN <= y <= BBOX[3] + MARGIN
                   for x, y in xy):
            return
        self.refs.append(ids)
        self.coords.append(xy)
        if t['highway'] in PEDESTRIAN_CLASS and not (t.get('footway') in ('sidewalk', 'crossing')
                                                     or t.get('path') in ('sidewalk', 'crossing')):
            layer = t.get('bridge') and 'bridge' or (t.get('tunnel') in ('yes', 'building_passage') and 'tunnel') or 'normal'
            self.ped.append((len(self.refs) - 1, layer, t.get('name')))


def seg_lengths(xy):
    """Haversine length of each segment of an (n, 2) lon/lat array, metres."""
    lon, lat = np.radians(xy[:, 0]), np.radians(xy[:, 1])
    dlat, dlon = np.diff(lat), np.diff(lon)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat[:-1]) * np.cos(lat[1:]) * np.sin(dlon / 2) ** 2
    return 2 * 6371008.8 * np.arcsin(np.sqrt(a))


def densify(poly):
    """Add interpolated vertices so no segment is longer than MAX_EDGE_M, so long
    straight stretches (bridges, rural roads) can still be split into short edges."""
    seg = seg_lengths(poly)
    if seg.max() <= MAX_EDGE_M:
        return poly
    out = [poly[:1]]
    for i, L in enumerate(seg):
        k = int(math.ceil(L / MAX_EDGE_M))
        t = np.arange(1, k + 1)[:, None] / k
        out.append(poly[i] + (poly[i + 1] - poly[i]) * t)
    return np.concatenate(out)


def to_lines(polys, kx, ky):
    """Polylines (lon/lat arrays) -> shapely LineStrings in local metres."""
    lens = [len(p) for p in polys]
    xy = np.concatenate(polys) * (kx, ky)
    return shapely.linestrings(xy, indices=np.repeat(np.arange(len(polys)), lens))


def encode(nodes, edges_a, edges_b, lengths, geoms):
    """Byte-for-byte port of the game's encodeWalkGraphBinary (1.7.17)."""
    n, m = len(nodes), len(edges_a)
    gcount = sum(len(g) for g in geoms)
    minlon, minlat = nodes.min(axis=0) if n else (0, 0)
    maxlon, maxlat = nodes.max(axis=0) if n else (0, 0)
    hdr = bytearray(HEADER_SIZE)
    struct.pack_into('<IBBHIIII', hdr, 0, WALK_GRAPH_MAGIC, WALK_GRAPH_VERSION, 0, 0, n, m, gcount, 0)
    struct.pack_into('<dddd', hdr, 24, minlon, minlat, maxlon, maxlat)
    node_coords = np.round(nodes * COORD_SCALE).astype('<i4').ravel()
    deg = np.bincount(edges_a, minlength=n) + np.bincount(edges_b, minlength=n)
    first = np.zeros(n + 1, dtype='<u4'); first[1:] = np.cumsum(deg)
    target = np.zeros(2 * m, dtype='<u4'); ref = np.zeros(2 * m, dtype='<u4')
    cursor = first[:-1].astype(np.int64).copy()
    # same fill order as the JS loop: edge id ascending, a-side then b-side
    for eid in range(m):
        a, b = edges_a[eid], edges_b[eid]
        target[cursor[a]] = b; ref[cursor[a]] = eid << 1; cursor[a] += 1
        target[cursor[b]] = a; ref[cursor[b]] = (eid << 1) | 1; cursor[b] += 1
    goff = np.zeros(m + 1, dtype='<u4')
    goff[1:] = np.cumsum([len(g) for g in geoms])
    gxy = (np.round(np.concatenate([g for g in geoms if len(g)]) * COORD_SCALE).astype('<i4').ravel()
           if gcount else np.zeros(0, dtype='<i4'))
    return b''.join([bytes(hdr), node_coords.tobytes(), first.tobytes(), target.tobytes(), ref.tobytes(),
                     np.asarray(lengths, dtype='<f4').tobytes(), goff.tobytes(), gxy.tobytes()])


def main():
    t0 = time.time()
    if not os.path.exists(SRC):
        import subprocess
        os.makedirs(os.path.dirname(SRC), exist_ok=True)
        subprocess.run(['osmium', 'tags-filter', 'data/osm/syd_box.osm.pbf', 'w/highway', '-o', SRC, '--overwrite'],
                       check=True)
    h = Ways()
    h.apply_file(SRC, locations=True, idx='flex_mem')
    print(f"walkable ways: {len(h.refs):,}  ({time.time()-t0:.0f}s)", flush=True)

    # --- split ways into edges at junctions --------------------------------
    use = {}
    for ids in h.refs:
        for k, nid in enumerate(ids):
            use[nid] = use.get(nid, 0) + (2 if k in (0, len(ids) - 1) else 1)
    junction = {nid for nid, c in use.items() if c >= 2}
    node_ix, node_xy = {}, []

    def nix(nid, xy):
        i = node_ix.get(nid)
        if i is None:
            i = node_ix[nid] = len(node_xy); node_xy.append(xy)
        return i

    ea, eb, epoly = [], [], []
    for ids, xy in zip(h.refs, h.coords):
        start = 0
        for k in range(1, len(ids)):
            if ids[k] in junction or k == len(ids) - 1:
                ea.append(nix(ids[start], xy[start])); eb.append(nix(ids[k], xy[k]))
                epoly.append(np.array(xy[start:k + 1]))
                start = k
    n = len(node_xy)
    print(f"raw graph: {n:,} nodes, {len(ea):,} edges", flush=True)

    # --- keep the largest connected component --------------------------------
    A = coo_matrix((np.ones(len(ea)), (ea, eb)), shape=(n, n))
    ncomp, lab = connected_components(A, directed=False)
    big = np.bincount(lab).argmax()
    keep_edge = lab[np.asarray(ea)] == big
    elen = np.array([seg_lengths(p).sum() for p in epoly])
    print(f"components: {ncomp:,}; largest keeps {keep_edge.mean():.1%} of edges, "
          f"{elen[keep_edge].sum()/elen.sum():.1%} of length", flush=True)

    # --- collapse degree-2 chains -------------------------------------------
    ea = np.asarray(ea)[keep_edge]; eb = np.asarray(eb)[keep_edge]
    epoly = [p for p, k in zip(epoly, keep_edge) if k]
    deg = np.bincount(ea, minlength=n) + np.bincount(eb, minlength=n)
    inc = [[] for _ in range(n)]
    for i, (a, b) in enumerate(zip(ea, eb)):
        inc[a].append(i); inc[b].append(i)
    used = np.zeros(len(ea), bool)
    chains = []                                    # (start node, end node, polyline)

    def walk(start, e):
        pts, cur = [], start
        while True:
            used[e] = True
            a, b = ea[e], eb[e]
            p = epoly[e] if a == cur else epoly[e][::-1]
            nxt = b if a == cur else a
            pts.append(p if not pts else p[1:])
            if deg[nxt] != 2 or nxt == start:
                return nxt, np.concatenate(pts)
            e2 = [x for x in inc[nxt] if not used[x]]
            if not e2:
                return nxt, np.concatenate(pts)
            cur, e = nxt, e2[0]

    for v in range(n):
        if deg[v] == 2 or deg[v] == 0:
            continue
        for e in inc[v]:
            if not used[e]:
                end, poly = walk(v, e)
                chains.append((v, end, poly))
    for e in range(len(ea)):                       # pure cycles with no junction
        if not used[e]:
            end, poly = walk(ea[e], e)
            chains.append((ea[e], end, poly))

    # --- split loops and long edges so every stretch has a node within reach --
    edges = []
    for a, b, poly in chains:
        poly = densify(poly)
        seg = seg_lengths(poly)
        total = seg.sum()
        if len(poly) > 2 and (a == b or total > MAX_EDGE_M):
            pieces = max(2 if a == b else 1, math.ceil(total / MAX_EDGE_M))
            cum = np.concatenate([[0], np.cumsum(seg)])
            cuts = [0]
            for p in range(1, pieces):
                k = int(np.searchsorted(cum, total * p / pieces))
                k = min(max(k, cuts[-1] + 1), len(poly) - 2)
                if k > cuts[-1]:
                    cuts.append(k)
            cuts.append(len(poly) - 1)
            ends = [a] + [None] * (len(cuts) - 2) + [b]
            for i in range(1, len(cuts) - 1):
                ends[i] = len(node_xy); node_xy.append(tuple(poly[cuts[i]]))
            for i in range(len(cuts) - 1):
                edges.append((ends[i], ends[i + 1], poly[cuts[i]:cuts[i + 1] + 1]))
        elif a != b:
            edges.append((a, b, poly))

    # --- renumber the surviving nodes, simplify geometry, measure ------------
    used_nodes = sorted({x for a, b, _ in edges for x in (a, b)})
    remap = {old: i for i, old in enumerate(used_nodes)}
    nodes = np.array([node_xy[o] for o in used_nodes], dtype=np.float64)
    A_ = np.array([remap[a] for a, _, _ in edges], dtype=np.int64)
    B_ = np.array([remap[b] for _, b, _ in edges], dtype=np.int64)
    lengths = np.array([seg_lengths(p).sum() for _, _, p in edges])
    lat0 = math.radians((BBOX[1] + BBOX[3]) / 2)
    kx, ky = 111320 * math.cos(lat0), 110540
    simp = shapely.simplify(to_lines([p for _, _, p in edges], kx, ky), SIMPLIFY_M)
    geoms = []
    for g in simp:
        c = shapely.get_coordinates(g)
        geoms.append(np.column_stack([c[1:-1, 0] / kx, c[1:-1, 1] / ky]) if len(c) > 2 else np.zeros((0, 2)))

    buf = encode(nodes, A_, B_, lengths, geoms)
    with gzip.open(OUT, 'wb', compresslevel=9) as f:
        f.write(buf)
    np.savez_compressed(f'{CITY_DIR}/walk/graph_check.npz', nodes=nodes, a=A_, b=B_, len=lengths)
    # how many demand points the game can snap (nearest node within 250 m)
    from scipy.spatial import cKDTree
    pts = json.load(open(f'{CITY_DIR}/demand_data.json'))['points']
    P = np.array([p['location'] for p in pts]); w = np.array([p['residents'] + p['jobs'] for p in pts], float)
    d, _ = cKDTree(nodes * (kx, ky)).query(P * (kx, ky))
    print(f"demand points within 250 m of a walk node: {(d <= 250).mean():.2%} of points, "
          f"{w[d <= 250].sum() / w.sum():.2%} of people; median snap {np.median(d):.0f} m")
    print(f"walk graph: {len(nodes):,} nodes, {len(A_):,} edges, "
          f"{sum(len(g) for g in geoms):,} geometry points, {lengths.sum()/1000:,.0f} km")
    print(f"  {len(buf)/1e6:.1f} MB raw, {os.path.getsize(OUT)/1e6:.1f} MB gzipped -> {OUT}")

    # --- pedestrian ways on the map ------------------------------------------
    if not os.path.exists(ROADS_DEPOT):
        os.replace(ROADS, ROADS_DEPOT)
    roads = json.load(open(ROADS_DEPOT))
    added = 0
    ped_lines = shapely.simplify(to_lines([np.array(h.coords[i]) for i, _, _ in h.ped], kx, ky), SIMPLIFY_M)
    for (i, layer, name), g in zip(h.ped, ped_lines):
        c = shapely.get_coordinates(g)
        coords = [[round(x / kx, 6), round(y / ky, 6)] for x, y in c]
        if len(coords) < 2:
            continue
        props = {'roadClass': 'pedestrian', 'structure': layer}
        if name:
            props['name'] = name
        roads['features'].append({'type': 'Feature', 'properties': props,
                                  'geometry': {'type': 'LineString', 'coordinates': coords}})
        added += 1
    with open(ROADS, 'w') as f:
        json.dump(roads, f, separators=(',', ':'))
    print(f"roads.geojson: +{added:,} pedestrian ways ({os.path.getsize(ROADS)/1e6:.0f} MB)")
    print(f"done in {(time.time()-t0)/60:.1f} min")


if __name__ == '__main__':
    main()
