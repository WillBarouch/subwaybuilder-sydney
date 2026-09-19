"""Tighten description.md: depot writes a page nobody can scroll.

Three passes:
  1. The 572-row Schools table becomes a breakdown by sector plus the largest
     sites. Figures come from the demand file itself (via the points schema),
     so they agree with the totals depot puts in the section header.
  2. Special demand categories are grouped under Infrastructure / Education /
     Attractions, as the popular maps do, instead of 17 loose rows.
  3. The tail is rewritten: a one-line summary up top, five short methodology
     points visible, and the full methodology and the source list folded into
     <details>. depot's stock "Water Depths" blurb (GEBCO, flat -5 m) is
     replaced, because this map does neither.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from mapconfig import CITY, BBOX as _BBOX, CITY_DIR, OA_CENTROIDS, SPECIAL_DIR
import json, re, collections, os

DESC = f'{CITY_DIR}/description.md'
src = open(DESC).read()

schema = json.load(open(f'{CITY_DIR}/.railyard_map/special_demand_points.json'))['points']
pts = {p['id']: p for p in json.load(open(f'{CITY_DIR}/demand_data.json'))['points']}

LABEL = {'elementary': 'Primary', 'middle_school': 'Middle',
         'high_school': 'Secondary', 'consolidated': 'All-through',
         'special_support': 'Special / alternative provision',
         'junior_high': 'Junior high'}

GROUPS = [('Infrastructure', ['Airports', 'Hospitals']),
          ('Education', ['Schools', 'Universities']),
          ('Attractions', None)]          # None: everything else, in depot's order

SUMMARY_LINE = ("<p>Greater Sydney end to end: the Central Coast, the Blue Mountains foothills, "
                "the Illawarra and Western Sydney International. Commutes come from the 2021 Census, "
                "where each SA1's workers work, grown to 2026, on one demand point per ABS "
                "SA1.</p>\n")

WATER_FEATURE = ("<li><strong>Water Depths</strong> — A water depth index built from a ~50 m "
                 "bathymetry composite (NSW multibeam and marine lidar, Wilson &amp; Power's "
                 "harbour and estuary grids, GEBCO offshore) keeps track out of the water and "
                 "gives the harbour its real depth; the in-game ocean foundations layer "
                 "visualizes it.</li>")


WALK_FEATURE = ("<li><strong>Walking Network</strong> — A walk graph of every street, footpath, "
                "shared path and set of steps (from OpenStreetMap), so commuters walk to stations along "
                "real routes and around rivers and bays rather than in straight lines (Subway Builder "
                "1.7.17+). Footpaths also show on the map.</li>")


def group_categories(text):
    """Put the per-category <details> blocks under three headings."""
    head, rest = text.split("<h2>Special Demand</h2>\n", 1)
    body, tail = rest.split("<br>\n", 1)
    blocks = re.findall(r"<details>\n<summary>(.*?) — .*?</details>\n", body, re.S)
    raw = re.findall(r"<details>\n<summary>.*?</details>\n", body, re.S)
    assert len(raw) == len(blocks), "category blocks not parsed"
    taken, out = set(), []
    for title, names in GROUPS:
        picked = [b for b, n in zip(raw, blocks) if (n in names if names else n not in taken)]
        if names:
            taken.update(names)
        if picked:
            out.append(f"<h3>{title}</h3>\n" + "\n".join(picked))
    return head + "<h2>Special Demand</h2>\n" + "\n".join(out) + "\n<br>\n" + tail


def rewrite_tail(text):
    """Short visible methodology; the long version and the sources fold away."""
    def stat(label):
        m = re.search(rf"<strong>{re.escape(label)}</strong></td><td align=\"right\">([\d,.]+)", text)
        return m.group(1)

    head, tail = text.split("<h2>Additional Features</h2>\n", 1)
    head = head.replace("</h3>\n", "</h3>\n" + SUMMARY_LINE, 1)
    feats = tail.split("<h2>Methodology</h2>", 1)[0]
    feats = re.sub(r"<li><strong>Water Depths</strong>.*?</li>", WATER_FEATURE, feats, flags=re.S)
    if os.path.exists(f"{CITY_DIR}/walk_graph.bin.gz"):
        feats = feats.replace("</ul>", WALK_FEATURE + "\n</ul>", 1)
    method = re.search(r"<h2>Methodology</h2>\n<ul>\n(.*?)</ul>\n", tail, re.S).group(1)
    sources = re.search(r"<h2>Data Sources</h2>\n<ul>\n(.*?)</ul>\n", tail, re.S).group(1)
    method = method.replace("<p>", "").replace("</p>", "")
    n_sources = sources.count("<li>")
    licence = "<h2>License</h2>\n" + tail.split("<h2>License</h2>\n", 1)[1]

    short = [
        f"<li><strong>Commutes.</strong> 2021 Census flows from each SA1 to each SA2 of work, "
        f"fitted to TfNSW's official 2026 projections of where people live and work, on one "
        f"demand point per ABS SA1 ({stat('Demand Points')} points). "
        f"{stat('Modeled Normal Demand')} commuters, mean road commute "
        f"{stat('Mean Commute Distance (km)')} km.</li>",
        f"<li><strong>Special demand</strong> ({stat('Modeled Special Demand')} trips a day) covers "
        f"visitors, students and passengers only; staff are already counted as commuters.</li>",
        "<li><strong>Students and pupils</strong> come from university and school enrolments, and "
        "live where the 2021 Census says people attending that kind of institution live.</li>",
        "<li><strong>Water depths</strong> come from NSW survey bathymetry rather than the global "
        "grid, so the harbour and the rivers keep their channels.</li>",
        "<li><strong>Worth knowing:</strong> the ABS randomly adjusts small census counts, "
        "people who usually work at home are estimated from 2011 rates, and campus splits and "
        "visitor numbers for beaches, parks and shopping centres are estimates.</li>",
    ]

    return (head + "<h2>Additional Features</h2>\n" + feats
            + "<h2>Methodology</h2>\n<ul>\n" + "\n".join(short) + "\n</ul>\n\n"
            + "<details>\n<summary>Full methodology, source by source</summary>\n\n<ul>\n"
            + method + "</ul>\n\n</details>\n\n"
            + f"<details>\n<summary>Data sources ({n_sources})</summary>\n\n<ul>\n"
            + sources.replace("<p>", "").replace("</p>", "") + "</ul>\n\n</details>\n\n"
            + licence)


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
               f'<p>{n_sites:,} secondary, selective and special schools from ACARA 2025 '
               f'enrolments, summarised by sector rather than listed '
               f'individually.</p>\n\n' + '\n'.join(rows) + '\n\n</details>')

pat = re.compile(r'<summary>Schools — [\d,]+</summary>.*?</details>', re.S)
new, n = pat.subn(replacement, src, count=1)
assert n == 1, "schools block not found"
new = group_categories(new)
new = rewrite_tail(new)
open(DESC, 'w').write(new)
print(f"schools: {n_sites:,} sites, {total:,} demand -> summary by phase + top 15")
print(f"description.md: {len(src)/1024:.0f} KB -> {len(new)/1024:.0f} KB")
