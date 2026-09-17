#!/bin/bash
# OSRM up -> route every pop -> package -> OSRM down.
set -euo pipefail
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate depot
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/scripts"
echo "### wait for docker $(date +%T)"
for i in $(seq 1 120); do docker info >/dev/null 2>&1 && break; sleep 5; done
docker info >/dev/null 2>&1 || { echo "docker never came up"; exit 1; }
echo "### osrm $(date +%T)";     bash scripts/setup_osrm.sh
echo "### route $(date +%T)";    python -u scripts/route_osrm.py --port 5003 --no-paths --workers 20
python -u scripts/fill_zero_routes.py
echo "### package $(date +%T)"
python -u scripts/prune_schema.py
python -u scripts/finalise.py
python -u scripts/trim_description.py
python -u scripts/package_map.py
docker stop SYD >/dev/null 2>&1 || true
docker rm SYD >/dev/null 2>&1 || true
rm -f build/SYD/SYD.osm.pbf build/SYD/SYD.osrm*
echo "### ROUTE+PACKAGE DONE $(date +%T)"
