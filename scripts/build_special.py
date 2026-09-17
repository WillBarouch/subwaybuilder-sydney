"""Special demand for SYD: universities, TAFE, secondary schools, airports,
and attractions / venues / beaches / shopping / hospitals.

Only non-employment trips are modelled -- staff at all of these places are
already jobs in TZP24. For the same reason military bases (in the v1 map) are
left out: their personnel are workplace jobs too.

Homes for students and pupils are chosen later (assemble_demand.py) from the
2021 Census count of people attending that kind of institution in each SA1
(G15), grown to 2026, with a distance decay calibrated per group
(calibrate_special_exponents.py). Each POI carries its `home_group`.

Outputs build/special_SYD/{universities,schools,airports,entertainment}.json
and data/home_weights_SYD.parquet.
"""
import sys, os, json, io, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, SPECIAL_DIR
import numpy as np, pandas as pd

SRC = 'data/special_src'
os.makedirs(SPECIAL_DIR, exist_ok=True)
inbox = lambda lon, lat: BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]
_codes = set()
def code_of(s):
    """Short unique id: initials of each word plus the tail of the last word."""
    w = [x for x in ''.join(c if c.isalnum() else ' ' for c in s).split() if x]
    base = (''.join(x[0] for x in w[:-1]) + w[-1][:6]).upper()[:10]
    c, k = base, 2
    while c in _codes:
        c, k = f"{base[:9]}{k}", k + 1
    _codes.add(c)
    return c

# =================================================================== home weights
P = pd.read_parquet(f'data/points_{CITY}.parquet')
mb = pd.read_parquet(f'data/mb_points_{CITY}.parquet')
mba = pd.read_parquet(f'data/mb_{CITY}.parquet').set_index('MB')
mb['wkf21'] = mb.MB.map(mba.wkf21_mb)
g = mb.groupby('SA1')[['wkf_mb', 'wkf21']].sum()
growth = (g.wkf_mb / g.wkf21.replace(0, np.nan)).clip(0.5, 4).fillna(1.0)
z = zipfile.ZipFile('data/abs/2021_GCP_SA1_NSW.zip')
g15 = pd.read_csv(z.open([n for n in z.namelist() if n.endswith('G15_NSW_SA1.csv')][0]))
g15 = g15.set_index(g15.SA1_CODE_2021.astype(np.int64))
w = pd.DataFrame({
    'sec_gov': g15.Secondary_Government_P,
    'sec_cath': g15.Secondary_Catholic_P,
    'sec_ind': g15.Secondary_Other_non_Govt_P,
    'sec_all': g15.Secondary_Tot_Secondary_P,
    'uni': g15.Tert_Uni_oth_h_edu_Ft_15_24_P + g15.Tert_Uni_oth_h_edu_Ft_25_ov_P
           + 0.5 * (g15.Tert_Uni_oth_h_edu_Pt_15_24_P + g15.Tert_Uni_oth_h_edu_Pt_25_ov_P),
    'voc': g15.Tert_Voc_edu_Tot_P,
})
homes = P[P.kind != 'work'][['pid', 'SA1']].copy()
hw = w.reindex(homes.SA1).fillna(0).mul(growth.reindex(homes.SA1).fillna(1.0).values, axis=0)
hw.index = homes.pid.values
hw.index.name = 'pid'
hw.reset_index().to_parquet(f'data/home_weights_{CITY}.parquet')
print("home weights (2026, in box):", {k: f"{v:,.0f}" for k, v in hw.sum().items()})

# No merge_within on campuses, venues or hospitals: depot folds every ordinary
# demand point inside the radius into the special point, jobs and commuters
# included. In the CBD a 250 m radius swallowed ~90,000 office workers into
# 'Private colleges - CBD north' (593k commuters across 53 points in all).
# =================================================================== universities
# DoE 2024 enrolments by attendance mode; on-campus equivalent = full-time
# internal + 0.6 x full-time multi-modal + half of the part-time equivalents.
ATTEND = 0.60          # share of on-campus students on campus on a given weekday
mt = json.load(open(f'{SRC}/he2024_mode_type.json'))
onc = collections.Counter()
for k, v in mt.items():
    inst, mode, typ = k.split('|')
    f = {('Internal', 'Full-time'): 1.0, ('Multi-modal', 'Full-time'): 0.6,
         ('Internal', 'Part-time'): 0.5, ('Multi-modal', 'Part-time'): 0.3}.get((mode, typ), 0.0)
    onc[inst] += v * f
