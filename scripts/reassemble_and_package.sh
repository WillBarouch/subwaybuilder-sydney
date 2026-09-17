#!/bin/bash
# Rebuild special layers on the existing base matrix, then route and package.
set -euo pipefail
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate depot
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/scripts"
python -u scripts/build_special.py 2>&1 | grep -v Warn
python -u scripts/build_entertainment.py
cp build/SYD/demand_data.base.json build/SYD/demand_data.json
rm -f build/SYD/.railyard_map/special_demand_points.json
python -u scripts/assemble_demand.py | grep -vE "^(Median|Mean)"
bash scripts/route_and_package.sh
