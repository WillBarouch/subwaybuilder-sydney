"""Package the finished map into the ZIP layout Railyard expects.

Per the publishing guide the archive must contain these six files, named for
the city code, plus the optional extras listed in OPTIONAL below:

    LDN.zip/
      LDN.pmtiles
      buildings_index.bin.gz
      config.json
      demand_data.json
      roads.geojson
      runways_taxiways.geojson

manifest.json is NOT bundled -- it goes up as its own release asset beside the
ZIP, so Railyard can check compatibility without downloading the archive.
Uploading it is not optional: a release published without one fails the
registry's game_version_valid integrity check and is dropped from downloads.
"""
import sys as _sys, os as _os
_sys.path.insert(0,_os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR
import argparse, json, os, zipfile

ap = argparse.ArgumentParser()
ap.add_argument('--src', default=CITY_DIR)
ap.add_argument('--out', default='deliverables')
ap.add_argument('--code', default=CITY)
ap.add_argument('--game-range', default='>=1.5.0',
                help='semver range for the subway-builder dependency')
ap.add_argument('--map-id', default='sydney', help='registry listing id')
a = ap.parse_args()

# buildings_index: the publishing guide still lists the .json, but every map
# published recently (ile-de-france, tokyo, beijing, shanghai, guangzhou, praha)
# ships buildings_index.bin.gz -- the format Subway Builder has used since
# 1.3.0. It is also 3.5x smaller than the JSON.
REQUIRED = [f"{a.code}.pmtiles", "buildings_index.bin.gz", "config.json",
            "demand_data.json", "roads.geojson", "runways_taxiways.geojson"]

# Optional files Railyard recognises (railyard/internal/files/map_validation.go):
# the ocean depth index (game water-depth costs) and building foundation tiles,
# plus the root-level .railyard_map helper folder (special demand schema).
OPTIONAL = ["ocean_depth_index.json.gz", "walk_graph.bin.gz", f"{a.code}_foundations.pmtiles",
            ".railyard_map/special_demand_points.json", ".railyard_map/special_demand_types.json"]

os.makedirs(a.out, exist_ok=True)
missing = [f for f in REQUIRED if not os.path.exists(os.path.join(a.src, f))]
if missing:
    raise SystemExit(f"cannot package, missing: {missing}")

cfg = json.load(open(os.path.join(a.src, "config.json")))
manifest = {"id": a.map_id, "name": cfg["name"], "version": cfg["version"],
            "dependencies": {"subway-builder": a.game_range}}
mpath = os.path.join(a.out, "manifest.json")
json.dump(manifest, open(mpath, "w"), indent=2)

zpath = os.path.join(a.out, f"{a.code}.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in REQUIRED + [f for f in OPTIONAL if os.path.exists(os.path.join(a.src, f))]:
        src = os.path.join(a.src, f)
        z.write(src, arcname=f)          # flat, apart from the root-level .railyard_map folder
        print(f"  + {f:<44} {os.path.getsize(src)/1e6:>9.1f} MB")
    for f in OPTIONAL:
        if not os.path.exists(os.path.join(a.src, f)):
            print(f"  - {f:<44} (not built, skipped)")

print(f"\n{zpath}   {os.path.getsize(zpath)/1e6:.1f} MB")
print(f"{mpath}  {json.dumps(manifest)}")
