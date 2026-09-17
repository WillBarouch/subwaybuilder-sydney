"""Enrolments by institution x attendance mode x attendance type (2024) from the
Department of Education's perturbed enrolment pivot table, whose data only lives
in the workbook's pivot cache. Writes data/special_src/he2024_mode_type.json,
which build_special.py uses to drop online students."""
import collections, json, zipfile
from lxml import etree

SRC = 'data/special_src/he2024_pivot.xlsx'
KEEP = ['Sydney', 'New South Wales', 'Macquarie', 'Western Sydney', 'Wollongong', 'Newcastle', 'Catholic',
        'Notre Dame', 'Torrens', 'Technology Sydney', 'Charles Sturt', 'Southern Cross', 'Central Queensland',
        'Victoria University', 'Charles Darwin', 'Federation']

z = zipfile.ZipFile(SRC)
d = etree.fromstring(z.read('xl/pivotCache/pivotCacheDefinition1.xml'))
ns = {'m': d.nsmap[None]}
fields = []
for cf in d.find('m:cacheFields', ns):
    items = cf.find('m:sharedItems', ns)
    fields.append((cf.get('name'), [x.get('v') for x in items] if items is not None and len(items) else None))
names = [f for f, _ in fields]
iI, iY, iM, iT, iC = (names.index(k) for k in
                      ('Institution', 'Year', 'Mode_Of_Attendance', 'Type_Of_Attendance', 'Enrolment Count'))
agg = collections.Counter()
for _, rec in etree.iterparse(z.open('xl/pivotCache/pivotCacheRecords1.xml'), tag='{%s}r' % ns['m']):
    ch = list(rec)
    def val(i):
        e = ch[i]
        return fields[i][1][int(e.get('v'))] if e.tag.endswith('}x') else e.get('v')
    if str(val(iY)) == '2024' and any(k in val(iI) for k in KEEP):
        agg[(val(iI), val(iM), val(iT))] += float(val(iC) or 0)
    rec.clear()
json.dump({'|'.join(k): v for k, v in agg.items()}, open('data/special_src/he2024_mode_type.json', 'w'), indent=0)
print(f"{len(agg)} institution/mode/type rows")
