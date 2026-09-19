"""Rebuild SYD's ocean depth index and ocean-foundation tiles from the composite
bathymetry (build_bathy_composite.py), then re-merge the map tiles.

depot's load_bathymetry_data samples its source on the same ~300 m grid it
uses for the game's depth-cell index, which would blur the Parramatta River and
Middle Harbour out of existence. This runs depot's own function with two edits:
the composite is read as-is (no resampling), and contours are drawn on its
~50 m grid, while the cell index keeps depot's 0.0027 deg size. It also stops
swimming pools and underground (tunnelled) waterways counting as water, in both
the depth index and the rendered base tiles. Everything else -- depth levels,
clipping to OSM water, gap patching, the cell index -- is depot's code unchanged.
"""
import sys, os, re, math, inspect, textwrap, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
from depot import maps as depot_maps
from depot.maps import MapGen

COMPOSITE = os.path.abspath(f'data/bathy/composite_{CITY}.nc')
A = lambda f: os.path.join(CITY_DIR, f)
NOT_WATER = {'ditch', 'swimming_pool', 'reflecting_pool'}
MIN_WATER_M2 = 500      # fountains and ornamental ponds (the CBD is full of them) aren't worth blocking track for


def tiny_water(geom, z, extent=4096):
    """An enclosed water polygon smaller than MIN_WATER_M2. Only polygons wholly
    inside the tile are judged, so a big lake clipped at a tile edge is never
    mistaken for a small one."""
    if 'Polygon' not in geom.geom_type:
        return False
    x0, y0, x1, y1 = geom.bounds
    if x0 <= 0 or y0 <= 0 or x1 >= extent or y1 >= extent:
        return False
    m_per_px = 40075016.7 * math.cos(math.radians((BBOX[1] + BBOX[3]) / 2)) / 2 ** z / extent
    return geom.area * m_per_px ** 2 < MIN_WATER_M2

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
# 3. build depth bands with their holes, from a lightly smoothed grid. depot builds
#    each band from outer rings only (holes filled) and then pads every band by
#    ~10 m and clips it against the shallower ones: harmless on GEBCO's smooth
#    grid, but on survey data it left overlapping slivers that render as dark
#    streaks and odd cut-outs (seen in-game 2026-09-17). contourpy's OuterOffset
#    output gives disjoint bands that meet exactly, so no padding or clipping.
src = swap(src, "# Generate contours", "contours_by_level.reverse()",
"""# Generate contours
        if self.verb:
            print("  Generating hole-aware depth bands")
        from contourpy import contour_generator, FillType
        from scipy.ndimage import gaussian_filter
        smooth = gaussian_filter(np.asarray(dense_depths, dtype=np.float64), sigma=SMOOTH_SIGMA)
        gen = contour_generator(dense_lons, dense_lats, smooth, fill_type=FillType.OuterOffset)
        levels = sorted(float(v) for v in DEPTH_LEVELS)
        contours_by_level = []
        for i in range(len(levels) - 1):
            lo, hi = levels[i], levels[i + 1]
            if lo >= 0:
                continue
            band_polys = []
            for pts, offs in zip(*gen.filled(lo, hi)):
                rings = [pts[offs[k]:offs[k + 1]] for k in range(len(offs) - 1)]
                rings = [r for r in rings if len(r) >= 4]
                if not rings:
                    continue
                poly = Polygon(rings[0], rings[1:])
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if not poly.is_empty and poly.area > 1e-9:
                    band_polys.append(poly)
            if band_polys:
                contours_by_level.append((lo, unary_union(band_polys)))
        # deepest -> shallowest, as the rest of depot's function expects
        contours_by_level.sort(key=lambda x: x[0])""")

