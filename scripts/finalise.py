"""config.json and description.md for the SYD map (registry id `sydney`, v2)."""
import argparse, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, CITY_DIR
import numpy as np
from depot.demand import DemandData

ap = argparse.ArgumentParser()
ap.add_argument('--name', default='Sydney')
ap.add_argument('--creator', default='willbarouch')
ap.add_argument('--version', default='2.2.0')
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
                 "the 2021 Census (where each SA1's workers work) grown to 2026 with Transport for "
                 "NSW's official projections, on one demand point per ABS SA1."),
    initial_view_state=[151.2137, -33.8581],
)

METHODOLOGY = [
 """<li>Map files generated with <a href="https://github.com/Subway-Builder-Modded/depot">Depot</a> from OpenStreetMap and Overture building footprints, with railway-station structures removed so stations can be built at existing stations.</li>""",
 """<li><strong>Demand points.</strong> One point per 2021 ABS SA1 (a few hundred homes each), placed on the mesh block nearest the worker-weighted centre, so points sit on housing rather than in parks. Where an SA1's jobs sit more than 500 m from its homes (an industrial estate at one end of a residential SA1), the jobs get their own point.</li>""",
 """<li><strong>Homes and jobs for 2026.</strong> Employed residents and jobs per travel zone come from Transport for NSW's Travel Zone Projections 2024 (TZP24), and are placed onto mesh blocks with TfNSW's own travel-zone-to-mesh-block concordance.</li>""",
 f"""<li><strong>Commute flows.</strong> From the 2021 Census through ABS TableBuilder: employed people by the SA1 they live in and the SA2 they work in, and by SA2 to SA2. Place of Work is usable despite the lockdown on Census night because the ABS asked people working from home for COVID to give their usual workplace. People who usually work at home can't be separated in these tables, so they are estimated from TfNSW's 2011 Journey to Work travel-mode field and taken out. The SA2-to-SA2 flows are fitted to TfNSW's 2026 home and job totals; the three SA2s at each end that barely existed in 2021 (new estates and the new airport) borrow their nearest established neighbours' patterns. Each SA1 keeps its own pattern of workplaces, blended with its SA2's where the ABS's random perturbation makes small counts unreliable, and flows are split onto job points by jobs and re-fitted so point totals and SA2-pair totals both hold. The map carries {commuters:,} commuters with a mean road commute of {mean_road:.1f} km (median {median_road:.1f} km).</li>"""
 """<li><strong>Keeping it playable.</strong> An SA1 matrix has millions of tiny flows. Pops are drawn by systematic sampling in proportion to flow, so long commutes are neither favoured nor dropped, then re-fitted to every point's resident and job totals, SA3-to-SA3 totals and the trip-length distribution.</li>""",
 f"""<li><strong>Special demand</strong> ({special:,} people a day) covers non-work trips only; staff are already counted as jobs, which is also why military bases are not included.</li>""",
 """<li><strong>Universities:</strong> 2024 Department of Education enrolments by institution and attendance mode (online students removed), split across real campuses, with a 60% weekday attendance factor. The campus splits are estimates. Private higher-education colleges (97,587 students in NSW) are grouped into CBD, Parramatta, North Sydney and Manly clusters. TAFE NSW campuses are sized from census vocational students and campus size.</li>""",
 """<li><strong>Secondary schools:</strong> every government, Catholic and independent school with Years 7-12 enrolments from ACARA 2025, plus special schools; primary schools are left out because their pupils overwhelmingly walk.</li>""",
 """<li><strong>Where pupils and students live.</strong> Homes are drawn from the 2021 Census count of people in each SA1 attending that kind of institution: government, Catholic or independent secondary school, TAFE, or university. Distance decay is calibrated per group to a straight-line mean of 3 km (government comprehensive), 5.5 km (Catholic), 8 km (independent), 12 km (fully selective), 7 km (TAFE) and 10 km (university). These targets are judgement calls, not survey measurements.</li>""",
 """<li><strong>Airports:</strong> Sydney Airport's 2025 traffic (42.54 million passengers, 17.17 million international) split across T1, T2 and T3, less transfers. Western Sydney International, which opens to passengers on 25 October 2026, is sized at its Stage 1 capacity of 10 million passengers a year.</li>""",
 """<li><strong>Attractions:</strong> published visitor numbers where available (Darling Harbour 26.4 million and The Rocks 14 million a year, the Opera House precinct, Taronga, Luna Park, Bondi). Stadiums and arenas use capacity times a typical event programme. Beaches, parks and shopping centres are estimates scaled to size and standing, discounted for local walk-in trips. Hospitals count outpatients and visitors at about 2.5 a day per bed.</li>""",
 """<li>Commute distances and times are real driving routes from a local OSRM server.</li>""",
 """<li><strong>Walking.</strong> Commuters walk to and from stations on a network built from OpenStreetMap: every street except motorways and their ramps, plus footpaths, shared paths, steps and separately mapped sidewalks (which connect about 1,000 km of footpaths that would otherwise be cut off from the streets), minus anything tagged private or no foot access. Only the connected network is kept (98% of walkable length); 99% of people's demand points sit within the game's 250 m snapping distance of it. Points that don't, mostly job sites behind private roads such as defence land and the Kurnell refinery, walk in straight lines as before.</li>""",
 """<li><strong>Water depths.</strong> Instead of the global 460 m GEBCO grid alone, depths come from a roughly 50 m composite. In priority order: the NSW Government's statewide multibeam and marine-lidar mosaic; Wilson &amp; Power's seamless 10 m grids for Sydney Harbour (including the Parramatta and Lane Cove rivers and Middle Harbour) and for Botany Bay, the Georges River and Port Hacking; their 50 m Hawkesbury grid (Broken Bay, Pittwater, Brisbane Water); and GEBCO for the open ocean. Depth bands are drawn from that grid, lightly smoothed (about 75 m) and built with their holes so neighbouring bands meet exactly, so the harbour reaches its real 40+ m and the rivers keep their channels. Water with no survey data (inland dams, some lagoons) falls back to the shallowest band. Swimming pools, fountains and ponds under 500 m², and underground waterways such as the Tank Stream under Pitt Street, don't count as water, so they don't block building.</li>""",
]
SOURCES = [
 """<li><a href="https://www.abs.gov.au/statistics/microdata-tablebuilder/tablebuilder">ABS - 2021 Census TableBuilder: employed persons, SA1 (UR) by SA2 (POW) and SA2 (UR) by SA2 (POW)</a></li>""",
 """<li><a href="https://opendata.transport.nsw.gov.au/dataset/journey-work-jtw-2011">Transport for NSW - Journey to Work 2011, Table 19 (home-worker rates only)</a></li>""",
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
