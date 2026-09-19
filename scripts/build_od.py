"""SA1-point commute matrix for SYD, and the base demand_data.json.

Sources
  * ABS 2021 Census (TableBuilder), employed persons by place of usual residence
    x place of work: SA1 (UR) x SA2 (POW) ("Table A") and SA2 (UR) x SA2 (POW)
    ("Table B"), in data/abs/. Cells are randomly perturbed by the ABS, so the
    SA1 table sets each SA1's pattern and the SA2 table the totals between areas.
  * TfNSW Travel Zone Projections 2024: employed residents and jobs for 2026 by
    mesh block (points carry them as W and J).
  * TfNSW Journey to Work 2011 (TZ x TZ x mode), only to estimate people who
    usually work at home, which the 2021 tables can't separate: their workplace
    is coded to their home, so they would otherwise become very short commutes.

2021 Place of Work is usable despite the lockdown on Census night: the ABS asked
people working from home because of COVID to give their usual workplace.

Steps
  1. Margins for 2026: each point's employed residents and jobs, restricted to
     commuters who both live and work inside the map (shares from the 2021 tables).
  2. SA2 x SA2 flows: Table B with usual home-workers taken off the diagonal;
     SA2s with little 2021 evidence for their 2026 size (new estates, the new
     airport) borrow their nearest established neighbours' patterns; fitted to
     the 2026 SA2 totals.
  3. Point seed: each home SA1's own Table A pattern (blended with its SA2's
     pattern where the SA1 has little 2021 evidence, and a little everywhere to
     smooth the ABS perturbation), split across the job points of each
     destination SA2 by jobs, with a mild distance preference.
  4. Tri-proportional IPF: point rows, point columns and SA2-pair totals.
  5. Sparsified to a playable number of pops, holding point margins, SA3-pair
     totals and the trip-length distribution (unchanged from v2.0).
"""
import sys, os, csv, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, CITY_DIR
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

NO_FIXED = {9499, 9599, 9799}
RELIABLE = 0.4          # 2021 evidence >= 40% of 2026 volume -> own pattern only
KNN = 8
BETA_IN = 3.0           # km, distance preference among job points inside a destination SA2
SMOOTH = 0.15           # minimum weight of the SA2 pattern in each SA1's seed (ABS perturbation)
MIN_SHARE = 0.002       # destination SA2s below this share of an SA1's seed are left out
OUT = f'{CITY_DIR}/demand_data.json'
t00 = time.time()
def log(*a): print(f"[{time.time()-t00:6.0f}s]", *a, flush=True)

P = pd.read_parquet(f'data/points_{CITY}.parquet')
MBA = pd.read_parquet(f'data/mb_{CITY}.parquet')
NP = len(P)
KX = np.cos(np.radians(-34)) * 111.32; KY = 110.57
px = (P.lon.values * KX).astype(np.float64); py = (P.lat.values * KY).astype(np.float64)


def read_tablebuilder(path):
    """TableBuilder CSV -> (column names, row names, matrix)."""
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))
    hi = next(i for i, r in enumerate(rows) if r and r[0].startswith('SA2 (POW)'))
    cols = [c for c in rows[hi][1:] if c != '']
    names, data = [], []
    for r in rows[hi + 2:]:
        if len(r) < len(cols) + 1 or not r[0] or r[0].startswith(('Dataset', 'INFO', 'Copyright', 'ABS')):
            continue
        names.append(r[0]); data.append([float(x or 0) for x in r[1:len(cols) + 1]])
    return cols, names, np.array(data)


# ------------------------------------------------------------ zones = SA2
Zs = np.array(sorted(P.SA2.astype(str).unique())); n = len(Zs); zi = {z: i for i, z in enumerate(Zs)}
p_z = np.array([zi[s] for s in P.SA2.astype(str)])
name2code = MBA.drop_duplicates('SA2_CODE21').set_index('SA2_NAME21').SA2_CODE21.astype(str)
home = P.W.values > 0; work = P.J.values > 0