U, T_ = 'university', 'technical_college'
# institution -> (share of students living in college/halls, [(campus, lon, lat, share)])
# Campus shares are estimates from each university's published campus profiles.
CAMPUS = {
 'The University of Sydney': (0.05, [
    ('USyd Camperdown/Darlington', 151.18941, -33.88891, 0.93),
    ('Sydney Conservatorium', 151.21439, -33.86360, 0.02),
    ('USyd Westmead', 150.98800, -33.80400, 0.03),
    ('USyd Camden', 150.65125, -34.02876, 0.02)]),
 'University of New South Wales': (0.06, [
    ('UNSW Kensington', 151.23124, -33.91760, 0.92),
    ('UNSW Paddington', 151.22027, -33.88384, 0.04)]),          # rest: UNSW Canberra
 'University of Technology Sydney': (0.03, [
    ('UTS Ultimo', 151.20033, -33.88325, 1.00)]),
 'Macquarie University': (0.06, [
    ('Macquarie University', 151.11271, -33.77420, 0.96),
    ('Macquarie City Campus', 151.20660, -33.86580, 0.04)]),
 'Western Sydney University': (0.03, [
    ('WSU Parramatta South', 151.02550, -33.81150, 0.20),
    ('WSU Parramatta City', 151.00380, -33.81600, 0.16),
    ('WSU Kingswood', 150.73012, -33.76833, 0.16),
    ('WSU Campbelltown', 150.79140, -34.06979, 0.14),
    ('WSU Bankstown City', 151.03050, -33.91760, 0.10),
    ('WSU Liverpool City', 150.92420, -33.92150, 0.07),
    ('WSU Sydney City', 151.21050, -33.87450, 0.05),
    ('WSU Hawkesbury', 150.75369, -33.61831, 0.04),
    ('WSU Westmead', 150.98706, -33.80705, 0.03),
    ('WSU Sydney Olympic Park', 151.06940, -33.84740, 0.03),
    ('WSU Nirimba', 150.87458, -33.72404, 0.02)]),
 'University of Wollongong': (0.08, [
    ('UOW Wollongong', 150.87835, -34.40505, 0.80),
    ('UOW Innovation Campus', 150.89867, -34.40163, 0.03),
    ('UOW Sydney CBD', 151.20650, -33.86700, 0.04),
    ('UOW Liverpool', 150.92360, -33.91970, 0.04),
    ('UOW Southern Sydney', 151.05214, -34.04269, 0.02)]),      # rest: Shoalhaven, Bega, Batemans Bay
 'The University of Newcastle': (0.02, [
    ('UON Central Coast (Ourimbah)', 151.37835, -33.35789, 0.06),
    ('UON Gosford', 151.34170, -33.42750, 0.02)]),              # rest: Newcastle, Port Macquarie
 'Australian Catholic University': (0.01, [
    ('ACU North Sydney', 151.20326, -33.83749, 0.26),
    ('ACU Strathfield', 151.07707, -33.87557, 0.20),
    ('ACU Blacktown', 150.90640, -33.76860, 0.03)]),            # rest: other states
 'The University of Notre Dame Australia': (0.01, [
    ('Notre Dame Broadway', 151.19900, -33.88350, 0.25),
    ('Notre Dame Darlinghurst', 151.22100, -33.87950, 0.13)]),  # rest: Fremantle, Broome
 'Torrens University Australia': (0.01, [
    ('Torrens Sydney (Surry Hills)', 151.20890, -33.88450, 0.30)]),
 'Victoria University': (0.0, [('VU Sydney', 151.20290, -33.87520, 0.15)]),
 'Charles Darwin University': (0.0, [('CDU Sydney', 151.20560, -33.87900, 0.15)]),
}
# Non-university higher-education providers in NSW (Section 2.5): 97,587
# students, overwhelmingly international students at CBD and Parramatta
# colleges. No per-provider split is published; clustered by precinct.
NUHEI = 97_587 * 0.80
NUHEI_CAMPUS = [('Private colleges - CBD north', 151.20700, -33.86600, 0.30),
                ('Private colleges - CBD south / Haymarket', 151.20400, -33.87900, 0.30),
                ('Private colleges - Parramatta', 151.00450, -33.81550, 0.08),
                ('Private colleges - North Sydney', 151.20700, -33.83900, 0.05),
                ('ICMS Manly', 151.29350, -33.79850, 0.03)]
