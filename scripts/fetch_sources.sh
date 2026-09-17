#!/bin/bash
# Public (no-login) sources for SYD. Idempotent: skips files already present.
set -uo pipefail
cd "$(dirname "$0")/../data"
UA="Mozilla/5.0"
get() {  # dest url
  [ -s "$1" ] && { echo "have $1"; return; }
  mkdir -p "$(dirname "$1")"
  curl -sL -A "$UA" --retry 3 -o "$1.part" "$2" -w "%{http_code} %{size_download} $1\n" && mv "$1.part" "$1"
}
H=https://opendata.transport.nsw.gov.au/data/dataset
# JTW 2011 (TfNSW BTS) + TZ11 geography
get jtw11/t11.zip  $H/66ee70ff-eb4f-45e5-b45b-90ce484ec178/resource/7cb0119a-b2f5-4b5e-bf40-cc17c1b045cf/download/bts_jtw_table11_2011_v1_3.zip
get jtw11/t01.zip  $H/66ee70ff-eb4f-45e5-b45b-90ce484ec178/resource/2dd13d56-2894-4153-bbab-972550629bfe/download/bts_jtw_table01_2011_v1_0.zip
get jtw11/codeframes.zip $H/66ee70ff-eb4f-45e5-b45b-90ce484ec178/resource/515b7ca4-42b7-4e57-8fdb-0d8b012f009b/download/bts_2011jtw_codeframes-v1.2_0.zip
get jtw11/user_guide.pdf $H/66ee70ff-eb4f-45e5-b45b-90ce484ec178/resource/86d45b1c-b887-4228-8c2c-a021d48e5ebe/download/tr2013-12_2011_jtw_user_guide_v1_3.pdf
get tz11/tz11_shp.zip $H/15a0fc08-f440-4879-84c9-54b11e0fb356/resource/d6e60cb3-dc42-4ec9-9cbf-d24cda37bf08/download/bts_spatial_tz_nsw_2011_shapefile.zip
get tz11/concordances.zip $H/15a0fc08-f440-4879-84c9-54b11e0fb356/resource/0099751c-8182-4cfd-8794-e598f7a9ee1a/download/bts_tz_concordances_2011.zip
# TZ21 geography + TZP24 projections
get tz21/tz21_geojson.zip $H/fd93096c-c7e2-4f33-9b98-264cbd75d9ce/resource/f5ff7030-0e92-4c69-b1f3-fc64c6687736/download/tz21_tfnsw_geojson.zip
get tz21/concordances.zip $H/fd93096c-c7e2-4f33-9b98-264cbd75d9ce/resource/cff87607-f6fc-4e57-b58d-0ea6f59d8f75/download/tz21_concordances.zip
get tzp24/population_by_tz.csv $H/e35da583-c645-4e15-a7ca-ea6678ae2699/resource/3739c279-7887-4e33-9b96-8a181b23be84/download/tzp24-population-erp_popd_pnpd-by-tz-2021-2066.csv
get tzp24/popd_age_sex_by_tz.csv $H/e35da583-c645-4e15-a7ca-ea6678ae2699/resource/62569f7f-53d4-4922-86be-e6f13e108777/download/tzp24-popd-by-age_sex-by-tz-2021-2066.csv
get tzp24/population_dictionary.csv $H/e35da583-c645-4e15-a7ca-ea6678ae2699/resource/9ee12cf7-6053-4f37-ad35-7f4bc2d485fb/download/tzp24-population-data-dictionary.csv
get tzp24/employment_by_tz.csv $H/65041f3f-c9bd-4731-b32b-05691272537e/resource/850e752d-f88a-48e6-8700-e7091430c2ac/download/tzp24-employment-by-tz-2021-2066.csv
get tzp24/employment_by_tz_industry.csv $H/65041f3f-c9bd-4731-b32b-05691272537e/resource/b1f00271-e244-458f-aad3-63a6fb4898f2/download/tzp24-employment-by-tz-by-industry-2021-2066.csv
get tzp24/employment_dictionary.csv $H/65041f3f-c9bd-4731-b32b-05691272537e/resource/52feabe5-9e16-41ed-83d8-1324661cedd1/download/tzp24-employment-data-dictionary.csv
get tzp24/workforce_by_tz.csv $H/ffd85ded-1107-4afc-af56-e22946b6f5b6/resource/10b8ff65-bfc8-4e86-a62f-e44780f5d5be/download/tzp24-workforce-by-status-by-tz-2021-2066.csv
get tzp24/technical_guide.pdf $H/65041f3f-c9bd-4731-b32b-05691272537e/resource/ca2fcd4d-fcaf-412a-b761-e5c86af6f570/download/tzp24-technical-guide.pdf
# ABS 2021 Census DataPacks (free): SA1 general community profile
get abs/2021_GCP_SA1_NSW.zip https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SA1_for_NSW_short-header.zip
# OSM
get osm/new_south_wales-latest.osm.pbf https://download.openstreetmap.fr/extracts/oceania/australia/new_south_wales-latest.osm.pbf
echo "### FETCH DONE"
