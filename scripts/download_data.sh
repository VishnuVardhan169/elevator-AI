#!/usr/bin/env bash
# Downloads all Kaggle datasets used by the POC into data/raw/.
# Requires `kaggle=<KGAT token>` in .env and the venv at .venv/.
set -euo pipefail
cd "$(dirname "$0")/.."

export KAGGLE_API_TOKEN="$(grep -i '^kaggle=' .env | cut -d= -f2- | tr -d '\r')"
KAGGLE=.venv/bin/kaggle

download() {
  local ref="$1" dest="data/raw/$2"
  if [ -d "$dest" ] && [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then
    echo "skip $ref (exists)"
    return
  fi
  echo "downloading $ref -> $dest"
  "$KAGGLE" datasets download -d "$ref" -p "$dest" --unzip -q
}

download shivamb/elevator-predictive-maintenance-dataset elevator
download arnabbiswas1/microsoft-azure-predictive-maintenance azure
download stephanmatzka/predictive-maintenance-dataset-ai4i-2020 ai4i
download giacomoveneri1/mimii-dataset-sound-data-for-malfunctioning-pump mimii
echo done