colsA, rowsA, A = read_tablebuilder('data/abs/tb/Table A1.csv')
colsB, rowsB, B = read_tablebuilder('data/abs/tb/tabB.csv')
assert colsA == colsB
cz = np.array([zi.get(name2code.get(c, ''), -1) for c in colsA])            # table column -> zone (or -1)
nsw_cols = np.array([c not in ('Total',) and not c.startswith(('Migratory', 'POW No Fixed', 'POW not stated'))
                     for c in colsA])
inbox_cols = cz >= 0


def to_zones(M):
    """Columns of M (table SA2s) -> in-box zone columns."""
    out = np.zeros((M.shape[0], n))
    np.add.at(out.T, cz[inbox_cols], M[:, inbox_cols].T)
    return out


rowA = {s: i for i, s in enumerate(rowsA)}
A_pts = np.zeros((NP, n)); A_nsw = np.zeros(NP)
for i, s in enumerate(P.SA1.astype(str)):
    if home[i] and s in rowA:
        A_pts[i] = to_zones(A[rowA[s]][None, :])[0]
        A_nsw[i] = A[rowA[s], nsw_cols].sum()
# job points share an SA1 with a home point: count each SA1's row once, on its home point
dup = pd.Series(P.SA1.values).duplicated(keep='first').values & home
A_pts[dup] = 0; A_nsw[dup] = 0

rowB = {name2code.get(s, ''): i for i, s in enumerate(rowsB)}
B_all = np.zeros((n, n)); B_rowtot = np.zeros(n)
for z, i in zi.items():
    if z in rowB:
        B_all[i] = to_zones(B[rowB[z]][None, :])[0]
        B_rowtot[i] = B[rowB[z], nsw_cols].sum()
col_all = to_zones(B[[i for i, s in enumerate(rowsB) if s != 'Total']]).sum(0)   # workers into each zone, from anywhere
log(f"SA2 zones {n}; 2021 in-box flows: SA1 table {A_pts.sum():,.0f}, SA2 table {B_all.sum():,.0f}")

# ------------------------------------------------------------ usual home-workers (2011 rates)
# 2011 Table 19: intrazonal 'worked at home / did not go to work' less the share
# that were absentees (other modes put 11% of workers in their home zone).
t = pd.read_csv('data/jtw11/t19/2011JTW_Table19_V1.1.csv',
                usecols=['O_TZ11', 'D_TZ11', 'MODE9', 'EMPLOYED_PERSONS'], dtype={'O_TZ11': str, 'D_TZ11': str})
t = t[t.O_TZ11.str.fullmatch(r'\d+', na=False) & t.D_TZ11.str.fullmatch(r'\d+', na=False)]
t['o'] = t.O_TZ11.astype(int); t['d'] = t.D_TZ11.astype(int)
t = t[~t.d.isin(NO_FIXED)]
wfh = (t.MODE9 == 9) & (t.o == t.d)
same_other = t[(t.MODE9 != 9) & (t.o == t.d)].EMPLOYED_PERSONS.sum() / t[t.MODE9 != 9].EMPLOYED_PERSONS.sum()
m9_away = t[(t.MODE9 == 9) & ~wfh].EMPLOYED_PERSONS.sum()
keep_share = min(1.0, m9_away * same_other / (1 - same_other) / t[wfh].EMPLOYED_PERSONS.sum())
hw_tz = (t[wfh].groupby('o').EMPLOYED_PERSONS.sum() * (1 - keep_share))
wk_tz = t.groupby('o').EMPLOYED_PERSONS.sum()
rate_tz = (hw_tz / wk_tz).reindex(wk_tz.index).fillna(0)
mb = MBA[MBA.in_box].copy()
mb['rate'] = mb.TZ11.map(rate_tz).fillna(rate_tz.median())
mb['SA2'] = mb.SA2_CODE21.astype(str)
g = mb.assign(w=mb.wkf21_mb * mb.rate).groupby('SA2')
rate_z = (g.w.sum() / mb.groupby('SA2').wkf21_mb.sum()).reindex(Zs).fillna(rate_tz.median()).values
log(f"usual home-workers: 2011 rate {np.average(rate_z, weights=B_all.sum(1) + 1e-9):.1%} of workers "
    f"(kept {keep_share:.0%} of intrazonal mode 9 as absentees)")
