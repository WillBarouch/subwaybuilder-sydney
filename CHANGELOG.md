# Changelog

## v2.2.0 — 2026-09-18

Walking along real streets, for Subway Builder 1.7.17's walk graph. The demand data is unchanged,
so v2.x saves carry over.

- **Commuters walk the street network.** The map ships a walk graph (`walk_graph.bin.gz`) built from
  OpenStreetMap: every street except motorways and their ramps, plus footpaths, shared paths, steps
  and separately mapped sidewalks, minus anything tagged private or closed to pedestrians. Walks to
  and from stations now follow real routes and go around the harbour, rivers and bays instead of
  across them.
  - 533,000 nodes and 742,000 edges covering 50,600 km of walkable ways; 17 MB compressed.
  - Only the connected network is kept (98% of walkable length). Sidewalks are included, though the
    game's docs suggest skipping them, because in Sydney about 1,000 km of footpaths (the airport
    precinct, Wolli Creek, newer estates) only reach the streets through them.
  - 99% of people's demand points are within the game's 250 m snapping distance. The rest, mostly
    job sites behind private roads such as defence land and the Kurnell refinery, walk in straight
    lines as before.
- **Footpaths show on the map.** 108,000 footpaths, shared paths, steps and pedestrian malls are
  added to `roads.geojson` as pedestrian ways (sidewalks are left off so streets don't get doubled).
- Older game versions ignore the walk graph and behave exactly as v2.1.0.
- **Installing through Railyard:** Railyard currently only copies the files it knows about, so the
  walk graph is left out until it recognises `walk_graph.bin`. Until then, copy `walk_graph.bin.gz`
  from the ZIP into the installed map folder (`cities/data/SYD/`).

## v2.1.0 — 2026-09-18

Water-depth fix on top of v2.0.0. The demand data is unchanged, so v2.0.0 saves carry over.

- **Depth bands no longer overlap.** depot builds each band from its outer edge only (so deeper
  water inside a band is covered over), pads every band by about 10 m and trims it against the
  shallower ones. That was harmless on the old global depth grid, but on detailed survey data it
  left overlapping slivers, which the game drew as dark streaks along every edge, with odd straight
  cut-outs. Bands are now built with their holes and meet exactly, with no padding or trimming.
- **The depth grid is lightly smoothed** (about 75 m) before the bands are drawn, which removes the
  blockiness and the seams where survey sources meet.
- On 9,100 sample points across the harbour: points covered by overlapping bands fell from 13.7% to
  0%, and points whose band disagreed with the depth data from 24.3% to 6.2% (the rest is water at
  the shoreline, which falls back to the 0-5 m band).
- Very small islands, such as Shark Island, lose their thin shallow rim as a result of the smoothing.

## v2.0.0 — 2026-09-17

A full rebuild of the map with a new generation pipeline (`scripts/`). The map code is still `SYD`,
so saves from v1 load on it; the demand is entirely new.

### Requirements
- Subway Builder **1.5.0 or later**. The map now ships the binary buildings index
  (`buildings_index.bin.gz`) that the game has used since 1.3.
- If you install by hand, remove v1 first.

### Coverage
- Extended from Penrith–Northern Beaches–Royal National Park to **Gosford and the Central Coast in the
  north, Wollongong, Shellharbour and Albion Park in the south, and Springwood in the west**. That
  takes in the Illawarra, Terrigal and Avoca on the coast, and Western Sydney International.
- Bounding box: `150.50, -34.62` to `151.48, -33.34` (v1: `150.535, -34.173` to `151.343, -33.365`).

### Demand
- **4.10 million people**, up from 3.18 million:
  - 2.93 million commuters;
  - 1.17 million special-demand trips a day.
- 13,465 demand points (v1: 9,687) and 91,400 pops (v1: 25,580).
- **One demand point per ABS SA1.** Each point sits on housing rather than at a geometric centre, and
  job clusters get their own point when they're far from an SA1's homes.
- **Commutes** come from Transport for NSW's Journey to Work travel-zone tables:
  - fitted to TfNSW's official 2026 projections of homes and jobs (TZP24);
  - growth areas (new estates, business parks, the new airport) borrow their neighbours' patterns;
  - people who work from home are removed.

  Mean road commute: 16.0 km.
- **Long commutes are kept.** Pops are sampled in proportion to flow and refitted so every point's
  totals and the trip-length distribution hold, rather than keeping only the biggest flows.

### Special demand
Visitors, students and passengers only; staff are already counted as commuters.
- **Universities:** 2024 Department of Education enrolments with online students removed, split
  across real campuses:
  - USyd, UNSW, UTS and Macquarie;
  - all eleven WSU campuses, UOW (including Sydney CBD and Liverpool), ACU and Notre Dame;
  - Newcastle's Central Coast campuses, and Sydney campuses of interstate universities;
  - private colleges grouped by precinct.
- **TAFE NSW** (new): 31 campuses.
- **Secondary schools** (new): 572 government, Catholic, independent, selective and special schools,
  from ACARA 2025 enrolments. Primary schools are left out.
- **Pupil and student homes** follow the 2021 Census count of who attends each kind of institution in
  each SA1, so not everyone lives next door to campus.
- **Airports:**
  - Sydney Airport's 2025 traffic across T1, T2 and T3;
  - **Western Sydney International at 10 million passengers a year**, now a single terminal point
    (v1 had it twice);
  - Shellharbour Airport.
- **Venues:** 139, up from 36, including:
  - beaches from Palm Beach to Wollongong, plus Terrigal and Avoca;
  - stadiums and arenas, and racecourses;
  - Darling Harbour, The Rocks, the Opera House, Taronga, Luna Park, museums and galleries;
  - parks and national parks, zoos and wildlife parks;
  - 34 shopping centres and 24 hospitals.
- **Military bases removed:** their personnel are workplace jobs, so counting them again
  double-counted.

### Map
- **Railway station structures removed** from the building footprints, so stations can be built at
  existing stations.
- **Water depths** now come from a 50 m composite instead of the global GEBCO grid:
  - the NSW Government's multibeam and marine-lidar survey;
  - Wilson & Power's seamless grids for Sydney Harbour (including the Parramatta and Lane Cove rivers
    and Middle Harbour), Botany Bay, the Georges River, Port Hacking and the Hawkesbury (Broken Bay,
    Pittwater, Brisbane Water);
  - GEBCO for the open ocean.

  The harbour reaches its real 40+ m depth, and rivers keep their channels.
- **The package now includes** the ocean depth index, building foundation tiles and special-demand
  metadata.

### Known limitations
- **The commute pattern dates from the 2011 Census**, grown to 2026. It's the finest public
  travel-zone table; 2021 origin–destination data is only available through ABS TableBuilder.
- **Some inputs are estimates:** university campus splits, TAFE campus sizes, and visitor numbers for
  beaches, parks and shopping centres. The map description says which.
- **About 16% of trips are under 3 km by road,** so the game will show them as walking. These are real
  short trips; the game has no bike mode.

## v1.2.0 — 2026-03-22
Last release built with the v1 generator (now in `v1/`): ABS census demand from Penrith to the Northern
Beaches and Royal National Park, with airports, universities, entertainment venues, beaches and
military bases.
