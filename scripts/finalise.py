"""config.json and description.md for the SYD map (registry id `sydney`, v2)."""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
import numpy as np
from depot.demand import DemandData

ap = argparse.ArgumentParser()
ap.add_argument('--name', default='Sydney')
ap.add_argument('--creator', default='willbarouch')
ap.add_argument('--version', default='2.0.0')
ap.add_argument('--map-id', default='sydney')
a = ap.parse_args()

# headline numbers straight from the routed demand, so the text never goes stale
dd = json.load(open(f'{CITY_DIR}/demand_data.json'))
com = [p for p in dd['pops'] if p['id'].isdigit()]
sz = np.array([p['size'] for p in com], float)
km = np.array([p['drivingDistance'] for p in com], float) / 1000
order = np.argsort(km)
commuters = int(sz.sum())
mean_road = float(np.average(km, weights=sz))
median_road = float(km[order][np.searchsorted(np.cumsum(sz[order]), sz.sum() / 2)])
special = int(sum(p['size'] for p in dd['pops'] if not p['id'].isdigit()))

d = DemandData(f'{CITY_DIR}/demand_data.json', CITY, bbox=BBOX, outputdir=CITY_DIR, verb=True)
d.create_config(
    name=a.name, bbox=BBOX, creator=a.creator, version=a.version, country="AU",
    description=("Greater Sydney from Gosford and the Central Coast to Wollongong and Shellharbour, "
                 "west to Springwood, including Western Sydney International. Commutes come from "
                 "Transport for NSW's travel-zone journey-to-work data grown to 2026 with its "
                 "official projections, on one demand point per ABS SA1."),
    initial_view_state=[151.2137, -33.8581],
)

