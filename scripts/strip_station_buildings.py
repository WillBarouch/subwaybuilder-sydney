"""Remove railway-station structures from the Overture building footprints.

Station trainsheds and platform canopies are mapped as buildings in Overture
(Waterloo, St Pancras, Paddington and the rest all appear as class
'train_station'). Leaving them in makes them solid obstacles, so you cannot
place a station where a station already is -- which is precisely where you want
one. depot's Overture query keeps only id/geometry/name/height and discards
subtype/class, so the class has to be re-queried and subtracted by id.

Parking structures (545) and hangars (206) are deliberately kept: those are
real buildings that should still block construction.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR, OA_CENTROIDS, SPECIAL_DIR
import json, os, shutil, sys
import duckdb
sys.path.insert(0, 'depot/src')
from depot.maps import MapGen

BBOX = _BBOX
SRC = f'{CITY_DIR}/buildings.geojson'
BACKUP = f'{CITY_DIR}/buildings.with_stations.geojson'
# Only train stations. Overture's generic 'transportation' class looked safe on
# the London build (88 buildings, mostly station-like), but in German data it is
# ~57,000 garages -- median 48 m2, the Garagenhöfe behind every housing block --
# which are real structures and must stay solid.
DROP_CLASSES = ('train_station',)

# read classes from the local Overture copy (fetch_overture_buildings.py)
con = duckdb.connect()
cls = ",".join(f"'{c}'" for c in DROP_CLASSES)
rows = con.execute(f"""
    SELECT id FROM 'data/overture/bldg_{CITY}.parquet'
    WHERE subtype = 'transportation' AND class IN ({cls})""").fetchall()
rel = 'local copy'
drop = {r[0] for r in rows}
print(f"Overture release {rel}: {len(drop):,} station buildings to remove")

if not os.path.exists(BACKUP):
    shutil.copy(SRC, BACKUP)
    print(f"backed up original footprints -> {BACKUP}")

kept = removed = 0
tmp = SRC + '.tmp'
with open(BACKUP) as fin, open(tmp, 'w') as fout:
    for line in fin:
        s = line.strip()
        if s.startswith('{"type":"Feature"'):
            core = s.rstrip(',')
            try:
                fid = json.loads(core)['properties'].get('id')
            except Exception:
                fid = None
            if fid in drop:
                removed += 1
                continue
            kept += 1
        fout.write(line)
os.replace(tmp, SRC)
print(f"features kept {kept:,}   removed {removed:,}")