unis = []
def add_uni(name, lon, lat, students, subtype):
    if not inbox(lon, lat) or students < 50: return
    unis.append({'type': subtype, 'name': name, 'code': code_of(name), 'location': [lon, lat],
                 'total_capacity': int(round(students)), 'pop_size': int(min(200, max(20, students / 12))),
                 'max_distance': 60_000, 'home_group': 'uni'})
for inst, (dorm, camps) in CAMPUS.items():
    base = onc[next(k for k in onc if k.startswith(inst))] * ATTEND * (1 - dorm)
    for name, lon, lat, sh in camps:
        add_uni(name, lon, lat, base * sh, U)
for name, lon, lat, sh in NUHEI_CAMPUS:
    add_uni(name, lon, lat, NUHEI * ATTEND * sh, T_)

# TAFE NSW: no campus enrolments are published. Vocational students living in
# the box (Census G15, grown to 2026) x weekday attendance, split by campus
# size class (Ultimo is the flagship; others large / medium / small).
TAFE_ATTEND = 0.30
TAFE = [('TAFE NSW Ultimo', 151.19931, -33.88216, 5), ('TAFE NSW Randwick', 151.23291, -33.90592, 2),
        ('TAFE NSW Kingswood', 150.73762, -33.76461, 2), ('TAFE NSW Campbelltown', 150.79709, -34.06780, 2),
        ('TAFE NSW Wollongong', 150.88524, -34.40822, 2), ('TAFE NSW Lidcombe', 151.04716, -33.87928, 2),
        ('TAFE NSW Granville', 151.00474, -33.83633, 2), ('TAFE NSW Meadowbank', 151.09170, -33.81482, 2),
        ('TAFE NSW Gosford', 151.34516, -33.42841, 2), ('TAFE NSW Hornsby', 151.09678, -33.69917, 2),
        ('TAFE NSW Liverpool', 150.92990, -33.92196, 2), ('TAFE NSW Wetherill Park', 150.91455, -33.84956, 2),
        ('TAFE NSW Loftus', 151.05214, -34.04269, 1), ('TAFE NSW St George', 151.13834, -33.96512, 1),
        ('TAFE NSW Mount Druitt', 150.82618, -33.76944, 1), ('TAFE NSW Blacktown', 150.91056, -33.77296, 1),
        ('TAFE NSW Northern Beaches', 151.26293, -33.76957, 1), ('TAFE NSW Enmore', 151.17285, -33.90295, 1),
        ('TAFE NSW Nirimba', 150.87350, -33.72296, 1), ('TAFE NSW Miller', 150.87348, -33.92600, 1),
        ('TAFE NSW Padstow', 151.02566, -33.94712, 1), ('TAFE NSW Baulkham Hills', 150.99276, -33.74847, 1),
        ('TAFE NSW Gymea', 151.08207, -34.03100, 1), ('TAFE NSW Shellharbour', 150.83913, -34.56102, 1),
        ('TAFE NSW Yallah', 150.77275, -34.52437, 1), ('TAFE NSW Petersham', 151.17460, -33.87378, 0.5),
        ('TAFE NSW Macquarie Fields', 150.89263, -33.98375, 0.5), ('TAFE NSW Castle Hill', 150.97520, -33.72411, 0.5),
        ('TAFE NSW Richmond', 150.75488, -33.61149, 0.5), ('TAFE NSW Penrith', 150.69747, -33.75166, 0.5),
        ('TAFE NSW West Wollongong', 150.88588, -34.42925, 0.5)]
voc_total = hw.voc.sum() * TAFE_ATTEND
wsum = sum(t[3] for t in TAFE)
for name, lon, lat, wt in TAFE:
    add_uni(name, lon, lat, voc_total * wt / wsum, 'junior_college')
    unis[-1]['home_group'] = 'voc'
json.dump(unis, open(f'{SPECIAL_DIR}/universities.json', 'w'), ensure_ascii=False, indent=1)
print(f"universities/colleges: {len(unis)} points, {sum(p['total_capacity'] for p in unis):,} daily students")