# 4. pools and underground waterways are not water. depot takes every feature of
#    the OpenMapTiles water/waterway layers except ditches, so backyard swimming
#    pools and culverted drains (the Tank Stream under Pitt Street) became water
#    that blocked construction (seen in-game 2026-09-18). Enclosed water under
#    MIN_WATER_M2 (fountains, garden ponds) goes too. Same filter for the
#    rendered tiles below.
src = re.sub(r"if feature_kind == 'ditch':\n(\s*)continue",
             lambda m: "if feature_kind in NOT_WATER or props.get('brunnel') == 'tunnel':\n" + m.group(1) + "continue",
             src, count=1)
src = re.sub(r"\n(\s*)geom_shape = shape\(raw_geom\)\n",
             lambda m: m.group(0) + m.group(1) + "if tiny_water(geom_shape, self.maxzoom, extent):\n"
                       + m.group(1) + "    continue\n", src, count=1)
assert "NOT_WATER" in src and "tiny_water" in src, "water filter not applied"

ns = dict(vars(depot_maps))
ns['SMOOTH_SIGMA'] = 1.5          # grid cells (~75 m)
ns['NOT_WATER'] = NOT_WATER
ns['tiny_water'] = tiny_water
exec(src, ns)
MapGen.load_bathymetry_data = ns['load_bathymetry_data']

wsrc = textwrap.dedent(inspect.getsource(MapGen._process_tile_worker))
wsrc = re.sub(r"\n(\s*)old_props = feature.get\('properties', \{\}\)\n",
              lambda m: m.group(0) + m.group(1) + "if old_props.get('class') in NOT_WATER or (layer_name == 'waterway' "
                        "and old_props.get('brunnel') == 'tunnel'):\n" + m.group(1) + "    continue\n",
              wsrc, count=1)
wsrc = re.sub(r"\n(\s*)geom = shape\(feature\['geometry'\]\)\n",
              lambda m: m.group(0) + m.group(1) + "if tiny_water(geom, z):\n" + m.group(1) + "    continue\n",
              wsrc, count=1)
assert "NOT_WATER" in wsrc and "tiny_water" in wsrc, "tile water filter not applied"
exec(wsrc, ns)
MapGen._process_tile_worker = ns['_process_tile_worker']

obj = MapGen(city=CITY, bbox=BBOX, osmpbf='data/osm/new_south_wales-latest.osm.pbf', outputdir='build',
             maxzoom=15, ncores=20, RAM=13, cleanup_files=False, reprocess_bathymetry_data=True,
             cities=['city', 'town'], suburbs=['suburb', 'village'],
             neighborhoods=['quarter', 'neighbourhood', 'hamlet'], verb=True)
obj.raw_mbtiles = A(f'{CITY.lower()}.mbtiles')

def sh(cmd):
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)

t0 = time.time()
if '--tiles-only' not in sys.argv:        # --tiles-only: depth index already built, redo the map tiles
    for f in ('ocean_depth_index.json.gz', 'ocean_depth_index_contours.json.gz',
              'ocean_foundations.geojson', 'ocean_foundations.mbtiles'):
        if os.path.exists(A(f)):
            os.replace(A(f), A(f + '.prev'))
    obj.load_bathymetry_data(opendap_url=COMPOSITE)
    print(f"depth index built in {(time.time()-t0)/60:.1f} min", flush=True)
    obj._generate_ocean_depth_tiles()

# rebuild the base tiles with the water filter (generate_pmtiles step 3), then
# re-merge exactly as steps 5-6, reusing the building tiles
lc = CITY.lower()
obj.fix_mbtiles()
obj._update_mbtiles_metadata(A(f'{lc}-fixed.mbtiles'))
merged = A(f'{lc}-merged.mbtiles')
sh(['tile-join', '--force', '-o', merged, A(f'{lc}-fixed.mbtiles'), A('buildings.mbtiles'),
    A('ocean_foundations.mbtiles'), '--no-tile-size-limit'])
obj._update_mbtiles_metadata(merged)
sh(['pmtiles', 'convert', merged, A(f'{CITY}-nolabels.pmtiles')])
obj.add_labels()
print(f"=== bathymetry + tiles rebuilt in {(time.time()-t0)/60:.1f} min ===")
