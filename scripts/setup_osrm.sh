#!/bin/bash
# OSRM for SYD. depot's prepare_osrm maps -p PORT:PORT, but osrm-routed always
# listens on 5000 inside the container, so any non-default host port lands on a
# dead socket (found on the LDNX build). Build the routing data with osmium +
# the OSRM image directly, then serve on host 5003 -> container 5000.
set -euo pipefail
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate depot
cd "$(dirname "$0")/.."
D=build/SYD; mkdir -p $D
[ -f $D/SYD.osm.pbf ] || osmium extract --strategy complete_ways --bbox 150.40,-34.72,151.58,-33.24 \
    data/osm/new_south_wales-latest.osm.pbf -o $D/SYD.osm.pbf --overwrite
IMG=ghcr.io/project-osrm/osrm-backend
if [ ! -f $D/SYD.osrm.hsgr ]; then
  docker run --rm -v "$(pwd)/$D:/data" $IMG osrm-extract -p /opt/car.lua /data/SYD.osm.pbf
  docker run --rm -v "$(pwd)/$D:/data" $IMG osrm-contract /data/SYD.osrm
fi
docker rm -f SYD >/dev/null 2>&1 || true
docker run --name SYD -d -p 5003:5000 -v "$(pwd)/$D:/data" $IMG osrm-routed --algorithm ch /data/SYD.osrm
T="http://127.0.0.1:5003/route/v1/driving/151.2070,-33.8688;150.8931,-34.4278?overview=false"
for i in $(seq 1 40); do curl -sf --max-time 5 "$T" >/dev/null && break; sleep 3; done
curl -s "$T" | head -c 200; echo
echo "### OSRM READY"
