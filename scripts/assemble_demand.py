"""Apply every special-demand layer on top of the census base matrix."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR, OA_CENTROIDS, SPECIAL_DIR
import json, os, shutil, time
from depot.demand import DemandData
from calibrate_special_exponents import assign_homes

BBOX = _BBOX
BASE = f'{CITY_DIR}/demand_data.json'
WORK = f'{CITY_DIR}/demand_data.json'

# add the big sites first so they absorb nearby base points before the
# thousands of small school points are laid down
LAYERS = ['airports', 'universities', 'entertainment', 'schools']

if not os.path.exists(f'{CITY_DIR}/demand_data.base.json'):
    shutil.copy(BASE, f'{CITY_DIR}/demand_data.base.json')
    print(f"kept a copy of the pre-special base at {CITY_DIR}/demand_data.base.json")

ldn = DemandData(f'{CITY_DIR}/demand_data.base.json', CITY, bbox=BBOX,
                 outputdir=CITY_DIR, verb=False)
print(f"base: {len(ldn['points']):,} points  {len(ldn['pops']):,} pops")
import pandas as pd
home_w = pd.read_parquet(f'data/home_weights_{CITY}.parquet').set_index('pid')

for layer in LAYERS:
    pois = json.load(open(f'{SPECIAL_DIR}/{layer}.json'))
    for p in pois:
        for k in [k for k in p if k.startswith('_')]:
            del p[k]
    if any(p.get('home_group') for p in pois):
        assign_homes(pois, ldn['points'], home_w)
        for p in pois:
            p.pop('home_group', None)
    t0 = time.time()
    ldn.add_points(pois)
    print(f"  + {layer:<14} {len(pois):>6,} points  ->  "
          f"{len(ldn['points']):>7,} points  {len(ldn['pops']):>8,} pops"
          f"   [{time.time()-t0:.0f}s]", flush=True)

ldn.save(WORK)
print(f"\nsaved {WORK}  ({os.path.getsize(WORK)/1e6:.1f} MB)")
print()
ldn.print_stats()
