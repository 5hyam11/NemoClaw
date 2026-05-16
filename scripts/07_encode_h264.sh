#!/usr/bin/env bash
# Re-encode all 5 outputs as H.264 + yuv420p + faststart, then verify.
set -euo pipefail

OUT_DIR="${OUT_DIR:-/workspace/outputs}"
TMP="${OUT_DIR}/_tmp"; mkdir -p "${TMP}"

FILES=(
  waymo_clean.mp4
  cosmos_base.mp4
  helios_flood.mp4
  perception_untrained.mp4
  perception_trained.mp4
)

for f in "${FILES[@]}"; do
  IN="${OUT_DIR}/${f}"
  if [[ ! -f "${IN}" ]]; then
    echo "MISSING: ${IN}"; exit 1
  fi
  OUT="${TMP}/${f}"
  ffmpeg -y -i "${IN}" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium \
    -movflags +faststart -an "${OUT}" 2>/dev/null
  mv "${OUT}" "${IN}"
done
rmdir "${TMP}"

echo
echo "=== Verification ==="
for f in "${FILES[@]}"; do
  printf "%-32s  " "${f}"
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,pix_fmt,width,height,r_frame_rate \
    -of csv=p=0 "${OUT_DIR}/${f}"
done