METHODOLOGY = [
 """<li>Map files generated with <a href="https://github.com/Subway-Builder-Modded/depot">Depot</a> from OpenStreetMap and Overture building footprints, with railway-station structures removed so stations can be built at existing stations.</li>""",
 """<li><strong>Demand points.</strong> One point per 2021 ABS SA1 (a few hundred homes each), placed on the mesh block nearest the worker-weighted centre, so points sit on housing rather than in parks. Where an SA1's jobs sit more than 500 m from its homes (an industrial estate at one end of a residential SA1), the jobs get their own point.</li>""",
 """<li><strong>Homes and jobs for 2026.</strong> Employed residents and jobs per travel zone come from Transport for NSW's Travel Zone Projections 2024 (TZP24), and are placed onto mesh blocks with TfNSW's own travel-zone-to-mesh-block concordance.</li>""",
 f"""<li><strong>Commute flows.</strong> The finest public commute table for Sydney is TfNSW's Journey to Work 2011, travel zone to travel zone (about 2,500 zones in this map). TfNSW withdrew its 2016 travel-zone release after ABS confidentiality changes. Home-workers are taken out using the table's travel-mode field. The 2011 pattern is fitted to the 2026 home and job totals of every zone. Zones that barely existed in 2011, such as new estates, business parks and the new airport, borrow the pattern of their nearest established zones. Flows are then split onto SA1 points by workers and jobs, and re-fitted so point totals and zone-pair totals both hold. The map carries {commuters:,} commuters with a mean road commute of {mean_road:.1f} km (median {median_road:.1f} km).</li>""",
 """<li><strong>Keeping it playable.</strong> An SA1 matrix has millions of tiny flows. Pops are drawn by systematic sampling in proportion to flow, so long commutes are neither favoured nor dropped, then re-fitted to every point's resident and job totals, SA3-to-SA3 totals and the trip-length distribution.</li>""",
 f"""<li><strong>Special demand</strong> ({special:,} people a day) covers non-work trips only; staff are already counted as jobs, which is also why military bases are not included.</li>""",
 """<li><strong>Universities:</strong> 2024 Department of Education enrolments by institution and attendance mode (online students removed), split across real campuses, with a 60% weekday attendance factor. The campus splits are estimates. Private higher-education colleges (97,587 students in NSW) are grouped into CBD, Parramatta, North Sydney and Manly clusters. TAFE NSW campuses are sized from census vocational students and campus size.</li>""",
 """<li><strong>Secondary schools:</strong> every government, Catholic and independent school with Years 7-12 enrolments from ACARA 2025, plus special schools; primary schools are left out because their pupils overwhelmingly walk.</li>""",
 """<li><strong>Where pupils and students live.</strong> Homes are drawn from the 2021 Census count of people in each SA1 attending that kind of institution: government, Catholic or independent secondary school, TAFE, or university. Distance decay is calibrated per group to a straight-line mean of 3 km (government comprehensive), 5.5 km (Catholic), 8 km (independent), 12 km (fully selective), 7 km (TAFE) and 10 km (university). These targets are judgement calls, not survey measurements.</li>""",
 """<li><strong>Airports:</strong> Sydney Airport's 2025 traffic (42.54 million passengers, 17.17 million international) split across T1, T2 and T3, less transfers. Western Sydney International, which opens to passengers on 25 October 2026, is sized at its Stage 1 capacity of 10 million passengers a year.</li>""",
 """<li><strong>Attractions:</strong> published visitor numbers where available (Darling Harbour 26.4 million and The Rocks 14 million a year, the Opera House precinct, Taronga, Luna Park, Bondi). Stadiums and arenas use capacity times a typical event programme. Beaches, parks and shopping centres are estimates scaled to size and standing, discounted for local walk-in trips. Hospitals count outpatients and visitors at about 2.5 a day per bed.</li>""",
 """<li>Commute distances and times are real driving routes from a local OSRM server.</li>""",
 """<li><strong>Water depths.</strong> Instead of the global 460 m GEBCO grid alone, depths come from a roughly 50 m composite. In priority order: the NSW Government's statewide multibeam and marine-lidar mosaic; Wilson &amp; Power's seamless 10 m grids for Sydney Harbour (including the Parramatta and Lane Cove rivers and Middle Harbour) and for Botany Bay, the Georges River and Port Hacking; their 50 m Hawkesbury grid (Broken Bay, Pittwater, Brisbane Water); and GEBCO for the open ocean. Depth bands are drawn from that grid, lightly smoothed (about 75 m) and built with their holes so neighbouring bands meet exactly, so the harbour reaches its real 40+ m and the rivers keep their channels. Water with no survey data (inland dams, some lagoons) falls back to the shallowest band.</li>""",
]
SOURCES = [
 """<li><a href="https://opendata.transport.nsw.gov.au/dataset/journey-work-jtw-2011">Transport for NSW - Journey to Work 2011, Tables 11 and 19 (travel zone to travel zone)</a></li>""",
 """<li><a href="https://www.transport.nsw.gov.au/data-and-research/reference-information/travel-zone-projections-2024">Transport for NSW - Travel Zone Projections 2024 (population, workforce, employment)</a></li>""",
 """<li><a href="https://opendata.transport.nsw.gov.au/dataset/travel-zones-2021">Transport for NSW - Travel Zones 2011 and 2021, and concordances</a></li>""",
 """<li><a href="https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files">ABS - ASGS Edition 3 mesh blocks and SA1s; Mesh Block Counts 2021</a></li>""",
 """<li><a href="https://www.abs.gov.au/census/find-census-data/datapacks">ABS - 2021 Census General Community Profile, SA1 (G15 type of educational institution)</a></li>""",
 """<li><a href="https://www.acara.edu.au/contact-us/acara-data-access">ACARA - School Profile, School Location and Enrolments by Grade 2025</a></li>""",
 """<li><a href="https://data.nsw.gov.au/data/dataset/nsw-education-nsw-public-schools-master-dataset">NSW Department of Education - public schools master dataset (selective schools)</a></li>""",
 """<li><a href="https://www.education.gov.au/higher-education-statistics/student-data/selected-higher-education-statistics-2024-student-data">Department of Education - Higher Education Statistics 2024 student data</a></li>""",
 """<li><a href="https://www.sydneyairport.com.au/corporate/media/corporate-newsroom/sydney-airport-traffic-and-operational-performance-q4-2025">Sydney Airport - 2025 traffic performance</a></li>""",
 """<li><a href="https://www.pm.gov.au/media/its-official-western-sydney-open-passengers-25-october-and-freight-26-july-2026">Western Sydney International opening dates</a></li>""",
 """<li><a href="https://www.planning.nsw.gov.au/sites/default/files/2025-11/place-management-nsw-luna-park-reserve-trust-annual-report-2024-2025.pdf">Place Management NSW - Annual Report 2024-25</a></li>""",
 """<li><a href="https://data.nsw.gov.au/data/dataset/nsw-bathymetry-sourced-from-multibeam-and-marine-lidar-surveys">NSW DCCEEW - NSW bathymetry sourced from multibeam and marine lidar surveys</a></li>""",
 """<li><a href="https://doi.org/10.1594/PANGAEA.885014">Wilson &amp; Power (2018), seamless bathymetry and topography for Sydney Harbour, Botany and the Hawkesbury River (PANGAEA 885012-885014)</a></li>""",
 """<li><a href="https://www.gebco.net/">GEBCO 2026 global bathymetry grid</a></li>""",
 """<li><a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a></li>""",
 """<li><a href="https://overturemaps.org/">Overture Maps Foundation building footprints</a></li>""",
]
d.create_description(a.map_id, METHODOLOGY, SOURCES)
print(f"wrote {CITY_DIR}/config.json and {CITY_DIR}/description.md  "
      f"(commuters {commuters:,}, mean road {mean_road:.1f} km, special {special:,})")
