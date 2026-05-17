#!/usr/bin/env bash
# Helios V2V: cosmos_base.mp4 (or waymo_clean.mp4 fallback) -> helios_flood.mp4
set -euo pipefail

CFG="${CFG:-/workspace/configs/flood_prompt.yaml}"
IN="${IN:-/workspace/outputs/cosmos_base.mp4}"
OUT="${OUT:-/workspace/outputs/helios_flood.mp4}"

# Fallback: IN=/workspace/outputs/waymo_clean.mp4 bash scripts/04_run_helios_flood.sh

read_yaml() { python -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))$1)" "${CFG}"; }
PROMPT=$(read_yaml '["prompt"]')
NEG=$(read_yaml '["negative_prompt"]')
CKPT=$(read_yaml '["helios"]["checkpoint"]')
NF=$(read_yaml '["helios"]["num_frames"]')
FPS=$(read_yaml '["helios"]["fps"]')
W=$(read_yaml '["helios"]["width"]')
H=$(read_yaml '["helios"]["height"]')
SEED=$(read_yaml '["helios"]["seed"]')

cd /workspace/Helios

# REPLACE script name + flags with what Helios README specifies:
python sample_video.py \
  --pretrained_model_name_or_path "${CKPT}" \
  --task v2v \
  --video_path "${IN}" \
  --prompt "${PROMPT}" \
  --negative_prompt "${NEG}" \
  --num_frames "${NF}" --fps "${FPS}" \
  --width "${W}" --height "${H}" \
  --seed "${SEED}" \
  --output_path "${OUT}"

echo "wrote ${OUT}"