# =================================================================== schools
ATTEND_SCH = 0.88      # NSW attendance rate
loc = pd.read_excel(f'{SRC}/acara_location_2025.xlsx', sheet_name=1)
grd = pd.read_excel(f'{SRC}/acara_grades_2025.xlsx', sheet_name=1)
prof = pd.read_excel(f'{SRC}/acara_profile_2025.xlsx', sheet_name=1)
nsw = pd.read_csv(f'{SRC}/nsw_public_schools.csv', encoding='latin-1')
sel = dict(zip(nsw.AgeID, nsw.Selective_school))
s = loc.merge(grd[['ACARA SML ID'] + [f'Year {k} Enrolments' for k in range(7, 13)]], on='ACARA SML ID', how='left') \
       .merge(prof[['ACARA SML ID', 'Total Enrolments']], on='ACARA SML ID', how='left')
s = s[(s.State == 'NSW') & s.Longitude.between(BBOX[0], BBOX[2]) & s.Latitude.between(BBOX[1], BBOX[3])]
s['secondary'] = s[[f'Year {k} Enrolments' for k in range(7, 13)]].apply(pd.to_numeric, errors='coerce').fillna(0).sum(1)
schools = []
for _, r in s.iterrows():
    special = r['Special school'] == 1
    te = pd.to_numeric(r['Total Enrolments'], errors='coerce')
    n = (0.0 if pd.isna(te) else float(te)) if special else float(r.secondary)
    daily = n * ATTEND_SCH
    if daily < 30: continue
    sector = str(r['School Sector'])
    if special:
        grp, sub = 'special', 'special_support'
    elif sector.startswith('Gov'):
        grp = 'sec_sel' if sel.get(int(r['Location AGE ID']) if pd.notna(r['Location AGE ID']) else -1) == 'Fully Selective' else 'sec_gov'
        sub = 'high_school'
    elif sector.startswith('Cath'):
        grp, sub = 'sec_cath', 'high_school'
    else:
        grp, sub = 'sec_ind', 'high_school'
    if str(r['School Type']) == 'Combined' and not special:
        sub = 'consolidated'
    schools.append({'type': sub, 'name': str(r['School Name']).strip(), 'code': f"S{r['ACARA SML ID']}",
                    'location': [round(float(r.Longitude), 6), round(float(r.Latitude), 6)],
                    'total_capacity': int(round(daily)), 'pop_size': int(min(200, max(10, daily / 8))),
                    'max_distance': 40_000, 'home_group': grp})
json.dump(schools, open(f'{SPECIAL_DIR}/schools.json', 'w'), ensure_ascii=False, indent=1)
print(f"schools: {len(schools)} points, {sum(p['total_capacity'] for p in schools):,} daily pupils  "
      + str(collections.Counter(p['home_group'] for p in schools)))

# =================================================================== airports
# Sydney Airport 2025: 42.54M passengers, 17.17M international (T1),
# 25.37M domestic and regional (T2 Virgin/Jetstar/Rex, T3 Qantas).
# WSI (opens 25 Oct 2026) at its Stage 1 capacity of 10M a year.
AIR = [('Sydney Airport T1 International', 'international_terminal', 151.1660, -33.9373, 17_170_000, 0.12),
       ('Sydney Airport T2 Domestic', 'domestic_terminal', 151.1796, -33.9353, 25_370_000 * 0.55, 0.06),
       ('Sydney Airport T3 Domestic', 'domestic_terminal', 151.1793, -33.9324, 25_370_000 * 0.45, 0.10),
       ('Western Sydney International', 'international_terminal', 150.7207, -33.8875, 10_000_000, 0.03),
       ('Shellharbour Airport', 'domestic_terminal', 150.7890, -34.5640, 120_000, 0.0)]
air = [{'type': t, 'name': n, 'code': code_of(n), 'location': [lo, la],
        'total_capacity': int(round(a / 365 * (1 - tr))), 'pop_size': 200 if a > 1e6 else 50,
        'merge_within': 400, 'max_distance': 100_000} for n, t, lo, la, a, tr in AIR]
json.dump(air, open(f'{SPECIAL_DIR}/airports.json', 'w'), indent=1)
for p in air: print(f"  {p['name']:<34} {p['total_capacity']:>7,}/day")
