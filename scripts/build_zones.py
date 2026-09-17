"""Demand points for SYD: one per 2021 SA1, placed at mesh-block precision.

Inputs
  * ABS ASGS 2021 mesh blocks (geometry, SA1/SA2/SA3/SA4 codes, category)
  * TfNSW Travel Zone Projections 2024 (TZP24) by TZ21: population, employed
    residents (workforce) and jobs for 2021 and 2026
  * TfNSW TZ21 -> MB21 concordance: each travel zone's population and
    employment shares by mesh block (TfNSW's own apportionment)
  * TfNSW TZ11 polygons, to link every mesh block to its 2011 travel zone

Every mesh block gets 2026 employed residents and jobs; SA1s aggregate them.
A SA1's home point is the mesh block nearest the worker-weighted mean of its
mesh blocks (so it lands on housing, not in the park between two estates).
Jobs sit on the same point unless the SA1's job-weighted centre is over
SPLIT_M away and both sides are substantial, in which case the jobs get their
own point -- an industrial estate at one end of a residential SA1.

Output: build/zones_SYD.npz and data/mb_SYD.parquet (per-MB attributes).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX
import numpy as np, pandas as pd, geopandas as gpd

YEAR = 2026
SPLIT_M, SPLIT_MIN = 500, 50
PAD = 0.12                                     # MBs just outside the box still count for zone totals
T = 'data/tz21/concordances/TZ21_Concordances'

# ---------------------------------------------------------------- mesh blocks
mb = gpd.read_file('/vsizip/data/abs/MB_2021_AUST_SHP_GDA2020.zip/MB_2021_AUST_GDA2020.shp',
                   bbox=(BBOX[0] - PAD, BBOX[1] - PAD, BBOX[2] + PAD, BBOX[3] + PAD), engine='pyogrio')
mb = mb[(mb.STE_CODE21 == '1') & mb.geometry.notna()].copy()
mb['MB'] = mb.MB_CODE21.astype(np.int64)
rp = mb.geometry.representative_point()
mb['lon'] = rp.x; mb['lat'] = rp.y
mb['in_box'] = mb.lon.between(BBOX[0], BBOX[2]) & mb.lat.between(BBOX[1], BBOX[3])
mb = pd.DataFrame(mb.drop(columns='geometry'))
print(f"mesh blocks near box: {len(mb):,}  in box: {mb.in_box.sum():,}")

# ---------------------------------------------------------------- TZP24 -> MB
tzmb = pd.read_parquet('data/tz21/tz21_mb21.parquet') if os.path.exists('data/tz21/tz21_mb21.parquet') else \
       pd.read_excel(f'{T}/02_TZ21_MB21_PopEmpArea.xlsx', sheet_name=1)
tzmb = tzmb.rename(columns={'MB_CODE21': 'MB'})
emp = pd.read_csv('data/tzp24/employment_by_tz.csv', encoding='utf-8-sig')
pop = pd.read_csv('data/tzp24/population_by_tz.csv', encoding='utf-8-sig')
wkf = pd.read_csv('data/tzp24/workforce_by_tz.csv', encoding='utf-8-sig')
tz = (emp[['TZ_CODE21', 'EMP_2021', f'EMP_{YEAR}']]
      .merge(pop[['TZ_CODE21', 'ERP_2021', f'ERP_{YEAR}']], on='TZ_CODE21')
      .merge(wkf[['TZ_CODE21', 'Emp_Wkf_POPD_15+yrs_2021', f'Emp_Wkf_POPD_15+yrs_{YEAR}']], on='TZ_CODE21'))
tz.columns = ['TZ21', 'emp21', 'emp', 'pop21', 'pop', 'wkf21', 'wkf']
x = tzmb.rename(columns={'TZ_CODE21': 'TZ21'}).merge(tz, on='TZ21')
x['pop_mb'] = x['pop'] * x.POPULATION / 100
x['wkf_mb'] = x['wkf'] * x.POPULATION / 100
x['emp_mb'] = x['emp'] * x.EMPLOYMENT / 100
x['wkf21_mb'] = x['wkf21'] * x.POPULATION / 100
x['emp21_mb'] = x['emp21'] * x.EMPLOYMENT / 100
agg = x.groupby('MB')[['pop_mb', 'wkf_mb', 'emp_mb', 'wkf21_mb', 'emp21_mb']].sum()
mb = mb.merge(agg, left_on='MB', right_index=True, how='left').fillna(
    {'pop_mb': 0, 'wkf_mb': 0, 'emp_mb': 0, 'wkf21_mb': 0, 'emp21_mb': 0})
print(f"box totals {YEAR}: population {mb.pop_mb[mb.in_box].sum():,.0f}  "
      f"employed residents {mb.wkf_mb[mb.in_box].sum():,.0f}  jobs {mb.emp_mb[mb.in_box].sum():,.0f}")

# ---------------------------------------------------------------- MB -> TZ11
tz11 = gpd.read_file('data/tz11/tz11_shp/TZ_NSW_2011.shp', engine='pyogrio').to_crs(4326)
tzcol = next(c for c in tz11.columns if c.upper() in ('TZ_CODE11', 'TZ11', 'TZ_CODE', 'TZ_2011'))
pts = gpd.GeoDataFrame(mb[['MB']], geometry=gpd.points_from_xy(mb.lon, mb.lat), crs=4326)
j = gpd.sjoin(pts, tz11[[tzcol, 'geometry']], how='left', predicate='within')
j = j[~j.index.duplicated()]
mb['TZ11'] = j[tzcol].astype('float').fillna(-1).astype(np.int64).values
miss = (mb.TZ11 < 0) & (mb.wkf_mb + mb.emp_mb > 0)
if miss.any():                                  # coastal slivers: nearest zone
    nn = gpd.sjoin_nearest(pts[miss.values].to_crs(3308), tz11[[tzcol, 'geometry']].to_crs(3308), how='left')
    nn = nn[~nn.index.duplicated()]
    mb.loc[miss, 'TZ11'] = nn[tzcol].astype(np.int64).values
print(f"MBs linked to TZ11: {(mb.TZ11 >= 0).mean():.1%}  (nearest-zone fallback for {miss.sum()})")
mb.to_parquet(f'data/mb_{CITY}.parquet')

# ---------------------------------------------------------------- SA1 points
m = mb[mb.in_box].copy()
m['SA1'] = m.SA1_CODE21.astype(np.int64)
xy = np.c_[m.lon.values * np.cos(np.radians(-34)) * 111.32, m.lat.values * 110.57]   # km, local
m['X'] = xy[:, 0]; m['Y'] = xy[:, 1]

def anchor(g, w):
    wt = g[w].values
    if wt.sum() <= 0:
        wt = g.AREASQKM21.values.astype(float)
    cx = np.average(g.X, weights=wt); cy = np.average(g.Y, weights=wt)
    cand = wt > 0
    k = np.argmin(np.where(cand, np.hypot(g.X - cx, g.Y - cy), np.inf))
    return g.index[k]

rows = []
for sa1, g in m.groupby('SA1', sort=True):
    W, J = g.wkf_mb.sum(), g.emp_mb.sum()
    if W + J < 0.5:
        continue
    h = anchor(g, 'wkf_mb') if W > 0 else anchor(g, 'emp_mb')
    jb = anchor(g, 'emp_mb') if J > 0 else h
    d = float(np.hypot(g.X[h] - g.X[jb], g.Y[h] - g.Y[jb])) * 1000
    split = d > SPLIT_M and W >= SPLIT_MIN and J >= SPLIT_MIN
    base = dict(SA1=sa1, SA2=int(g.SA2_CODE21.iloc[0]), SA3=int(g.SA3_CODE21.iloc[0]),
                SA4=int(g.SA4_CODE21.iloc[0]))
    if split:
        rows.append({**base, 'kind': 'home', 'lon': g.lon[h], 'lat': g.lat[h], 'W': W, 'J': 0.0})
        rows.append({**base, 'kind': 'work', 'lon': g.lon[jb], 'lat': g.lat[jb], 'W': 0.0, 'J': J})
    else:
        rows.append({**base, 'kind': 'both', 'lon': g.lon[h], 'lat': g.lat[h], 'W': W, 'J': J})
P = pd.DataFrame(rows).reset_index(drop=True)
P['pid'] = np.arange(len(P))
print(f"points: {len(P):,}  ({(P.kind=='both').sum():,} combined, {(P.kind=='home').sum():,} split pairs)  "
      f"SA1s {P.SA1.nunique():,}")

# MB -> point, so zone-to-zone flows can be split by mesh-block weights
home_pid = P[P.kind != 'work'].set_index('SA1').pid
work_pid = P[P.kind != 'home'].set_index('SA1').pid
m['home_pid'] = m.SA1.map(home_pid).fillna(-1).astype(np.int64)
m['work_pid'] = m.SA1.map(work_pid).fillna(-1).astype(np.int64)
m[['MB', 'SA1', 'TZ11', 'wkf_mb', 'emp_mb', 'home_pid', 'work_pid']].to_parquet(f'data/mb_points_{CITY}.parquet')
P.to_parquet(f'data/points_{CITY}.parquet')
print(f"workers {P.W.sum():,.0f}  jobs {P.J.sum():,.0f}")