hw_pts = np.minimum(rate_z[p_z] * A_pts.sum(1), A_pts[np.arange(NP), p_z])
A_pts[np.arange(NP), p_z] -= hw_pts
hw_z = np.minimum(rate_z * B_all.sum(1), np.diag(B_all))
B_all[np.arange(n), np.arange(n)] -= hw_z
log(f"  removed {hw_pts.sum():,.0f} (SA1 table) / {hw_z.sum():,.0f} (SA2 table) from own-SA2 cells")

# ------------------------------------------------------------ 2026 margins
# live-in-box share of each SA1's workers who work in the box; for jobs, the
# share of each SA2's workers who live in the box
stay_pt = np.divide(A_pts.sum(1) + hw_pts, A_nsw, out=np.full(NP, np.nan), where=A_nsw > 20)
stay_z = np.divide(B_all.sum(1) + hw_z, B_rowtot, out=np.full(n, np.nan), where=B_rowtot > 0)
stay_z = np.where(np.isnan(stay_z), np.nanmedian(stay_z), stay_z)
stay_pt = np.where(np.isnan(stay_pt), stay_z[p_z], stay_pt)
inj_z = np.divide(B_all.sum(0) + hw_z, col_all, out=np.full(n, np.nan), where=col_all > 0)
inj_z = np.where(np.isnan(inj_z), np.nanmedian(inj_z), inj_z)
# home-workers are neither commuters nor jobs anyone travels to
rowP = P.W.values * np.clip(stay_pt, 0, 1) * (1 - rate_z[p_z])
colP = P.J.values * np.clip(inj_z[p_z], 0, 1) * (1 - rate_z[p_z])
colP *= rowP.sum() / colP.sum()
R2 = np.bincount(p_z, rowP, n); C2 = np.bincount(p_z, colP, n)
log(f"2026 in-box commuters {rowP.sum():,.0f} (of {P.W.sum():,.0f} employed residents)")

# ------------------------------------------------------------ SA2 x SA2 for 2026
zx = np.bincount(p_z, px * (P.W.values + 1e-6), n) / np.bincount(p_z, P.W.values + 1e-6, n)
zy = np.bincount(p_z, py * (P.W.values + 1e-6), n) / np.bincount(p_z, P.W.values + 1e-6, n)
jx = np.bincount(p_z, px * (P.J.values + 1e-6), n) / np.bincount(p_z, P.J.values + 1e-6, n)
jy = np.bincount(p_z, py * (P.J.values + 1e-6), n) / np.bincount(p_z, P.J.values + 1e-6, n)


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


n21 = B_all.sum(1); m21 = B_all.sum(0)
a_row = np.clip(np.divide(n21, RELIABLE * R2, out=np.ones(n), where=R2 > 0), 0, 1)
rel = (a_row >= 1) & (n21 >= 50)
NBr = neighbour_rows(B_all, np.maximum(n21, 1e-9), zx, zy, rel)
own = np.divide(B_all, n21[:, None], out=np.zeros_like(B_all), where=n21[:, None] > 0)
S2 = (a_row[:, None] * own + (1 - a_row[:, None]) * NBr) * R2[:, None]
log(f"growth origins: {(a_row < 1).sum()} SA2s holding {R2[a_row < 1].sum():,.0f} commuters borrow neighbour patterns")
sc_ = S2.sum(0)
a_col = np.clip(np.divide(m21, RELIABLE * C2, out=np.ones(n), where=C2 > 0), 0, 1)
relc = (a_col >= 1) & (m21 >= 50)
NBc = neighbour_rows(S2.T, np.maximum(sc_, 1e-9), jx, jy, relc & (sc_ > 0)).T
ownc = np.divide(S2, sc_[None, :], out=np.zeros_like(S2), where=sc_[None, :] > 0)
S2 = (a_col[None, :] * ownc + (1 - a_col[None, :]) * NBc) * C2[None, :]
log(f"growth destinations: {(a_col < 1).sum()} SA2s holding {C2[a_col < 1].sum():,.0f} jobs borrow neighbour patterns")
for it in range(300):
    rs = S2.sum(1); S2 *= np.divide(R2, rs, out=np.zeros(n), where=rs > 0)[:, None]
    cs = S2.sum(0); S2 *= np.divide(C2, cs, out=np.zeros(n), where=cs > 0)[None, :]
