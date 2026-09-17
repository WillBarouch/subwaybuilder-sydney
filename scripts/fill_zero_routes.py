"""Backfill pops that OSRM returned a zero-duration route for.

These are commutes whose origin and destination resolved to the same demand
point. depot treats drivingSeconds<=0 as "not yet routed", so they must be
given a nonzero value or every downstream check thinks routing never ran.
Straight-line distance at depot's own 30 km/h fallback speed, floored at 1.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY_DIR

F = os.path.join(CITY_DIR, 'demand_data.json')
d = json.load(open(F))
loc = {p['id']: p['location'] for p in d['points']}
bad = [x for x in d['pops'] if not x.get('drivingSeconds')]
print(f"  pops with no route: {len(bad):,} of {len(d['pops']):,}")
R = 6371.0
for x in bad:
    (lo1, la1), (lo2, la2) = loc[x['residenceId']], loc[x['jobId']]
    a1, b1, a2, b2 = map(math.radians, (lo1, la1, lo2, la2))
    h = math.sin((b2-b1)/2)**2 + math.cos(b1)*math.cos(b2)*math.sin((a2-a1)/2)**2
    dist = 2*R*math.asin(math.sqrt(h))*1000
    x['drivingDistance'] = max(1, int(dist))
    x['drivingSeconds'] = max(1, int(dist/1000/30*3600))
json.dump(d, open(F, 'w'), separators=(',', ':'))
left = sum(1 for x in d['pops'] if not x.get('drivingSeconds'))
print(f"  filled; remaining unrouted: {left}")
