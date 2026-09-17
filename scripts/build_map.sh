#!/bin/bash
set -euo pipefail
source "$(conda info --base)/etc/profile.d/conda.sh"; conda activate depot
cd "$(dirname "$0")/.."
export DEPOT_PLANETILER_HEAP=12g PYTHONPATH="$PWD/scripts"
mkdir -p .scratch
bash scripts/disk_guard.sh &
python -u scripts/build_city.py
echo "### MAP BUILD DONE"
