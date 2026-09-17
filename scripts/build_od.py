"""SA1-point commute matrix for SYD, and the base demand_data.json.

Source: TfNSW Journey to Work 2011, Table 11 -- Census 2011 employed persons by
origin travel zone x destination travel zone (TZ11, ~2,400 zones in the box).
It is the finest public commute table for Sydney: TfNSW withdrew the 2016
travel-zone release after ABS confidentiality changes, and 2021 origin-
destination data is only in ABS TableBuilder.

Steps
  1. Zone margins for 2026. Every TZ11 gets employed residents and jobs from
     TZP24 (via mesh blocks), restricted to the part inside the box and to the
     share of its 2011 commuters who stayed inside the box.
  2. Growth zones. A zone that had few 2011 workers (or jobs) relative to 2026
     -- a new estate, a new business park, the airport -- borrows the commute
     pattern of its nearest established zones, blended by how much 2011
     evidence it has.
  3. IPF of the 2011 pattern to the 2026 margins at TZ11 level.
  4. Each zone-to-zone flow is split onto SA1 points: by employed residents at
     the home end and jobs at the work end, with a mild distance preference
     inside the pair; then re-fitted so point margins and zone-pair totals
     both hold (tri-proportional IPF).
  5. Sparsified to a playable number of pops (as for BLN): coverage-based
     support plus SA3-pair and distance-band support, small pairs pruned, and
     every re-fit holds point margins, SA3-pair totals and the trip-length
     distribution fixed.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, CITY_DIR
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

NO_FIXED = {9499, 9599, 9799}
RELIABLE = 0.4          # 2011 evidence >= 40% of 2026 volume -> own pattern only
KNN = 8
BETA_IN = 3.0           # km, distance preference inside a zone pair
OUT = f'{CITY_DIR}/demand_data.json'
t00 = time.time()
def log(*a): print(f"[{time.time()-t00:6.0f}s]", *a, flush=True)

P = pd.read_parquet(f'data/points_{CITY}.parquet')
MBP = pd.read_parquet(f'data/mb_points_{CITY}.parquet')
MBA = pd.read_parquet(f'data/mb_{CITY}.parquet')
NP = len(P)
KX = np.cos(np.radians(-34)) * 111.32; KY = 110.57
px = (P.lon.values * KX).astype(np.float64); py = (P.lat.values * KY).astype(np.float64)

# ------------------------------------------------------------ zone totals
tzW_all = MBA.groupby('TZ11').wkf_mb.sum(); tzJ_all = MBA.groupby('TZ11').emp_mb.sum()
tzW_in = MBP.groupby('TZ11').wkf_mb.sum();  tzJ_in = MBP.groupby('TZ11').emp_mb.sum()
Zs = np.array(sorted(set(tzW_in.index[tzW_in > 0]) | set(tzJ_in.index[tzJ_in > 0])))
Zs = Zs[Zs >= 0]; n = len(Zs); zi = {z: i for i, z in enumerate(Zs)}
Win = tzW_in.reindex(Zs).fillna(0).values; Jin = tzJ_in.reindex(Zs).fillna(0).values
inW = Win / np.maximum(tzW_all.reindex(Zs).fillna(0).values, 1e-9)
inJ = Jin / np.maximum(tzJ_all.reindex(Zs).fillna(0).values, 1e-9)
inW = np.clip(inW, 0, 1); inJ = np.clip(inJ, 0, 1)
MBP['lonx'] = MBP.MB.map(MBA.set_index('MB').lon) * KX
MBP['laty'] = MBP.MB.map(MBA.set_index('MB').lat) * KY
def centroid(w):
    g = MBP.assign(w=MBP[w] + 1e-6).groupby('TZ11')
    cx = g.apply(lambda d: np.average(d.lonx, weights=d.w), include_groups=False)
    cy = g.apply(lambda d: np.average(d.laty, weights=d.w), include_groups=False)
    return cx.reindex(Zs).values, cy.reindex(Zs).values
zhx, zhy = centroid('wkf_mb'); zjx, zjy = centroid('emp_mb')
log(f"zones {n:,}  in-box employed residents {Win.sum():,.0f}  jobs {Jin.sum():,.0f}")

# ------------------------------------------------------------ 2011 flows
# Table 19 (TZ x TZ x mode) rather than Table 11, to take out people working
# from home: in 2011 their workplace was coded to their home, so they appear as
# zero-length commutes. Mode 9 lumps them with 'did not go to work' (people with
# a real workplace who were off that day). Other modes put 11% of workers in
# their home zone, which implies ~37k of the 151k intrazonal mode-9 workers are
# absentees; keep that share and drop the rest.
t = pd.read_csv('data/jtw11/t19/2011JTW_Table19_V1.1.csv',
                usecols=['O_TZ11', 'D_TZ11', 'MODE9', 'EMPLOYED_PERSONS'], dtype={'O_TZ11': str, 'D_TZ11': str})
t = t[t.O_TZ11.str.fullmatch(r'\d+', na=False) & t.D_TZ11.str.fullmatch(r'\d+', na=False)]
t['o'] = t.O_TZ11.astype(int); t['d'] = t.D_TZ11.astype(int)
t = t[~t.d.isin(NO_FIXED)]
wfh = (t.MODE9 == 9) & (t.o == t.d)
same_other = t[(t.MODE9 != 9) & (t.o == t.d)].EMPLOYED_PERSONS.sum() / t[t.MODE9 != 9].EMPLOYED_PERSONS.sum()
m9 = t[t.MODE9 == 9].EMPLOYED_PERSONS.sum(); m9_away = t[(t.MODE9 == 9) & ~wfh].EMPLOYED_PERSONS.sum()
keep_share = min(1.0, m9_away * same_other / (1 - same_other) / t[wfh].EMPLOYED_PERSONS.sum())
t.loc[wfh, 'EMPLOYED_PERSONS'] *= keep_share
log(f"home-workers: kept {keep_share:.0%} of {t[wfh].EMPLOYED_PERSONS.sum()/keep_share:,.0f} intrazonal "
    f"'worked at home / did not go to work' (other modes: {same_other:.1%} intrazonal)")
t = t.groupby(['o', 'd'], as_index=False).EMPLOYED_PERSONS.sum()
out_o = t.groupby('o').EMPLOYED_PERSONS.sum().reindex(Zs).fillna(0).values
out_d = t.groupby('d').EMPLOYED_PERSONS.sum().reindex(Zs).fillna(0).values
t = t[t.o.isin(zi) & t.d.isin(zi)]
oi = t.o.map(zi).values; di = t.d.map(zi).values
F = np.zeros((n, n))
np.add.at(F, (oi, di), t.EMPLOYED_PERSONS.values)
log(f"2011 flows: {len(t):,} zone pairs, {F.sum():,.0f} workers between box zones")

Fin = F * inW[:, None] * inJ[None, :]
n11 = Fin.sum(1); m11 = Fin.sum(0)
r = np.divide((F * inJ[None, :]).sum(1), out_o, out=np.full(n, np.nan), where=out_o > 0)
c = np.divide((F * inW[:, None]).sum(0), out_d, out=np.full(n, np.nan), where=out_d > 0)
def fill_nb(v, xs, ys):          # zones with no 2011 flows take their neighbours' share
    ok = ~np.isnan(v)
    tr = cKDTree(np.c_[xs[ok], ys[ok]])
    _, k = tr.query(np.c_[xs[~ok], ys[~ok]], k=KNN)
    v = v.copy(); v[~ok] = v[ok][k].mean(1)
    return v
r = fill_nb(r, zhx, zhy); c = fill_nb(c, zjx, zjy)
R = Win * r
C = Jin * c; C *= R.sum() / C.sum()
log(f"2026 in-box commuters {R.sum():,.0f}  (stay-in-box share {R.sum()/Win.sum():.1%})")

# ------------------------------------------------------------ growth zones
def neighbour_rows(M, tot, xs, ys, reliable):
    tr = cKDTree(np.c_[xs[reliable], ys[reliable]])
    idx = np.nonzero(reliable)[0]
    dd, kk = tr.query(np.c_[xs, ys], k=KNN + 1)
    NB = np.zeros_like(M)
    for i in range(len(xs)):
        sel = [(d_, idx[k_]) for d_, k_ in zip(dd[i], kk[i]) if idx[k_] != i][:KNN]
        w = np.array([1 / (d_ + 1.0) for d_, _ in sel]); w /= w.sum()
        for wi, (_, j) in zip(w, sel):
            NB[i] += wi * M[j] / tot[j]
    return NB

a_row = np.clip(np.divide(n11, RELIABLE * R, out=np.ones(n), where=R > 0), 0, 1)
rel = (a_row >= 1) & (n11 >= 50)
NBr = neighbour_rows(Fin, n11, zhx, zhy, rel)
own = np.divide(Fin, n11[:, None], out=np.zeros_like(Fin), where=n11[:, None] > 0)
S = (a_row[:, None] * own + (1 - a_row[:, None]) * NBr) * R[:, None]
log(f"growth origins: {(a_row < 1).sum():,} zones holding {R[a_row < 1].sum():,.0f} commuters borrow neighbour patterns")

sc_ = S.sum(0)
a_col = np.clip(np.divide(m11, RELIABLE * C, out=np.ones(n), where=C > 0), 0, 1)
relc = (a_col >= 1) & (m11 >= 50)
NBc = neighbour_rows(S.T, np.maximum(sc_, 1e-9), zjx, zjy, relc & (sc_ > 0)).T
ownc = np.divide(S, sc_[None, :], out=np.zeros_like(S), where=sc_[None, :] > 0)
S = (a_col[None, :] * ownc + (1 - a_col[None, :]) * NBc) * C[None, :]
log(f"growth destinations: {(a_col < 1).sum():,} zones holding {C[a_col < 1].sum():,.0f} jobs borrow neighbour patterns")

for it in range(200):
    rs = S.sum(1); S *= np.divide(R, rs, out=np.zeros(n), where=rs > 0)[:, None]
    cs = S.sum(0); S *= np.divide(C, cs, out=np.zeros(n), where=cs > 0)[None, :]
rerr = np.abs(S.sum(1) - R).sum() / R.sum()
zd = np.hypot(zhx[:, None] - zjx[None, :], zhy[:, None] - zjy[None, :])
log(f"zone IPF: row error {rerr:.4%}   mean zone-centroid distance 2011 {np.average(zd, weights=Fin):.2f} km"
    f" -> 2026 {np.average(zd, weights=S):.2f} km")

# ------------------------------------------------------------ onto points
hz = MBP[MBP.home_pid >= 0].groupby(['TZ11', 'home_pid']).wkf_mb.sum().reset_index()
wz = MBP[MBP.work_pid >= 0].groupby(['TZ11', 'work_pid']).emp_mb.sum().reset_index()
H = {z: (g.home_pid.values, g.wkf_mb.values / g.wkf_mb.sum()) for z, g in hz.groupby('TZ11') if g.wkf_mb.sum() > 0}
Wd = {z: (g.work_pid.values, g.emp_mb.values / g.emp_mb.sum()) for z, g in wz.groupby('TZ11') if g.emp_mb.sum() > 0}
rowP = np.zeros(NP); colP = np.zeros(NP)
for z, (p, w) in H.items():  rowP[p] += R[zi[z]] * w
for z, (q, w) in Wd.items(): colP[q] += C[zi[z]] * w

Sf = np.where(S >= 0.02, S, 0)
parts_r, parts_c, parts_b, parts_v = [], [], [], []
for o in range(n):
    if Zs[o] not in H: continue
    hp, hw = H[Zs[o]]
    ds = np.nonzero(Sf[o])[0]
    ds = np.array([d for d in ds if Zs[d] in Wd], dtype=np.int64)
    if not len(ds): continue
    qs = [Wd[Zs[d]] for d in ds]
    lens = np.array([len(q[0]) for q in qs])
    qp = np.concatenate([q[0] for q in qs]); qw = np.concatenate([q[1] for q in qs])
    dq = np.repeat(ds, lens)
    dist = np.hypot(px[hp][:, None] - px[qp][None, :], py[hp][:, None] - py[qp][None, :])
    wgt = hw[:, None] * qw[None, :] * np.exp(-dist / BETA_IN)
    starts = np.r_[0, np.cumsum(lens)[:-1]]
    bsum = np.add.reduceat(wgt.sum(0), starts)
    val = wgt * (Sf[o, ds] / np.maximum(bsum, 1e-30))[np.repeat(np.arange(len(ds)), lens)][None, :]
    parts_r.append(np.repeat(hp, len(qp)).astype(np.int32))
    parts_c.append(np.tile(qp, len(hp)).astype(np.int32))
    parts_b.append(np.tile(o * n + dq, len(hp)).astype(np.int64))
    parts_v.append(val.ravel())
er = np.concatenate(parts_r); ec = np.concatenate(parts_c)
eb = np.concatenate(parts_b); ev = np.concatenate(parts_v).astype(np.float64)
del parts_r, parts_c, parts_b, parts_v
ub, eb = np.unique(eb, return_inverse=True)
btot = np.bincount(eb, ev)
log(f"point-level entries {len(ev):,}  zone-pair blocks {len(ub):,}")
for it in range(40):
    rs = np.bincount(er, ev, NP); ev *= np.divide(rowP, rs, out=np.zeros(NP), where=rs > 0)[er]
    cs = np.bincount(ec, ev, NP); ev *= np.divide(colP, cs, out=np.zeros(NP), where=cs > 0)[ec]
    bs = np.bincount(eb, ev, len(ub)); ev *= np.divide(btot, bs, out=np.zeros(len(ub)), where=bs > 0)[eb]
key = er.astype(np.int64) * NP + ec
uk, inv = np.unique(key, return_inverse=True)
T = np.zeros((NP, NP), dtype=np.float32)
T.flat[uk] = np.bincount(inv, ev).astype(np.float32)
del er, ec, eb, ev, key, inv
# same-point pairs (live and work in one SA1) are not trips the game can serve
same = float(np.trace(T, dtype=np.float64)); np.fill_diagonal(T, 0)
log(f"dropped {same:,.0f} same-SA1 commuters ({same/(T.sum(dtype=np.float64)+same):.1%})")
row_m = T.sum(1, dtype=np.float64); col_m = T.sum(0, dtype=np.float64)
log(f"dense point matrix {T.sum(dtype=np.float64):,.0f} commuters; "
    f"row fit {np.abs(row_m - rowP).sum()/rowP.sum():.3%}")

# ------------------------------------------------------------ trip lengths
def dist_rows(a, b):
    return np.hypot(px[a:b, None] - px[None, :], py[a:b, None] - py[None, :])
BANDS = np.array([0, 0.75, 1.5, 2.5, 4, 6, 8, 11, 15, 20, 30, 50, 1e9])
NB = len(BANDS) - 1
metro = (P.SA4.values >= 115) & (P.SA4.values <= 128)       # Greater Sydney excl. Central Coast
band_tot = np.zeros(2 * NB)
mean_num = 0.0
for a in range(0, NP, 1000):
    b = min(NP, a + 1000); D = dist_rows(a, b)
    bi = np.clip(np.searchsorted(BANDS, D, side='right') - 1, 0, NB - 1)
    grp = (metro[a:b, None] & metro[None, :]).astype(np.int64)
    band_tot += np.bincount((bi + grp * NB).ravel(), weights=T[a:b].ravel().astype(np.float64), minlength=2 * NB)
    mean_num += float((T[a:b] * D).sum(dtype=np.float64))
dense_mean = mean_num / T.sum(dtype=np.float64)
bt = band_tot[:NB] + band_tot[NB:]
log(f"dense mean straight-line commute {dense_mean:.2f} km; bands " +
    ", ".join(f"{BANDS[k]:g}-{BANDS[k+1]:g} {bt[k]/bt.sum()*100:.1f}%" for k in range(NB)))

# ------------------------------------------------------------ sparsify
S3 = np.unique(P.SA3.values); s3i = {s: i for i, s in enumerate(S3)}; nG = len(S3)
zg = np.array([s3i[s] for s in P.SA3.values])
M = np.zeros((nG, nG))
for a in range(0, NP, 2000):
    b = min(NP, a + 2000)
    blk = np.add.reduceat(T[a:b][:, np.argsort(zg, kind='stable')], np.searchsorted(np.sort(zg), np.arange(nG)), axis=1)
    np.add.at(M, zg[a:b], blk)

# Support by systematic sampling. SA1s are small (~240 commuters), so almost
# every pair is a handful of people and threshold pruning either keeps ~150k
# pops or, at a higher threshold, collapses the fit (tried: 41% row error).
# Instead lay each origin's commuters end to end and take a pair every STEP
# people, with a random start -- a pair is picked with probability proportional
# to its flow, so long commutes are neither favoured nor dropped. Do the same
# ordered by destination so every job point gets its share, take the union and
# re-fit sizes to all margins.
STEP = float(os.environ.get('SB_POP_STEP', 70))
rng = np.random.default_rng(20260917)
def systematic(M_, tot, step):
    out_a, out_b = [], []
    G = rng.random() * step
    for a in range(M_.shape[0]):
        ra = float(tot[a])
        if ra <= 0: continue
        k0 = np.ceil(G / step - 1e-12)
        ticks = np.arange(k0, np.floor((G + ra) / step - 1e-12) + 1) * step - G
        ticks = ticks[(ticks >= 0) & (ticks < ra)]
        if len(ticks) == 0:
            ticks = np.array([rng.random() * ra])          # every point keeps a pair
        cs = np.cumsum(M_[a], dtype=np.float64)
        idx = np.minimum(np.searchsorted(cs, ticks, side='right'), M_.shape[1] - 1)
        out_a.append(np.full(len(idx), a)); out_b.append(idx)
        G += ra
    return np.concatenate(out_a), np.concatenate(out_b)
ra_, rb_ = systematic(T, row_m, STEP)
Tt = np.ascontiguousarray(T.T)
cb_, ca_ = systematic(Tt, col_m, STEP)
del Tt
rr = np.r_[ra_, ca_]; cc = np.r_[rb_, cb_]
key = np.unique(rr.astype(np.int64) * NP + cc)
sr = (key // NP).astype(np.int32); sc = (key % NP).astype(np.int32)
sv = T[sr, sc].astype(np.float64)
del T
log(f"support {len(sv):,} pairs (step {STEP:g})")

def refit(sr, sc, sv, iters=150):
    blk_id = zg[sr] * nG + zg[sc]
    band_id = (np.clip(np.searchsorted(BANDS, np.hypot(px[sr] - px[sc], py[sr] - py[sc]), side='right') - 1, 0, NB - 1)
               + (metro[sr] & metro[sc]).astype(np.int64) * NB)
    for it in range(iters):
        bs_ = np.bincount(band_id, sv, 2 * NB)
        sv *= np.divide(band_tot, bs_, out=np.zeros(2 * NB), where=bs_ > 0)[band_id]
        bsum = np.bincount(blk_id, sv, nG * nG)
        sv *= np.divide(M.ravel(), bsum, out=np.zeros(nG * nG), where=bsum > 0)[blk_id]
        cs = np.bincount(sc, sv, NP); sv *= np.divide(col_m, cs, out=np.zeros(NP), where=cs > 0)[sc]
        rs = np.bincount(sr, sv, NP); sv *= np.divide(row_m, rs, out=np.zeros(NP), where=rs > 0)[sr]
    return sv
sv = refit(sr, sc, sv, iters=300)
# fold away slivers the re-fit shrank to nothing, keeping each point's biggest link
MIN_POP = float(os.environ.get('SB_MIN_POP', 3))
for rnd in range(4):
    top_r = np.zeros(len(sv), bool); top_c = np.zeros(len(sv), bool)
    o_ = np.lexsort((-sv, sr)); first = np.r_[True, sr[o_][1:] != sr[o_][:-1]]; top_r[o_[first]] = True
    o_ = np.lexsort((-sv, sc)); first = np.r_[True, sc[o_][1:] != sc[o_][:-1]]; top_c[o_[first]] = True
    keep = (sv >= MIN_POP) | top_r | top_c
    if keep.all(): break
    sr, sc, sv = sr[keep], sc[keep], sv[keep]
    sv = refit(sr, sc, sv)
    log(f"  prune round {rnd+1}: {len(sv):,} pairs  mean {sv.sum()/len(sv):.1f}/pair")

rerr = np.abs(np.bincount(sr, sv, NP) - row_m).sum() / row_m.sum()
cerr = np.abs(np.bincount(sc, sv, NP) - col_m).sum() / col_m.sum()
berr = np.abs(np.bincount(zg[sr] * nG + zg[sc], sv, nG * nG) - M.ravel()).sum() / M.sum()
fd = np.hypot(px[sr] - px[sc], py[sr] - py[sc])
log(f"sparse mean straight-line commute {np.average(fd, weights=sv):.2f} km (dense {dense_mean:.2f}); "
    f"under 2.5 km sparse {sv[fd < 2.5].sum()/sv.sum():.1%} dense {bt[:3].sum()/bt.sum():.1%}")
log(f"margin error: rows {rerr:.2%}  cols {cerr:.2%}  SA3 pairs {berr:.2%}")
np.savez_compressed(f'build/od_debug_{CITY}.npz', sr=sr, sc=sc, sv=sv, row_m=row_m, col_m=col_m,
                    band_tot=band_tot, M=M, S3=S3)

# ------------------------------------------------------------ emit
target = int(round(sv.sum())); fl = np.floor(sv).astype(np.int64)
rem = target - fl.sum()
if rem > 0: fl[np.argsort(sv - fl)[::-1][:rem]] += 1
keep = fl > 0; sr, sc, fl = sr[keep], sc[keep], fl[keep]
used = np.unique(np.concatenate([sr, sc]))
points = [{"id": str(int(i)), "location": [round(float(P.lon[i]), 6), round(float(P.lat[i]), 6)],
           "jobs": 0, "residents": 0, "popIds": []} for i in used]
pops = [{"id": str(k), "size": int(s), "residenceId": str(int(a)), "jobId": str(int(b)),
         "drivingSeconds": 0, "drivingDistance": 0} for k, (a, b, s) in enumerate(zip(sr, sc, fl))]
os.makedirs(CITY_DIR, exist_ok=True)
json.dump({"points": points, "pops": pops}, open(OUT, 'w'), separators=(',', ':'))
log(f"points {len(points):,}   pops {len(pops):,}   people {fl.sum():,}   "
    f"mean {fl.mean():.1f}/pop   {os.path.getsize(OUT)/1e6:.1f} MB -> {OUT}")
