"""Single source of truth for which map is being built. Override with env vars."""
import json, os
CITY = os.environ.get('SB_CITY', 'SYD')
BBOX = json.loads(os.environ.get('SB_BBOX', '[150.50, -34.62, 151.48, -33.34]'))
CITY_DIR = os.path.join('build', CITY)
DATA_DIR = 'data'
OA_CENTROIDS = os.path.join(DATA_DIR, f'grid_{CITY}.csv')   # kept for script compatibility
DEMAND = os.path.join(CITY_DIR, 'demand_data.json')
SPECIAL_DIR = os.path.join('build', f'special_{CITY}')
def describe():
    return f"{CITY} bbox={BBOX}"
