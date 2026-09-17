"""Fill drivingSeconds / drivingDistance / drivingPath from the local OSRM server.

This produces exactly what depot's DemandData.calculate_routes(routing_method='osrm')
produces -- same OSRM server, same /nearest snapping, same /route call, same shapely
simplification of the geometry -- but it is usable at this map's size:

  * depot re-snaps the destination point via /nearest once per *pop*; here every
    point is snapped once up front (23k requests instead of ~394k),
  * depot rescans the whole pops list for each point, which is O(points x pops)
    and alone runs into billions of comparisons on a map this size,
  * requests are issued from a thread pool rather than one at a time.

Run with --sample N to route a random N pops and report the projected file size
before committing to the full pass.
"""
import sys as _sys, os as _os
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR
import argparse, json, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor

import requests
from shapely.geometry import LineString

ap = argparse.ArgumentParser()
ap.add_argument('--demand', default=f'{CITY_DIR}/demand_data.json')
ap.add_argument('--out', default=None)
ap.add_argument('--port', type=int, default=5000)
ap.add_argument('--workers', type=int, default=16)
ap.add_argument('--simplify-tol', type=float, default=0.0002)
ap.add_argument('--no-paths', action='store_true')
ap.add_argument('--sample', type=int, default=0)
ap.add_argument('--coord-dp', type=int, default=5,
                help='decimal places for drivingPath coords; 5 dp is ~1 m')
a = ap.parse_args()

BASE = f"http://127.0.0.1:{a.port}"
d = json.load(open(a.demand))
points, pops = d['points'], d['pops']
print(f"points {len(points):,}  pops {len(pops):,}")

sess = [requests.Session() for _ in range(a.workers)]

# ---------------------------------------------------- snap every point once
def snap(i):
    p = points[i]
    s = sess[i % a.workers]
    try:
        r = s.get(f"{BASE}/nearest/v1/driving/{p['location'][0]},{p['location'][1]}",
                  timeout=30)
        if r.status_code == 200:
            return i, r.json()["waypoints"][0]["location"]
    except Exception:
        pass
    return i, None

t0 = time.time()
snapped = {}
with ThreadPoolExecutor(a.workers) as ex:
    for n, (i, loc) in enumerate(ex.map(snap, range(len(points))), 1):
        snapped[points[i]['id']] = loc
        if n % 5000 == 0:
            print(f"  snapped {n:,}/{len(points):,}", flush=True)
missing = sum(1 for v in snapped.values() if v is None)
print(f"snapped {len(points):,} points in {time.time()-t0:.0f}s ({missing} unsnappable)")

# --------------------------------------------------------------- route pops
targets = pops if not a.sample else random.Random(0).sample(pops, min(a.sample, len(pops)))
print(f"routing {len(targets):,} pops with {a.workers} workers")

KM, R = 1000.0, 6371.0
def haversine_kmh(lo1, la1, lo2, la2, kph=30):
    from math import radians, sin, cos, asin, sqrt
    lo1, la1, lo2, la2 = map(radians, (lo1, la1, lo2, la2))
    h = sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2
    dist = 2*R*asin(sqrt(h))*KM
    return dist, dist/KM/kph*3600

counts = {'ok': 0, 'noroute': 0, 'fail': 0}
def route(args):
    k, p = args
    s = sess[k % a.workers]
    h, j = snapped.get(p['residenceId']), snapped.get(p['jobId'])
    if h is None or j is None:
        counts['fail'] += 1
        return p, None
    try:
        r = s.get(f"{BASE}/route/v1/driving/{h[0]},{h[1]};{j[0]},{j[1]}"
                  f"?overview={'false' if a.no_paths else 'full'}&geometries=geojson",
                  timeout=30)
        resp = r.json()
    except Exception:
        counts['fail'] += 1
        return p, None
    if r.status_code != 200 or resp.get('code') != 'Ok' or not resp.get('routes'):
        dist, dur = haversine_kmh(h[0], h[1], j[0], j[1])
        counts['noroute'] += 1
        return p, (int(dur), int(dist), None)
    rt = resp['routes'][0]
    path = None
    if not a.no_paths:
        try:
            line = LineString(rt['geometry']['coordinates'])
            dp = a.coord_dp
            path = [[round(x, dp), round(y, dp)] for x, y in
                    line.simplify(tolerance=a.simplify_tol, preserve_topology=True).coords]
        except Exception:
            path = None
    counts['ok'] += 1
    return p, (int(rt['duration']), int(rt['distance']), path)

t0 = time.time()
done = 0
with ThreadPoolExecutor(a.workers) as ex:
    for p, res in ex.map(route, enumerate(targets), chunksize=64):
        done += 1
        if res:
            p['drivingSeconds'], p['drivingDistance'] = res[0], res[1]
            if res[2]:
                p['drivingPath'] = res[2]
        if done % 25000 == 0:
            el = time.time() - t0
            print(f"  {done:,}/{len(targets):,}  {done/el:.0f} pops/s  "
                  f"eta {(len(targets)-done)/max(done/el,1)/60:.1f} min", flush=True)
el = time.time() - t0
print(f"routed {done:,} in {el:.0f}s ({done/max(el,1):.0f}/s)  {counts}")

if a.sample:
    n = len(targets)
    per = len(json.dumps(targets, separators=(',', ':'))) / n
    print(f"\nmean bytes/pop with these settings: {per:.0f}")
    print(f"projected pops payload for {len(pops):,} pops: "
          f"{per*len(pops)/1e6:.0f} MB")
    routed = [p for p in targets if p.get('drivingSeconds')]
    if routed:
        import statistics as st
        print(f"median commute {st.median(p['drivingDistance'] for p in routed)/1000:.1f} km, "
              f"{st.median(p['drivingSeconds'] for p in routed)/60:.1f} min")
else:
    out = a.out or a.demand
    with open(out, 'w') as f:
        json.dump(d, f, separators=(',', ':'))
    print(f"wrote {out} ({os.path.getsize(out)/1e6:.1f} MB)")
