"""Collapse the ~5,000-row Schools table in description.md into a summary.

depot lists every special demand point individually. That is right for a map
with a few dozen; here it produces a 648 KB listing page that no reader can
scroll. Schools are replaced with a breakdown by phase plus the largest few
sites; every other category is left exactly as depot generated it.

Figures are taken from the demand file itself (via the points schema), so they
agree with the totals depot puts in the section header.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR, OA_CENTROIDS, SPECIAL_DIR
import json, re, collections

DESC = f'{CITY_DIR}/description.md'
src = open(DESC).read()

schema = json.load(open(f'{CITY_DIR}/.railyard_map/special_demand_points.json'))['points']
pts = {p['id']: p for p in json.load(open(f'{CITY_DIR}/demand_data.json'))['points']}

LABEL = {'elementary': 'Primary', 'middle_school': 'Middle',
         'high_school': 'Secondary', 'consolidated': 'All-through',
         'special_support': 'Special / alternative provision',
         'junior_high': 'Junior high'}

by = collections.defaultdict(lambda: [0, 0])
named = []
for s in schema:
    if s['type'] != 'school':
        continue
    p = pts.get(s['point_id'])
    if not p:
        continue
    dem = p['jobs'] + p['residents']
    r = by[s['sub_type']]
    r[0] += 1; r[1] += dem
    named.append((s['name']['__default__'], dem))

total = sum(v[1] for v in by.values())
n_sites = sum(v[0] for v in by.values())

rows = ['<table style="width: auto">',
        '<tr><th align="left">Phase</th><th align="right">Sites</th>'
        '<th align="right">Modeled Demand</th></tr>']
for k in ['elementary', 'middle_school', 'junior_high', 'high_school',
          'consolidated', 'special_support']:
    if k in by:
        n, dem = by[k]
        rows.append(f'<tr><td align="left">&nbsp;&nbsp;{LABEL[k]}&nbsp;&nbsp;</td>'
                    f'<td align="right">&nbsp;&nbsp;{n:,}&nbsp;&nbsp;</td>'
                    f'<td align="right">&nbsp;&nbsp;{dem:,}&nbsp;&nbsp;</td></tr>')
rows.append('</table>')

rows += ['', '<p>Largest 15 by modeled demand:</p>', '<table style="width: auto">',
         '<tr><th align="left">Name</th><th align="right">Modeled Demand</th></tr>']
for name, dem in sorted(named, key=lambda x: -x[1])[:15]:
    rows.append(f'<tr><td align="left">&nbsp;&nbsp;{name}&nbsp;&nbsp;</td>'
                f'<td align="right">&nbsp;&nbsp;{dem:,}&nbsp;&nbsp;</td></tr>')
rows.append('</table>')

replacement = (f'<summary>Schools — {total:,}</summary>\n\n'
               f'<p>{n_sites:,} individual school sites from the DfE Get Information '
               f'About Schools register, summarised by phase rather than listed '
               f'individually.</p>\n\n' + '\n'.join(rows) + '\n\n</details>')

pat = re.compile(r'<summary>Schools — [\d,]+</summary>.*?</details>', re.S)
new, n = pat.subn(replacement, src, count=1)
assert n == 1, "schools block not found"
open(DESC, 'w').write(new)
print(f"schools: {n_sites:,} sites, {total:,} demand -> summary by phase + top 15")
print(f"description.md: {len(src)/1024:.0f} KB -> {len(new)/1024:.0f} KB")
