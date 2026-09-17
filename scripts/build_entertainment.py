"""Attractions, venues, beaches, parks, shopping and hospitals for SYD.

Annual visits:
  * published: Darling Harbour 26.4M and The Rocks ~14M (Placemaking NSW
    2024-25), Luna Park >1M (same report), Sydney Opera House precinct 10.9M,
    Taronga Zoo ~1.5M, Bondi Beach 2.64M tourist visits in 2024 plus locals
  * stadiums and arenas: capacity x typical event programme
  * beaches, parks, shopping centres: estimates scaled to size and standing
  * hospitals: outpatients and visitors, ~2.5 a day per bed (NSW Health bed
    numbers, rounded)

Sizing follows BLN/LDN: annual / 365, discounted where most footfall is local
walk-in or already counted (precincts full of CBD workers, beaches, parks and
shopping). Staff are excluded everywhere -- they are TZP24 jobs.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapconfig import CITY, BBOX, SPECIAL_DIR

# depot's default decay exponents for these types (CNV 3, LIB 2, REL 2) keep
# nearly every visitor within ~2 km -- wrong for a convention centre, the state
# library or a regional temple, whose visitors come from across the region
EXPONENT = {'convention_center': 1.0, 'library': 1.0, 'temple': 1.0}
SHARE = {'shopping_center': 0.20, 'park': 0.40, 'nature_park': 0.30, 'beach': 0.50,
         'precinct': 0.35, 'hospital': 1.0}
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

# (name, depot subtype, discount class or None, annual visits, lon, lat)
V = [
 # --- precincts and icons ---
 ('Darling Harbour',                'cultural_center',  'precinct', 26_400_000, 151.1990, -33.8745),
 ('The Rocks',                      'heritage_site',    'precinct', 14_000_000, 151.2085, -33.8590),
 ('Sydney Opera House',             'theater',          'precinct', 10_900_000, 151.2151, -33.8572),
 ('Barangaroo',                     'cultural_center',  'precinct', 10_000_000, 151.2012, -33.8620),
 ('The Star Sydney',                'casino',           'precinct',  6_000_000, 151.1951, -33.8679),
 ('Sydney Fish Market',             'marketplace',      'precinct',  5_000_000, 151.1907, -33.8744),
 ("Paddy's Markets & Chinatown",    'marketplace',      'precinct',  5_000_000, 151.2034, -33.8798),
 ('Queen Victoria Building',        'shopping_center',  None,        8_000_000 * 0.20, 151.2067, -33.8714),
 ('ICC Sydney',                     'convention_center', None,       1_500_000, 151.1997, -33.8752),
 ('Taronga Zoo',                    'zoo',              None,        1_500_000, 151.2414, -33.8438),
 ('Luna Park Sydney',               'amusement_park',   None,        1_000_000, 151.2098, -33.8473),
 ('Sydney Tower Eye',               'scenic_spot',      None,          800_000, 151.2089, -33.8705),
 ('Art Gallery of NSW',             'art_museum',       None,        1_800_000, 151.2174, -33.8686),
 ('Australian Museum',              'museum',           None,        1_000_000, 151.2133, -33.8743),
 ('Museum of Contemporary Art',     'art_museum',       None,          900_000, 151.2090, -33.8600),
 ('State Library of NSW',           'library',          None,        1_200_000, 151.2130, -33.8662),
 ('Powerhouse Parramatta',          'science_museum',   None,        1_000_000, 151.0077, -33.8155),
 ('Cockatoo Island',                'historic_building', None,         300_000, 151.1722, -33.8476),
 ('Nan Tien Temple',                'temple',           None,          500_000, 150.8486, -34.4666),
 # --- zoos and parks with gates ---
 ('Sydney Zoo',                     'zoo',              None,          800_000, 150.8661, -33.7885),
 ('Featherdale Wildlife Park',      'zoo',              None,          500_000, 150.8843, -33.7658),
 ('Symbio Wildlife Park',           'zoo',              None,          300_000, 150.9688, -34.2053),
 ('Australian Reptile Park',        'zoo',              None,          400_000, 151.2772, -33.4180),
 ('Raging Waters Sydney',           'theme_park',       None,          400_000, 150.9077, -33.8080),
 # --- stadiums and arenas (capacity x events) ---
 ('Accor Stadium',                  'stadium',          None,        1_800_000, 151.0634, -33.8471),
 ('Sydney Cricket Ground',          'stadium',          None,        1_200_000, 151.2247, -33.8914),
 ('Allianz Stadium',                'stadium',          None,        1_000_000, 151.2251, -33.8892),
 ('CommBank Stadium',               'stadium',          None,          800_000, 151.0000, -33.8087),
 ('Qudos Bank Arena',               'arena',            None,        1_000_000, 151.0690, -33.8452),
 ('Sydney Showground',              'events',           None,        1_000_000, 151.0716, -33.8480),
 ('Sydney Olympic Park Aquatic Centre', 'sports_complex', None,        800_000, 151.0672, -33.8503),
 ('Ken Rosewall Arena',             'arena',            None,          150_000, 151.0723, -33.8551),
 ('Entertainment Quarter & Hordern Pavilion', 'arena',  None,        1_000_000, 151.2242, -33.8941),
 ('Royal Randwick Racecourse',      'racetrack',        None,          400_000, 151.2280, -33.9060),
 ('Rosehill Gardens',               'racetrack',        None,          300_000, 151.0262, -33.8239),
 ('Warwick Farm Racecourse',        'racetrack',        None,           80_000, 150.9448, -33.9100),
 ('WIN Stadium',                    'stadium',          None,          200_000, 150.9025, -34.4281),
 ('WIN Entertainment Centre',       'arena',            None,          200_000, 150.9027, -34.4268),
 ('Central Coast Stadium',          'stadium',          None,          200_000, 151.3380, -33.4280),
 ('Penrith Stadium',                'stadium',          None,          300_000, 150.6960, -33.7560),
 ('Brookvale Oval',                 'stadium',          None,          200_000, 151.2710, -33.7660),
 ('Ocean Protect Stadium',          'stadium',          None,          200_000, 151.1406, -34.0384),
 ('Leichhardt Oval',                'stadium',          None,          120_000, 151.1548, -33.8686),
 ('Campbelltown Sports Stadium',    'stadium',          None,          150_000, 150.8290, -34.0610),
 ('Jubilee Stadium',                'stadium',          None,          120_000, 151.1292, -33.9721),
 ('North Sydney Oval',              'stadium',          None,          100_000, 151.2080, -33.8350),
 ('Enmore Theatre',                 'theater',          None,          200_000, 151.1742, -33.8990),
 ('Capitol Theatre',                'theater',          None,          400_000, 151.2064, -33.8795),
 ('State Theatre',                  'theater',          None,          300_000, 151.2075, -33.8709),
 # --- beaches (tourist + local visits) ---
 ('Bondi Beach',                    'beach',            'beach',     4_500_000, 151.2753, -33.8923),
 ('Manly Beach',                    'beach',            'beach',     4_000_000, 151.2889, -33.7977),
 ('Coogee Beach',                   'beach',            'beach',     2_000_000, 151.2579, -33.9208),
 ('Cronulla Beach',                 'beach',            'beach',     2_000_000, 151.1550, -34.0551),
 ('Watsons Bay & The Gap',          'beach',            'beach',     1_500_000, 151.2800, -33.8440),
 ('Terrigal Beach',                 'beach',            'beach',     1_500_000, 151.4439, -33.4450),
 ('Wollongong City & North Beach',  'beach',            'beach',     1_500_000, 150.9020, -34.4180),
 ('Bronte Beach',                   'beach',            'beach',     1_200_000, 151.2683, -33.9036),
 ('Maroubra Beach',                 'beach',            'beach',     1_200_000, 151.2567, -33.9496),
 ('Dee Why Beach',                  'beach',            'beach',     1_000_000, 151.2985, -33.7507),
 ('Collaroy & Narrabeen Beach',     'beach',            'beach',     1_000_000, 151.3001, -33.7175),
 ('Palm Beach',                     'beach',            'beach',       800_000, 151.3253, -33.5912),
 ('Balmoral Beach',                 'beach',            'beach',       800_000, 151.2513, -33.8241),
 ('Clovelly Beach',                 'beach',            'beach',       800_000, 151.2664, -33.9135),
 ('Avoca Beach',                    'beach',            'beach',       800_000, 151.4352, -33.4667),
 ('Brighton-Le-Sands',              'beach',            'beach',       800_000, 151.1560, -33.9600),
 ('Avalon Beach',                   'beach',            'beach',       600_000, 151.3325, -33.6353),
 ('Umina & Ettalong Beach',         'beach',            'beach',       600_000, 151.3220, -33.5260),
 ('Freshwater Beach',               'beach',            'beach',       500_000, 151.2906, -33.7821),
 ('Curl Curl Beach',                'beach',            'beach',       500_000, 151.2958, -33.7700),
 ('Tamarama Beach',                 'beach',            'beach',       400_000, 151.2706, -33.9005),
 ('Thirroul Beach',                 'beach',            'beach',       400_000, 150.9286, -34.3156),
 ('Austinmer Beach',                'beach',            'beach',       400_000, 150.9351, -34.3066),
 ('Nielsen Park',                   'beach',            'beach',       400_000, 151.2666, -33.8514),
 # --- parks ---
 ('Royal Botanic Garden Sydney',    'botanical_garden', 'park',      5_000_000, 151.2155, -33.8640),
 ('Centennial Parklands',           'park',             'park',      7_000_000, 151.2348, -33.8979),
 ('Parramatta Park',                'park',             'park',      2_500_000, 150.9991, -33.8082),
 ('Sydney Olympic Park Parklands',  'park',             'park',      3_000_000, 151.0782, -33.8442),
 ('Western Sydney Parklands',       'park',             'park',      2_000_000, 150.8620, -33.7950),
 ('Australian Botanic Garden Mount Annan', 'botanical_garden', 'park', 600_000, 150.7700, -34.0700),
 ('Royal National Park',            'nature_park',      'nature_park', 1_200_000, 151.0580, -34.0710),
 ('Ku-ring-gai Chase National Park', 'nature_park',     'nature_park',   800_000, 151.1580, -33.6560),
 ('Lane Cove National Park',        'nature_park',      'nature_park',   800_000, 151.1470, -33.7870),
 # --- shopping (estimated annual customer visits) ---
 ('Westfield Sydney',               'shopping_center',  'shopping_center', 20_000_000, 151.2089, -33.8701),
 ('Westfield Parramatta',           'shopping_center',  'shopping_center', 20_000_000, 151.0021, -33.8178),
 ('Westfield Bondi Junction',       'shopping_center',  'shopping_center', 17_000_000, 151.2509, -33.8923),
 ('Westfield Chatswood',            'shopping_center',  'shopping_center', 16_000_000, 151.1836, -33.7970),
 ('Castle Towers',                  'shopping_center',  'shopping_center', 16_000_000, 151.0063, -33.7306),
 ('Macquarie Centre',               'shopping_center',  'shopping_center', 15_000_000, 151.1213, -33.7772),
 ('Westfield Miranda',              'shopping_center',  'shopping_center', 15_000_000, 151.1001, -34.0350),
 ('Westfield Warringah Mall',       'shopping_center',  'shopping_center', 15_000_000, 151.2658, -33.7676),
 ('Broadway Sydney',                'shopping_center',  'shopping_center', 14_000_000, 151.1945, -33.8836),
 ('Westfield Penrith',              'shopping_center',  'shopping_center', 14_000_000, 150.6917, -33.7510),
 ('Macarthur Square',               'shopping_center',  'shopping_center', 13_000_000, 150.7973, -34.0754),
 ('Westfield Burwood',              'shopping_center',  'shopping_center', 13_000_000, 151.1059, -33.8745),
 ('Westfield Liverpool',            'shopping_center',  'shopping_center', 12_000_000, 150.9238, -33.9188),
 ('Rouse Hill Town Centre',         'shopping_center',  'shopping_center', 12_000_000, 150.9257, -33.6908),
 ('Erina Fair',                     'shopping_center',  'shopping_center', 12_000_000, 151.3922, -33.4378),
 ('Westpoint Blacktown',            'shopping_center',  'shopping_center', 12_000_000, 150.9061, -33.7703),
 ('Westfield Eastgardens',          'shopping_center',  'shopping_center', 11_000_000, 151.2243, -33.9448),
 ('Westfield Hornsby',              'shopping_center',  'shopping_center', 11_000_000, 151.1002, -33.7048),
 ('Westfield Hurstville',           'shopping_center',  'shopping_center', 10_000_000, 151.1055, -33.9661),
 ('Westfield Mt Druitt',            'shopping_center',  'shopping_center', 10_000_000, 150.8198, -33.7667),
 ('Top Ryde City',                  'shopping_center',  'shopping_center', 10_000_000, 151.1066, -33.8125),
 ('Bankstown Central',              'shopping_center',  'shopping_center', 10_000_000, 151.0391, -33.9158),
 ('Stockland Shellharbour',         'shopping_center',  'shopping_center',  9_000_000, 150.8390, -34.5645),
 ('Stockland Wetherill Park',       'shopping_center',  'shopping_center',  9_000_000, 150.8988, -33.8588),
 ('Wollongong Central',             'shopping_center',  'shopping_center',  8_000_000, 150.8942, -34.4246),
 ('Stockland Merrylands',           'shopping_center',  'shopping_center',  8_000_000, 150.9894, -33.8346),
 ('Roselands',                      'shopping_center',  'shopping_center',  7_000_000, 151.0690, -33.9348),
 ('Chatswood Chase',                'shopping_center',  'shopping_center',  6_000_000, 151.1859, -33.7941),
 ('Rhodes Waterside',               'shopping_center',  'shopping_center',  6_000_000, 151.0853, -33.8348),
 ('DFO Homebush',                   'shopping_center',  'shopping_center',  6_000_000, 151.0768, -33.8554),
 ('Marrickville Metro',             'shopping_center',  'shopping_center',  6_000_000, 151.1718, -33.9068),
 ('Birkenhead Point Outlet Centre', 'shopping_center',  'shopping_center',  5_000_000, 151.1627, -33.8558),
 ('Narellan Town Centre',           'shopping_center',  'shopping_center',  7_000_000, 150.7375, -34.0417),
 # --- hospitals (beds x 2.5 visitors/outpatients a day x 365) ---
 ('Westmead Hospitals',             'hospital',         'hospital', 1375 * 2.5 * 365, 150.9871, -33.8028),
 ('Royal Prince Alfred Hospital',   'hospital',         'hospital',  950 * 2.5 * 365, 151.1815, -33.8892),
 ('Liverpool Hospital',             'hospital',         'hospital',  880 * 2.5 * 365, 150.9307, -33.9203),
 ('Royal North Shore Hospital',     'hospital',         'hospital',  780 * 2.5 * 365, 151.1911, -33.8214),
 ('Randwick Hospitals Campus',      'hospital',         'hospital',  870 * 2.5 * 365, 151.2388, -33.9191),
 ('Wollongong Hospital',            'hospital',         'hospital',  600 * 2.5 * 365, 150.8830, -34.4247),
 ('St George Hospital',             'hospital',         'hospital',  600 * 2.5 * 365, 151.1340, -33.9671),
 ('Concord Hospital',               'hospital',         'hospital',  580 * 2.5 * 365, 151.0932, -33.8379),
 ('Nepean Hospital',                'hospital',         'hospital',  520 * 2.5 * 365, 150.7135, -33.7599),
 ('Gosford Hospital',               'hospital',         'hospital',  510 * 2.5 * 365, 151.3395, -33.4203),
 ('Northern Beaches Hospital',      'hospital',         'hospital',  490 * 2.5 * 365, 151.2328, -33.7508),
 ('Bankstown-Lidcombe Hospital',    'hospital',         'hospital',  480 * 2.5 * 365, 151.0208, -33.9330),
 ('Campbelltown Hospital',          'hospital',         'hospital',  470 * 2.5 * 365, 150.8060, -34.0779),
 ('Blacktown Hospital',             'hospital',         'hospital',  440 * 2.5 * 365, 150.9171, -33.7759),
 ('St Vincent\'s Hospital Sydney',  'hospital',         'hospital',  380 * 2.5 * 365, 151.2212, -33.8801),
 ('Sutherland Hospital',            'hospital',         'hospital',  350 * 2.5 * 365, 151.1147, -34.0376),
 ('Hornsby Ku-ring-gai Hospital',   'hospital',         'hospital',  300 * 2.5 * 365, 151.1124, -33.7031),
 ('Sydney Adventist Hospital',      'hospital',         'hospital',  500 * 2.5 * 365, 151.0985, -33.7334),
 ('Shellharbour Hospital',          'hospital',         'hospital',  230 * 2.5 * 365, 150.8404, -34.5590),
 ('Canterbury Hospital',            'hospital',         'hospital',  200 * 2.5 * 365, 151.0983, -33.9194),
 ('Fairfield Hospital',             'hospital',         'hospital',  200 * 2.5 * 365, 150.9040, -33.8600),
 ('Mount Druitt Hospital',          'hospital',         'hospital',  150 * 2.5 * 365, 150.8295, -33.7655),
 ('Ryde Hospital',                  'hospital',         'hospital',  150 * 2.5 * 365, 151.0896, -33.7956),
 ('Auburn Hospital',                'hospital',         'hospital',  150 * 2.5 * 365, 151.0332, -33.8603),
]

points, out = [], []
for name, sub, cls, annual, lon, lat in V:
    if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
        out.append(name); continue
    daily = annual / 365.0 * SHARE.get(cls, 1.0)
    points.append({"type": sub, "name": name, "code": code_of(name),
                   "location": [round(lon, 6), round(lat, 6)],
                   "total_capacity": int(round(daily)), "pop_size": int(min(200, max(15, daily / 10))),
                   "max_distance": 60_000, "_annual": int(annual),
                   **({"exponent": EXPONENT[sub]} if sub in EXPONENT else {})})
codes = [p['code'] for p in points]
assert len(codes) == len(set(codes)), [c for c in codes if codes.count(c) > 1]
os.makedirs(SPECIAL_DIR, exist_ok=True)
json.dump(points, open(f'{SPECIAL_DIR}/entertainment.json', 'w'), ensure_ascii=False, indent=1)
print(f"venues: {len(points)}   daily demand {sum(p['total_capacity'] for p in points):,}")
if out: print("outside box:", out)
