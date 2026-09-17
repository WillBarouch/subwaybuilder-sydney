"""Composite bathymetry for SYD on a ~50 m grid, replacing depot's GEBCO-only depths.

Sources, highest priority first (all elevations relative to AHD / mean sea level):
  1. NSW DCCEEW "NSW bathymetry sourced from multibeam and marine lidar surveys"
     (5 m statewide mosaic; its 20 m overview is used), CC BY
  2. Wilson & Power (2018), seamless 10 m bathymetry for Sydney Harbour (incl.
     Parramatta and Lane Cove rivers, Middle Harbour) and Botany (Georges River,
     Port Hacking, Bate Bay), PANGAEA 885014 / 885012, CC BY 4.0. Only cells
     below 0 m are used, so their land topography never leaks in.
  3. Wilson & Power (2018), Hawkesbury River incl. Broken Bay and Brisbane Water,
     50 m, PANGAEA 885013
  4. GEBCO 2026 (what depot uses by default) everywhere else

Each source is resampled onto the target grid by averaging. The result is written
as data/bathy/composite_SYD.nc with an `elevation` variable on ascending lon/lat,
the shape depot's bathymetry loader expects, plus a per-cell source map.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX
import numpy as np, xarray as xr, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin

OUT = f'data/bathy/composite_{CITY}.nc'
BUF = 0.05
DLAT = 0.00045                                   # ~50 m
DLON = DLAT / np.cos(np.radians((BBOX[1] + BBOX[3]) / 2))
W, S, E, N = BBOX[0] - BUF, BBOX[1] - BUF, BBOX[2] + BUF, BBOX[3] + BUF
nx = int(np.ceil((E - W) / DLON)); ny = int(np.ceil((N - S) / DLAT))
dst_transform = from_origin(W, S + ny * DLAT, DLON, DLAT)       # north-up
print(f"target grid {nx} x {ny} ({DLON*111320*np.cos(np.radians(-34)):.0f} x {DLAT*110574:.0f} m)")

def warp(src_path, overview=None, resampling=Resampling.average, keep=lambda a: np.isfinite(a)):
    dst = np.full((ny, nx), np.nan, dtype=np.float32)
    opts = {'OVERVIEW_LEVEL': str(overview)} if overview is not None else {}
    with rasterio.open(src_path, **opts) as src:
        nod = src.nodata
        crs = src.crs or 'EPSG:4326'          # W&P .prj files differ in case from the grids
        # read only the part of the source that covers the target box
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds
        l, b, r, t = transform_bounds('EPSG:4326', crs, W, S, E, N, densify_pts=21)
        win = from_bounds(l, b, r, t, src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(1, window=win, masked=False).astype(np.float32)
        if nod is not None:
            arr[arr == nod] = np.nan
        arr[arr < -1e30] = np.nan
        arr[~keep(arr)] = np.nan
        reproject(arr, dst, src_transform=src.window_transform(win), src_crs=crs,
                  src_nodata=np.nan, dst_transform=dst_transform, dst_crs='EPSG:4326',
                  dst_nodata=np.nan, resampling=resampling)
        print(f"  {os.path.basename(src_path)[:60]}: read {arr.shape[1]}x{arr.shape[0]}, "
              f"{np.isfinite(dst).sum():,} target cells")
    return dst

# 4. GEBCO base (depot's own OPeNDAP source)
print("GEBCO 2026 ...")
g = xr.open_dataset("https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026/"
                    "sub_ice_topography_bathymetry/netcdf/GEBCO_2026_sub_ice.nc")
g = g.elevation.sel(lon=slice(W - 0.02, E + 0.02), lat=slice(S - 0.02, N + 0.02)).load()
lons = W + (np.arange(nx) + 0.5) * DLON
lats_desc = S + ny * DLAT - (np.arange(ny) + 0.5) * DLAT
base = g.interp(lon=lons, lat=lats_desc, method='linear').values.astype(np.float32)
comp = base.copy(); source = np.full((ny, nx), 4, dtype=np.uint8)

layers = []
M = 'data/bathy/nsw_mosaic.zip'
layers.append((1, warp(f'/vsizip/{M}/BathymetryMosaic_MarineLidar_MBES/ml_mb_dem0', overview=1)))
for name, member in [('Sydney', 'Sydney/syd_0.0001_gcs.txt'), ('Botany', 'Botany/botany_0.0001_gcs.txt')]:
    layers.append((2, warp(f'/vsizip/data/bathy/{name}.zip/{member}', keep=lambda a: np.isfinite(a) & (a < 0))))
layers.append((3, warp('/vsizip/data/bathy/hawkesbury_revised.zip/hawkesbury_revised/hawkesbury_0.0005_gcs.txt',
                       keep=lambda a: np.isfinite(a) & (a < 0))))

# apply lowest priority first so higher ones overwrite
for prio, arr in sorted(layers, key=lambda x: -x[0]):
    m = np.isfinite(arr)
    comp[m] = arr[m]; source[m] = prio

comp = np.nan_to_num(comp, nan=0.0)
ds = xr.Dataset({'elevation': (('lat', 'lon'), comp[::-1]), 'source': (('lat', 'lon'), source[::-1])},
                coords={'lon': lons, 'lat': lats_desc[::-1]})
ds.attrs['sources'] = ("1 NSW multibeam+marine lidar mosaic (DCCEEW); 2 Wilson & Power 2018 Sydney/Botany 10 m; "
                       "3 Wilson & Power 2018 Hawkesbury 50 m; 4 GEBCO 2026")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
ds.to_netcdf(OUT)
wet = comp < 0
for k, lab in [(1, 'NSW mosaic'), (2, 'W&P 10 m'), (3, 'W&P Hawkesbury'), (4, 'GEBCO')]:
    print(f"  source {lab:15s} {(wet & (source == k)).sum():>9,} wet cells")
print(f"wrote {OUT}  min {comp.min():.1f} m")
