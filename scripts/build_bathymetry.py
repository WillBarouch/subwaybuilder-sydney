"""Rebuild SYD's ocean depth index and ocean-foundation tiles from the composite
bathymetry (build_bathy_composite.py), then re-merge the map tiles.

depot's load_bathymetry_data samples its source on the same ~300 m grid it
uses for the game's depth-cell index, which would blur the Parramatta River and
Middle Harbour out of existence. This runs depot's own function with two edits:
the composite is read as-is (no resampling), and contours are drawn on its
~50 m grid, while the cell index keeps depot's 0.0027 deg size. Everything else
-- depth levels, clipping to OSM water, gap patching, the cell index -- is
depot's code unchanged.
"""
import sys, os, inspect, textwrap, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
from depot import maps as depot_maps
from depot.maps import MapGen

COMPOSITE = os.path.abspath(f'data/bathy/composite_{CITY}.nc')
A = lambda f: os.path.join(CITY_DIR, f)

src = textwrap.dedent(inspect.getsource(MapGen.load_bathymetry_data))

def swap(text, start, end, new):
    i = text.index(start); j = text.index(end, i) + len(end)
    return text[:i] + new + text[j:]

# 1. read the composite directly instead of GEBCO + resampling to CELL_SIZE
src = swap(src, "self.bathy = xr.open_dataset(opendap_url)", "depths = self.bathy.values",
"""self.bathy = xr.open_dataset(opendap_url).elevation.load()
    min_lon, min_lat, max_lon, max_lat = self.bbox
    # cell index grid stays at CELL_SIZE (game lookup); contours use the composite grid
    step_x = CELL_SIZE / float(np.cos(np.radians((min_lat + max_lat) / 2.)))
    step_y = CELL_SIZE
    grid_x = np.arange(min_lon, max_lon+step_x, step_x)
    grid_y = np.arange(min_lat, max_lat+step_y, step_y)
    lons = self.bathy.lon.values
    lats = self.bathy.lat.values
    depths = self.bathy.values""")
# 2. contour on the composite grid itself (it is already fine enough)
src = swap(src, "# Increase the resolution multiplier for smoother curves",
           "dense_depths = interp_func(interp_points).reshape(dense_mesh_lon.shape)",
"""dense_lons, dense_lats, dense_depths = lons, lats, depths""")
assert "interp(" not in src.split("def load_bathymetry_data")[1].split("contourf")[0], "resampling not removed"

ns = dict(vars(depot_maps))
exec(src, ns)
MapGen.load_bathymetry_data = ns['load_bathymetry_data']

obj = MapGen(city=CITY, bbox=BBOX, osmpbf='data/osm/new_south_wales-latest.osm.pbf', outputdir='build',
             maxzoom=15, ncores=20, RAM=13, cleanup_files=False, reprocess_bathymetry_data=True,
             cities=['city', 'town'], suburbs=['suburb', 'village'],
             neighborhoods=['quarter', 'neighbourhood', 'hamlet'], verb=True)
obj.raw_mbtiles = A(f'{CITY.lower()}.mbtiles')

def sh(cmd):
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)

t0 = time.time()
for f in ('ocean_depth_index.json.gz', 'ocean_depth_index_contours.json.gz',
          'ocean_foundations.geojson', 'ocean_foundations.mbtiles'):
    if os.path.exists(A(f)):
        os.replace(A(f), A(f + '.gebco'))
obj.load_bathymetry_data(opendap_url=COMPOSITE)
print(f"depth index built in {(time.time()-t0)/60:.1f} min", flush=True)
obj._generate_ocean_depth_tiles()

# re-merge exactly as generate_pmtiles step 5-6, reusing the fixed base and building tiles
lc = CITY.lower()
merged = A(f'{lc}-merged.mbtiles')
sh(['tile-join', '--force', '-o', merged, A(f'{lc}-fixed.mbtiles'), A('buildings.mbtiles'),
    A('ocean_foundations.mbtiles'), '--no-tile-size-limit'])
obj._update_mbtiles_metadata(merged)
sh(['pmtiles', 'convert', merged, A(f'{CITY}-nolabels.pmtiles')])
obj.add_labels()
print(f"=== bathymetry + tiles rebuilt in {(time.time()-t0)/60:.1f} min ===")
