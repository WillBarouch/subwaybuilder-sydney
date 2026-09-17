"""Name -> location index of OSM features relevant to special demand.

Each feature keeps its representative point, area and key tags, so the
special-demand scripts can look things up by name (or by tag + nearest point)
instead of hard-coding coordinates.
"""
import json
import geopandas as gpd
from shapely.geometry import shape

rows = []
for line in open('data/osm/syd_poi.geojsonseq'):
    line = line.strip().lstrip('\x1e')
    if not line: continue
    f = json.loads(line)
    p = f['properties']; g = shape(f['geometry'])
    if not p.get('name'): continue
    rp = g.representative_point() if g.geom_type != 'Point' else g
    rows.append({'name': p['name'], 'lon': round(rp.x, 6), 'lat': round(rp.y, 6),
                 'area_m2': 0.0 if g.geom_type in ('Point', 'LineString') else
                            gpd.GeoSeries([g], crs=4326).to_crs(3308).area.iloc[0],
                 **{k: p[k] for k in ('amenity', 'leisure', 'tourism', 'natural', 'shop', 'military',
                                      'landuse', 'aeroway', 'boundary', 'building', 'operator') if k in p}})
json.dump(rows, open('data/special_src/osm_poi_index.json', 'w'), ensure_ascii=False)
print(len(rows), 'named features')
