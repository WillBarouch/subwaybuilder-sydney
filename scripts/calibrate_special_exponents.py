"""Choose home locations for school, TAFE and university pops with a calibrated
exponential distance decay, instead of depot's power-law gravity.

depot weights each candidate home by residents / d**exponent. Its defaults
(SCH 2.5, UNI 2) put most pupils and a third of students within 1 km, and the
game walks anyone under roughly 3 km by road (found on the BLN build).

Here the weight is census_attendees * exp(-d / beta): candidate homes are
weighted by how many people in that SA1 attend that kind of institution (2021
Census G15, grown to 2026 -- see build_special.py), and beta is bisected per
group so the people-weighted straight-line mean hits the target. Each POI's
pops are drawn by systematic sampling and handed to depot as `required_locs`.

Targets are judgement calls, not survey measurements: government
comprehensive high schools draw locally, Catholic and independent schools
further, fully selective schools metro-wide; university students in Sydney
commonly live far from campus.
"""
import zlib
import numpy as np

# group -> (census weight column, target people-weighted straight-line mean, km)
TARGETS = {
    'sec_gov':  ('sec_gov', 3.0),
    'sec_cath': ('sec_cath', 5.5),
    'sec_ind':  ('sec_ind', 8.0),
    'sec_sel':  ('sec_gov', 12.0),
    'special':  ('sec_all', 6.0),
    'voc':      ('voc', 7.0),
    'uni':      ('uni', 10.0),
}


def _hav(lo, la, lon, lat):
    lo1, la1, lo2, la2 = map(np.radians, (lo, la, lon, lat))
    a = np.sin((la2-la1)/2)**2 + np.cos(la1)*np.cos(la2)*np.sin((lo2-lo1)/2)**2
    return 6371e3 * 2 * np.arcsin(np.sqrt(a))


def _job_capacity(p):
    return p['total_capacity'] - int(p['total_capacity'] * p.get('residential_split', 0.0))


def assign_homes(pois, points, weights, log=print):
    """Set required_locs on every POI with a `home_group`. `points` is the live
    DemandData point list (special points are skipped); `weights` is a
    DataFrame indexed by base point id (int) with the census columns."""
    base = [p for p in points if p['id'].isdigit()]
    lon = np.array([p['location'][0] for p in base])
    lat = np.array([p['location'][1] for p in base])
    ids = np.array([int(p['id']) for p in base])
    W = weights.reindex(ids).fillna(0.0)

    for group, (col, target) in TARGETS.items():
        sel = [p for p in pois if p.get('home_group') == group]
        if not sel:
            continue
        res = W[col].values.astype(float)
        D = np.stack([_hav(*p['location'], lon, lat) for p in sel])        # (n, m) metres
        mw = np.array([p.get('merge_within') or 0 for p in sel])[:, None]
        R = np.where(D > mw, res[None, :], 0.0)
        cap = np.array([_job_capacity(p) for p in sel], float)

        def weights_for(beta_km):
            Wt = R * np.exp(-D / (beta_km * 1000))
            return Wt / np.maximum(Wt.sum(1, keepdims=True), 1e-300)

        def mean_km(beta_km):
            return ((weights_for(beta_km) * D).sum(1) / 1000 * cap).sum() / cap.sum()

        lo, hi = 0.05, 80.0
        for _ in range(40):
            mid = (lo * hi) ** 0.5
            if mean_km(mid) < target: lo = mid
            else: hi = mid
        beta = (lo * hi) ** 0.5
        Wb = weights_for(beta)
        short = [(Wb * (D < t)).sum(1) @ cap / cap.sum() for t in (1000, 2000, 3000)]
        log(f"  {group:9s} beta {beta:5.2f} km  mean {mean_km(beta):4.1f} km  "
            f"<1/2/3 km {short[0]:.0%}/{short[1]:.0%}/{short[2]:.0%}  ({len(sel)} POIs, {cap.sum():,.0f} people)")

        for p, w in zip(sel, Wb):
            cap_p = _job_capacity(p)
            n = max(1, round(cap_p / p['pop_size']))
            rng = np.random.default_rng(zlib.crc32(p['code'].encode()))
            ticks = (rng.random() + np.arange(n)) / n                     # systematic sample
            idx = np.searchsorted(np.cumsum(w), ticks, side='right').clip(0, len(base) - 1)
            p['required_locs'] = [base[i]['location'] for i in idx]
            p['pop_size_req'] = max(1, round(cap_p / n))
