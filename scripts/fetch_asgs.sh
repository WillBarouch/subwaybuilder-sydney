#!/bin/bash
# ABS ASGS 2021 boundaries (SA1, MB) and Mesh Block counts.
set -uo pipefail
cd "$(dirname "$0")/../data/abs"
B=https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files
get() { [ -s "$1" ] && return; curl -sL -A "Mozilla/5.0" --retry 3 -o "$1.part" "$2" -w "%{http_code} %{size_download} $1\n" && mv "$1.part" "$1"; }
get SA1_2021_AUST_SHP_GDA2020.zip $B/SA1_2021_AUST_SHP_GDA2020.zip
get MB_2021_AUST_SHP_GDA2020.zip  $B/MB_2021_AUST_SHP_GDA2020.zip
get mb_counts_2021.xlsx "https://www.abs.gov.au/census/guide-census-data/mesh-block-counts/2021/Mesh%20Block%20Counts%2C%202021.xlsx"
echo "### ASGS DONE"
