#!/bin/bash
# Public sources for special demand and water depths. Idempotent: skips files already present.
set -uo pipefail
cd "$(dirname "$0")/../data"
UA="Mozilla/5.0"
get() {  # dest url
  [ -s "$1" ] && { echo "have $1"; return; }
  mkdir -p "$(dirname "$1")"
  curl -sL -A "$UA" --retry 3 -o "$1.part" "$2" -w "%{http_code} %{size_download} $1\n" && mv "$1.part" "$1"
}
S=special_src
# schools: ACARA 2025 profile/location/grades, NSW public schools master dataset (selective schools)
A="https://dataandreporting.blob.core.windows.net/anrdataportal/Data-Access-Program"
get $S/acara_profile_2025.xlsx  "$A/School%20Profile%202025.xlsx"
get $S/acara_location_2025.xlsx "$A/School%20Location%202025.xlsx"
get $S/acara_grades_2025.xlsx   "$A/Enrolments%20by%20Grade%202025.xlsx"
get $S/nsw_public_schools.csv "https://data.nsw.gov.au/data/dataset/78c10ea3-8d04-4c9c-b255-bbf8547e37e7/resource/3e6d5f6a-055c-440d-a690-fc0537c31095/download/master_dataset.csv"
# universities: Department of Education 2024 student data
get $S/he2024_pivot.xlsx    "https://www.education.gov.au/download/19507/perturbed-student-enrolments-pivot-table-2024/41971/document/xlsx"
get $S/he2024_section2.xlsx "https://www.education.gov.au/download/19481/2024-section-2-all-students/41929/document/xlsx"
# water depths: Wilson & Power (2018) on PANGAEA, NSW multibeam + marine lidar mosaic (1.7 GB)
P="https://store.pangaea.de/Publications/WilsonK_etal_2018"
get bathy/Sydney.zip "$P/Sydney.zip"
get bathy/Botany.zip "$P/Botany.zip"
get bathy/hawkesbury_revised.zip "$P/hawkesbury_revised.zip"
get bathy/nsw_mosaic.zip "https://www.planningportal.nsw.gov.au/opendata/dataset/a40c3e5e-860a-40ab-b54f-47d38c5ca5fd/resource/2ef6c816-04b1-4aa7-9f06-e727b9c0cdd9/download/bathymetrymosaic_marinelidar_mbes.zip"
echo "### SPECIAL + BATHY FETCH DONE"
