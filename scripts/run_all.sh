#!/usr/bin/env bash
# End-to-end. Run from /workspace inside the NGC container.
set -euo pipefail

SRC_CLIP="${SRC_CLIP:-clips/raw/segment_front.mp4}"
START="${START:-12}"
DUR="${DUR:-5}"

# 1. Trim source -> waymo_clean.mp4
python scripts/01_trim_waymo.py --in "${SRC_CLIP}" --start "${START}" --duration "${DUR}"

# 2. cosmos_base.mp4 — if Cosmos pipeline produced it, use it. Else fall back to the clean clip.
if [[ ! -f outputs/cosmos_base.mp4 ]]; then
  echo "No cosmos_base.mp4 — using waymo_clean as the visual base."
  cp outputs/waymo_clean.mp4 outputs/cosmos_base.mp4
fi

# 3. Boxes (YOLO fallback path — swap for Cosmos-extracted boxes if available)
python scripts/02_detect_boxes_yolo.py \
  --video outputs/cosmos_base.mp4 \
  --out   data/boxes/waymo_clean.json

# 4. Helios flood
bash scripts/04_run_helios_flood.sh

# 5. Overlays
python scripts/05_render_trained.py
python scripts/06_render_untrained.py

# 6. Final encode + verify
bash scripts/07_encode_h264.sh

echo "DONE. Five outputs in outputs/."