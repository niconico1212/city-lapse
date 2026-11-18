#!/usr/bin/env bash
# Rebuild everything downstream of the research files and GHSL clips.
#   scripts/run_pipeline.sh            all cities
#   scripts/run_pipeline.sh tokyo lagos  just these
# Assumes scripts/01_fetch_ghsl.py has been run (raw/clips/*.npz exist).
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/03_footprints.py "$@"
$PY scripts/04_buildings.py "$@"
$PY scripts/05_export_index.py
