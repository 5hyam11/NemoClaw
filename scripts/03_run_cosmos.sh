#!/usr/bin/env bash
# Cosmos-Drive-Dreams: render HDMap+bbox condition video, then run Transfer.
set -euo pipefail

CLIP_ID="${CLIP_ID:-FILL_ME_IN}"
RDS_HQ_ROOT="${RDS_HQ_ROOT:-/workspace/data/rds_hq}"
OUT="${OUT:-/workspace/outputs}"

cd /workspace/Cosmos-Drive-Dreams

# 1. Render HDMap + bbox condition (CPU-only mode is fine for this)
cd cosmos-drive-dreams-toolkits
python render_from_rds_hq.py \
  -i "${RDS_HQ_ROOT}" \
  -o "${OUT}/cosmos_cond" \
  -d rds_hq \
  --skip lidar --skip world_scenario
cd ..

# 2. Transfer inference — VERIFY EXACT FLAGS in cosmos-transfer1/README.md.
# Placeholder:
# python -m cosmos_transfer1.inference \
#   --checkpoint /workspace/weights/Cosmos-Transfer1-7B-Sample-AV \
#   --condition_video "${OUT}/cosmos_cond/hdmap/.../${CLIP_ID}_0.mp4" \
#   --prompt "urban driving, daylight, photorealistic" \
#   --output_path "${OUT}/cosmos_base.mp4"

echo "expect cosmos_base.mp4 at ${OUT}/cosmos_base.mp4"