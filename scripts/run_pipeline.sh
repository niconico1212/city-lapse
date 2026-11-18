#!/usr/bin/env bash
# Rebuild everything downstream of the research files and GHSL clips.
#   scripts/run_pipeline.sh            all cities
#   scripts/run_pipeline.sh tokyo lagos  just these
# Assumes scripts/01_fetch_ghsl.py has been run (raw/clips/*.npz exist).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/03_footprints.py "$@"
# Artistic layers (data/extras.json; pilot: Tokyo). Real shapes need the PLATEAU GeoParquet files
# in raw/plateau/ and must run before the generator, which reads their coverage mask.
if ls raw/plateau/*_building_lod0.parquet >/dev/null 2>&1; then
  if [ $# -eq 0 ] || [[ " $* " == *" tokyo "* ]]; then $PY scripts/08_real_buildings.py; fi
fi
$PY scripts/04_buildings.py "$@"
if [ $# -eq 0 ] || [[ " $* " == *" tokyo "* ]]; then $PY scripts/09_landmark_models.py tokyo; fi
$PY scripts/05_export_index.py