zd = np.hypot(zx[:, None] - jx[None, :], zy[:, None] - jy[None, :])
log(f"SA2 IPF: row error {np.abs(S2.sum(1) - R2).sum() / R2.sum():.4%}; mean SA2-centroid distance "
    f"2021 {np.average(zd, weights=B_all):.2f} km -> 2026 {np.average(zd, weights=S2):.2f} km")

# ------------------------------------------------------------ point seed
S2n = np.divide(S2, S2.sum(1, keepdims=True), out=np.zeros_like(S2), where=S2.sum(1, keepdims=True) > 0)
jobs_in = [np.nonzero(work & (p_z == z))[0] for z in range(n)]
jw = [colP[q] / max(colP[q].sum(), 1e-9) for q in jobs_in]
hs = np.nonzero(rowP > 0)[0]
PATT = np.zeros((len(hs), n))
for k, h in enumerate(hs):
    ev = A_pts[h].sum()
    alpha = min(1.0, ev / (RELIABLE * rowP[h]))
    lam = max(SMOOTH, 1 - alpha)
    PATT[k] = (1 - lam) * (A_pts[h] / ev if ev > 0 else 0) + lam * S2n[p_z[h]]
has_jobs = np.array([len(j) > 0 for j in jobs_in])
USE = (PATT >= MIN_SHARE) & (S2[p_z[hs]] > 0) & has_jobs[None, :]
# every SA2 pair with commuters needs somebody to carry them: where no SA1 of the
# origin SA2 reaches MIN_SHARE, the pair is offered to all of them
covered = np.zeros((n, n), bool)
np.logical_or.at(covered, p_z[hs], USE)
gap = (S2 > 0) & ~covered & has_jobs[None, :]
USE |= gap[p_z[hs]] & (PATT > 0)
log(f"seed: {USE.sum():,} SA1-to-SA2 cells, {gap.sum():,} thin SA2 pairs ({S2[gap].sum():,.0f} commuters) "
    f"spread across their whole origin SA2")
parts_r, parts_c, parts_b, parts_v = [], [], [], []
for k, h in enumerate(hs):
    z = p_z[h]; patt = PATT[k]
    ds = np.nonzero(USE[k])[0]
    if not len(ds):
        continue
    qp = np.concatenate([jobs_in[d] for d in ds]); qw = np.concatenate([jw[d] for d in ds])
    lens = np.array([len(jobs_in[d]) for d in ds])
    dist = np.hypot(px[h] - px[qp], py[h] - py[qp])
    w = qw * np.exp(-dist / BETA_IN)
    starts = np.r_[0, np.cumsum(lens)[:-1]]
    bsum = np.add.reduceat(w, starts)
    val = w * np.repeat(patt[ds] * rowP[h] / np.maximum(bsum, 1e-30), lens)
    parts_r.append(np.full(len(qp), h, np.int32)); parts_c.append(qp.astype(np.int32))
    parts_b.append((z * n + np.repeat(ds, lens)).astype(np.int64)); parts_v.append(val)
er = np.concatenate(parts_r); ec = np.concatenate(parts_c)
eb = np.concatenate(parts_b); ev = np.concatenate(parts_v).astype(np.float64)
del parts_r, parts_c, parts_b, parts_v
btot = S2.ravel()
log(f"point-level entries {len(ev):,}")
for it in range(150):
    rs = np.bincount(er, ev, NP); ev *= np.divide(rowP, rs, out=np.zeros(NP), where=rs > 0)[er]
    cs = np.bincount(ec, ev, NP); ev *= np.divide(colP, cs, out=np.zeros(NP), where=cs > 0)[ec]
    bs = np.bincount(eb, ev, n * n); ev *= np.divide(btot, bs, out=np.zeros(n * n), where=bs > 0)[eb]
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
    f"row fit {np.abs(row_m - rowP).sum()/rowP.sum():.3%}  col fit {np.abs(col_m - colP).sum()/colP.sum():.3%}")

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
