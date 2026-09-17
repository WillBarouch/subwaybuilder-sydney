#!/bin/bash
# Named OSM features used to place campuses, venues, beaches and hospitals (input to osm_poi_index.py).
set -euo pipefail
cd "$(dirname "$0")/.."
osmium extract --strategy complete_ways --bbox 150.45,-34.67,151.53,-33.29 \
  data/osm/new_south_wales-latest.osm.pbf -o data/osm/syd_box.osm.pbf --overwrite
osmium tags-filter data/osm/syd_box.osm.pbf \
  nwr/amenity=university,college,hospital,casino,theatre,arts_centre,conference_centre,marketplace \
  nwr/leisure=stadium,sports_centre,park,water_park,nature_reserve,marina,racetrack,golf_course \
  nwr/tourism=attraction,museum,zoo,theme_park,aquarium,gallery,viewpoint nwr/natural=beach \
  nwr/shop=mall,department_store nwr/military nwr/landuse=military nwr/aeroway=terminal,aerodrome \
  nwr/boundary=national_park,protected_area nwr/building=university,stadium,hospital \
  -o data/osm/syd_poi.osm.pbf --overwrite
osmium export data/osm/syd_poi.osm.pbf -f geojsonseq -o data/osm/syd_poi.geojsonseq --overwrite \
  --geometry-types=point,polygon,linestring
python scripts/osm_poi_index.py
