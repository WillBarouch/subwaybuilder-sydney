"""Drop special-demand schema references to pops that consolidation removed.

depot's create_description walks pop_ids from the points schema and raises
KeyError if any have been merged away, which happens whenever consolidate_pops
or a point removal runs after the schema was written.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY_DIR

P = os.path.join(CITY_DIR, '.railyard_map', 'special_demand_points.json')
sch = json.load(open(P))
live = {p['id'] for p in json.load(open(os.path.join(CITY_DIR, 'demand_data.json')))['pops']}
before = sum(len(p['pop_ids']) for p in sch['points'])
for p in sch['points']:
    p['pop_ids'] = [i for i in p['pop_ids'] if i in live]
sch['points'] = [p for p in sch['points'] if p['pop_ids']]
json.dump(sch, open(P, 'w'), indent=1)
print(f"pruned {before - sum(len(p['pop_ids']) for p in sch['points'])} stale pop refs; "
      f"{len(sch['points'])} special points remain")
