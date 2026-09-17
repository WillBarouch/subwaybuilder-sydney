"""Overture buildings for the box, fetched once with retries.

depot's own fetch runs one long DuckDB httpfs scan; on the SYD build DuckDB
1.5.3 aborted mid-read ("Information loss on integer cast") twice in a row.
This downloads with Overture's own client instead, keeps everything needed --
the columns depot uses plus subtype/class/num_floors for job placement -- in a
local parquet, then writes the buildings.pkl cache that depot's
_fetch_overture_buildings loads instead of querying S3 itself.
"""
import sys, os, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
import duckdb
from shapely import wkb
from depot.maps import MapGen

OUT = f'data/overture/bldg_{CITY}.parquet'
PKL = f'{CITY_DIR}/buildings.pkl'
os.makedirs(os.path.dirname(OUT), exist_ok=True)
os.makedirs(CITY_DIR, exist_ok=True)

RAW = f'data/overture/bldg_{CITY}_raw.parquet'
if not os.path.exists(OUT):
    # DuckDB 1.5.3's httpfs aborts reading these files ("Information loss on
    # integer cast", twice in a row), so download with Overture's own client
    # (pyarrow S3 + STAC file pruning) and filter locally.
    for attempt in range(1, 4):
        if os.path.exists(RAW):
            break
        t0 = time.time()
        r = subprocess.run(['overturemaps', 'download', '--bbox', ','.join(map(str, BBOX)),
                            '-f', 'geoparquet', '-t', 'building', '-o', RAW + '.part',
                            '--request_timeout', '300'])
        if r.returncode == 0:
            os.replace(RAW + '.part', RAW)
            print(f"downloaded in {(time.time()-t0)/60:.1f} min (attempt {attempt})", flush=True)
        else:
            print(f"attempt {attempt} failed (exit {r.returncode})", flush=True)
            time.sleep(30 * attempt)
    if not os.path.exists(RAW):
        sys.exit("Overture download failed 3 times")
    con = duckdb.connect()
    # same containment test depot applies to its own query
    con.execute(f"""
    COPY (
      SELECT id, geometry, names.primary AS name, height, num_floors, subtype, class
      FROM read_parquet('{RAW}')
      WHERE bbox.xmin >= {BBOX[0]} AND bbox.xmax <= {BBOX[2]}
        AND bbox.ymin >= {BBOX[1]} AND bbox.ymax <= {BBOX[3]}
    ) TO '{OUT}' (FORMAT PARQUET)""")
    con.close()

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
print(con.execute(f"SELECT count(*) FROM '{OUT}'").fetchone()[0], "buildings", flush=True)
if not os.path.exists(PKL):
    df = con.execute(f"SELECT id, ST_AsWKB(geometry) AS geometry, name, height FROM '{OUT}'").df()
    df['geometry'] = df['geometry'].apply(lambda b: wkb.loads(bytes(b)))
    df.to_pickle(PKL)
    print(f"wrote {PKL}  ({len(df):,} rows)")
