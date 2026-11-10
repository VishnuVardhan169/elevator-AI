#!/usr/bin/env bash
# Downloads the publicly available REAL elevator datasets into data/raw/<dataset_id>/.
# Skips any dataset whose folder already has files. Re-run safely.
set -uo pipefail
cd "$(dirname "$0")/.."

export KAGGLE_API_TOKEN="$(grep -i '^kaggle=' .env | cut -d= -f2- | tr -d '\r')"
UA="Mozilla/5.0 (elevator-ai-poc data download)"

fetch() {  # fetch <dataset_id> <file_name> <url>
  local dest="data/raw/$1" file="$2" url="$3"
  mkdir -p "$dest"
  if [ -s "$dest/$file" ]; then echo "skip $1/$file (exists)"; return; fi
  echo "downloading $1/$file"
  if curl -fL --retry 3 -m 1800 -A "$UA" -o "$dest/$file.part" "$url"; then
    mv "$dest/$file.part" "$dest/$file"
    echo "  ok $(du -h "$dest/$file" | cut -f1)"
  else
    rm -f "$dest/$file.part"; echo "  FAILED $url"
  fi
}

# --- NY / NYC open data (Socrata full CSV exports) ---
fetch mta_nyct_ee_availability  mta_nyct_elevator_escalator_availability.csv \
  "https://data.ny.gov/api/views/rc78-7x78/rows.csv?accessType=DOWNLOAD"
fetch mta_mnr_ee_availability   mta_metro_north_elevator_escalator_availability.csv \
  "https://data.ny.gov/api/views/ax67-8386/rows.csv?accessType=DOWNLOAD"
fetch nyc_dob_elevator_complaints nyc_dob_elevator_complaints.csv \
  "https://data.cityofnewyork.us/api/views/kqwi-7ncn/rows.csv?accessType=DOWNLOAD"
fetch nyc_dob_elevator_devices  nyc_dob_now_elevator_safety_compliance.csv \
  "https://data.cityofnewyork.us/api/views/e5aq-a4j2/rows.csv?accessType=DOWNLOAD"

fetch mta_nyct_ee_availability  MTA_SubwayElevatorAndEscalatorAvailability_Overview.pdf \
  "https://data.ny.gov/api/views/rc78-7x78/files/6390c660-801d-4e3e-b6b5-948760a0f353?download=true&filename=MTA_SubwayElevatorAndEscalatorAvailability_Overview.pdf"

# --- research repositories ---
fetch huawei_elevator_door_zenodo grc-datasets-pred-maintenance-v1.0.0.zip \
  "https://zenodo.org/records/3653909/files/omlstreaming/grc-datasets-pred-maintenance-v1.0.0.zip?download=1"
if [ ! -d data/raw/huawei_elevator_door_zenodo/omlstreaming-grc-datasets-pred-maintenance-892dd65 ]; then
  (cd data/raw/huawei_elevator_door_zenodo && python3 -m zipfile -e grc-datasets-pred-maintenance-v1.0.0.zip .)
fi
fetch realvibrations_elevator 17_elevator.zip \
  "https://realvibrations.nipslab.org/media/vibrations/rv-000150/17_elevator.zip"
if [ ! -s data/raw/realvibrations_elevator/data.dat ]; then
  (cd data/raw/realvibrations_elevator && python3 -m zipfile -e 17_elevator.zip .)
fi

# Manual (browser) downloads - these servers block scripted access:
#   figshare_traction_elevator: https://figshare.com/articles/dataset/Traction_Elevator_Predictive_maintenance_XLSX/26807974
#   mondragon_17floor_trips:     https://doi.org/10.48764/dwdv-gz94  (Elevator_class_dataset.csv + README.txt)
# Save them into data/raw/<dataset_id>/.

# --- Kaggle (real phone accelerometer recording of elevator rides) ---
if [ -z "$(ls -A data/raw/elevator_acc_phone 2>/dev/null)" ]; then
  echo "downloading elevator_acc_phone (kaggle)"
  .venv/bin/kaggle datasets download -d andrewross3/elevatoracc2 -p data/raw/elevator_acc_phone --unzip -q || echo "  FAILED kaggle"
else
  echo "skip elevator_acc_phone (exists)"
fi
echo done
