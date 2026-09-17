"""End-to-end, resumable map build for whichever city mapconfig names.

Improves on the ad-hoc LDN sequence in two ways:
  * Overture footprints are fetched, then station structures stripped, and only
    then handed to process_buildings -- so buildings are processed once rather
    than twice.
  * The Thames bathymetry override is built early (it needs only the OSM
    extract) and injected by wrapping load_bathymetry_data, so generate_pmtiles
    runs once instead of twice.

Every stage checks for its own artifact and skips if present, so re-running
after an interruption resumes rather than restarts.
"""
import os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
from depot.maps import MapGen

lc = CITY.lower()
A = lambda f: os.path.join(CITY_DIR, f)

obj = MapGen(
    city=CITY, bbox=BBOX,
    osmpbf='data/osm/new_south_wales-latest.osm.pbf',
    outputdir='build',
    building_index_filter_size=100,
    building_tile_filter_size=50,
    building_index_simplification=4,
    building_tile_simplification=1,
    max_building_tile_size=450,
    maxzoom=15, ncores=20, RAM=13,
    cleanup_files=False,
    reprocess_bathymetry_data=False,
    cities=['city', 'town'],
    suburbs=['suburb', 'village'],
    neighborhoods=['quarter', 'neighbourhood', 'hamlet'],
    verb=True,
)

def stage(name, artifact, fn):
    if os.path.exists(artifact):
        print(f"\n=== SKIP {name} ({os.path.basename(artifact)} present) ===", flush=True)
        return
    print(f"\n=== {name} ===", flush=True)
    t0 = time.time()
    fn()
    print(f"=== {name} done in {(time.time()-t0)/60:.1f} min ===", flush=True)

def sh(cmd):
    subprocess.run(cmd, shell=True, check=True)

# 1 -- OSM extract for the bbox
stage('extract_base_data', A(f'{lc}.osm.pbf'), obj.extract_base_data)

# 4 -- Overture footprints
stage('fetch Overture buildings (local, with retries)', A('buildings.pkl'),
      lambda: sh("python -u scripts/fetch_overture_buildings.py"))
stage('Overture buildings -> geojson', A('buildings.geojson'),
      obj._fetch_overture_buildings)

# 5 -- drop railway station structures before any expensive geometry work
stage('strip station buildings', A('buildings.with_stations.geojson'),
      lambda: sh("python scripts/strip_station_buildings.py"))

# 6 -- collision index
obj.buildings_geojson = A('buildings.geojson')
stage('process_buildings', A('buildings_index.bin.gz'), obj.process_buildings)

# 7 -- roads / aeroways
stage('process_roads_and_aeroways', A('roads.geojson'),
      obj.process_roads_and_aeroways)

# 8 -- tiles (depot's default bathymetry handling)
stage('generate_pmtiles', A(f'{CITY}-nolabels.pmtiles'), obj.generate_pmtiles)

# 9 -- labels
stage('add_labels', A(f'{CITY}.pmtiles'), obj.add_labels)

print(f"\n=== {CITY} MAP COMPLETE ===", flush=True)
for f in [f'{CITY}.pmtiles', 'buildings_index.bin.gz', 'roads.geojson',
          'runways_taxiways.geojson']:
    p = A(f)
    print(f"  {f:<28}{os.path.getsize(p)/1e6:>9.1f} MB" if os.path.exists(p)
          else f"  {f:<28}   MISSING")
