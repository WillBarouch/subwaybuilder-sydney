#!/bin/bash
# Stop the map build before C: runs dry. WSL's disk is a file on C:, so a full
# C: crashes the VM mid-write instead of failing cleanly (2026-09-14).
LIMIT_KB=$((3 * 1024 * 1024))
while true; do
  free=$(df -k /mnt/c | awk 'NR==2{print $4}')
  if [ "$free" -lt "$LIMIT_KB" ]; then
    echo "### DISK GUARD: C: down to $((free/1024)) MB free - stopping build" >> "$(dirname "$0")/../.scratch/map.log"
    ps -eo pid,args | awk '($2=="python" && $4 ~ /build_city/) || ($2=="node" && /mapshaper/) || /tippecanoe|tile-join|planetiler/' \
      | grep -v awk | awk '{print $1}' | xargs -r kill
    exit 0
  fi
  ps -eo args | grep -qE "^python -u scripts/build_c[i]ty" || exit 0
  sleep 20
done
