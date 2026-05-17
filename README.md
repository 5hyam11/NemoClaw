# DreamLoop

AV safety demo pipeline on a DGX Spark. Cosmos-Drive-Dreams + Helios V2V
flood a Waymo dashcam clip and stress-test a fake perception stack.

## Final outputs

After the pipeline finishes, five `.mp4` files live on the Spark at:

```
~/dreamloop-workspace/dreamloop/outputs/
├── waymo_clean.mp4              # trimmed Waymo baseline
├── cosmos_base.mp4              # Cosmos-Drive-Dreams synthetic pass
├── helios_flood.mp4             # Helios V2V flood transformation
├── perception_trained.mp4       # flood + clean ground-truth boxes
└── perception_untrained.mp4     # flood + glitchy boxes (dropout, jitter, ghosts)
```

You pull them to your laptop in Step 12.

## Hardware

- NVIDIA DGX Spark (GB10 Grace Blackwell, sm_121, aarch64, CUDA 13.0)
- ~150 GB free disk for model weights + clips
- Outbound network for HuggingFace + GitHub
- HuggingFace account with accepted licenses for:
  - `nvidia/Cosmos-Transfer1-7B-Sample-AV`
  - `BestWishYSH/Helios-Distilled`

---

## Step 1 — SSH into the Spark

```bash
ssh <you>@<dgx-spark-host>
nvidia-smi
uname -m                              # must print: aarch64
df -h ~                               # need ~150 GB free in $HOME
```

If `nvidia-smi` fails or `uname -m` isn't `aarch64`, stop — wrong machine.

---

## Step 2 — Clone the repos

Layout: your repo and the two upstream model repos are **siblings**
under `~/dreamloop-workspace`. The shell scripts assume that structure.

```bash
mkdir -p ~/dreamloop-workspace && cd ~/dreamloop-workspace

# Your repo
git clone https://github.com/<you>/dreamloop.git
cd dreamloop && git checkout <your-branch> && cd ..

# Upstream model repos
git clone --recurse-submodules https://github.com/nv-tlabs/Cosmos-Drive-Dreams.git
git clone --depth=1 https://github.com/PKU-YuanGroup/Helios.git

ls
# dreamloop  Cosmos-Drive-Dreams  Helios
```

`--recurse-submodules` is critical — Cosmos-Drive-Dreams has
`cosmos-transfer1` as a submodule and nothing works without it.

---

## Step 3 — Launch the NGC PyTorch container

PyTorch on the Spark needs to be the ARM64 + CUDA-13 build. The NGC
container is the shortest path to that.

```bash
docker pull nvcr.io/nvidia/pytorch:25.11-py3

docker run --rm -it --gpus all \
  --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 \
  --shm-size=16g \
  -v $HOME/dreamloop-workspace:/workspace \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -w /workspace \
  nvcr.io/nvidia/pytorch:25.11-py3 bash
```

Every step below runs **inside this container**. If you exit and come
back, re-run the same `docker run` line.

---

## Step 4 — Smoke-test the container

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
ffmpeg -version | head -1
python -c "import cv2; print('cv2', cv2.__version__)"
```

`torch.cuda.is_available()` must print `True`. If it doesn't, the host
is missing NVIDIA Container Toolkit. On the host:
`sudo apt install nvidia-container-toolkit && sudo systemctl restart docker`.
Fix this before anything else.

---

## Step 5 — Install deps + smoke-test the overlay path

```bash
cd /workspace/dreamloop
pip install -r requirements.txt
chmod +x scripts/*.sh
mkdir -p data/boxes outputs clips/raw weights

# Synthetic clip + fake boxes — verifies overlay code without any model
python - <<'PY'
import cv2, json, numpy as np, os
os.makedirs("outputs", exist_ok=True); os.makedirs("data/boxes", exist_ok=True)
W, H, FPS, N = 640, 360, 24, 72
w = cv2.VideoWriter("outputs/_smoke.mp4", cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
for i in range(N):
    f = np.full((H, W, 3), 40, np.uint8)
    cv2.circle(f, (100 + 3*i, 180), 20, (50, 150, 200), -1)
    w.write(f)
w.release()
frames = [{"idx": i, "boxes": [{"x1": 80+3*i, "y1": 160, "x2": 120+3*i,
          "y2": 200, "label": "car", "track_id": 1, "confidence": 0.9}]}
          for i in range(N)]
json.dump({"fps": FPS, "width": W, "height": H, "frames": frames},
          open("data/boxes/_smoke.json", "w"))
PY

python scripts/05_render_trained.py   --video outputs/_smoke.mp4 --boxes data/boxes/_smoke.json --out outputs/_smoke_trained.mp4
python scripts/06_render_untrained.py --video outputs/_smoke.mp4 --boxes data/boxes/_smoke.json --out outputs/_smoke_untrained.mp4

ls -la outputs/_smoke*.mp4
rm outputs/_smoke*.mp4 data/boxes/_smoke.json
```

If both smoke files exist, the overlay path is green. This is your
safety floor — even if Cosmos and Helios both die you can still produce
a demo from any input video.

---

## Step 6 — Download model weights

Open a second terminal pane on the host and `docker exec` into the
running container (or just run these in the same shell — they take a
while):

```bash
pip install -U "huggingface_hub[cli]"

# Helios-Distilled — fastest variant, the only sane choice on Spark
huggingface-cli download BestWishYSH/Helios-Distilled \
  --local-dir /workspace/dreamloop/weights/Helios-Distilled

# Cosmos-Transfer1 7B Sample-AV — gated, requires login + license acceptance
huggingface-cli login                    # paste your HF token
huggingface-cli download nvidia/Cosmos-Transfer1-7B-Sample-AV \
  --local-dir /workspace/dreamloop/weights/Cosmos-Transfer1-7B-Sample-AV
```

Check progress in another shell: `du -sh /workspace/dreamloop/weights/*`.

**Hour-2 rule:** if Cosmos weights aren't fully downloaded by the end of
Hour 2, kill the download and commit to the fallback (Step 10b). Don't
keep waiting.

---

## Step 7 — Install Cosmos + Helios deps

```bash
cd /workspace/Cosmos-Drive-Dreams
pip install -r requirements.txt
pip install -r cosmos-transfer1/requirements.txt

# Cosmos smoke test on the bundled example
cd cosmos-drive-dreams-toolkits
python render_from_rds_hq.py \
  -i ../assets/example -o /tmp/cosmos_smoke \
  -d rds_hq --skip lidar --skip world_scenario
ls /tmp/cosmos_smoke                     # should contain hdmap/.../*.mp4
cd /workspace

cd /workspace/Helios
pip install -r requirements.txt
cd /workspace
```

If a pip install errors with `libcudart.so.12: cannot open shared object
file`, that package was built against CUDA 12 and the Spark only has
CUDA 13. Try `pip install <pkg> --no-deps` and install its non-torch
deps manually. Don't burn more than 15 minutes on any one stuck package
— drop it and move on.

---

## Step 8 — Drop your Waymo source clip in place

You need a Waymo segment as an mp4 (front camera). Place it at:

```bash
cp /path/to/your_waymo_segment.mp4 /workspace/dreamloop/clips/raw/segment_front.mp4
ls -la /workspace/dreamloop/clips/raw/segment_front.mp4
```

If you only have a TFRecord, extract to mp4 with `waymo-open-dataset`
tooling first. If you don't have Waymo access at all, any urban dashcam
mp4 will work for the demo — provenance doesn't show up on screen.

---

## Step 9 — Verify Helios CLI

This is the step that kills hackathon teams. The flag names in
`scripts/04_run_helios_flood.sh` are templated — verify them against
Helios's real entrypoint before running the full pipeline.

```bash
cd /workspace/Helios
ls *.py                                  # find the actual entrypoint
grep -A 20 -i "video.to.video\|v2v\|inference" README.md
```

If the entrypoint or flag names differ from what `04_run_helios_flood.sh`
has, fix that script now:

```bash
cd /workspace/dreamloop
vim scripts/04_run_helios_flood.sh       # update entrypoint + flag names
```

Then do a 24-frame test render to confirm the model loads and runs:

```bash
cd /workspace/Helios
# Substitute <entrypoint> and real flag names for your install
python <entrypoint>.py \
  --pretrained_model_name_or_path /workspace/dreamloop/weights/Helios-Distilled \
  --task v2v \
  --video_path /workspace/dreamloop/clips/raw/segment_front.mp4 \
  --prompt "wet street, light rain, photorealistic" \
  --num_frames 24 --fps 24 --width 768 --height 480 \
  --seed 17 \
  --output_path /tmp/helios_test.mp4

ls -la /tmp/helios_test.mp4
```

Time it. If 24 frames took 60 seconds, 121 frames takes ~5 minutes —
plan accordingly. If output is all black or garbage, tune
`image_noise_sigma_*` and `video_noise_sigma_*` in
`configs/flood_prompt.yaml`, or set `is_skip_first_chunk: true`.

---

## Step 10a — Run the full pipeline (Cosmos available)

```bash
cd /workspace/dreamloop
SRC_CLIP=clips/raw/segment_front.mp4 START=12 DUR=5 bash scripts/run_all.sh
```

`run_all.sh` runs every stage in order. Each stage is idempotent — if
something fails, fix it and re-run the orchestrator or step through the
individual scripts:

```bash
python scripts/01_trim_waymo.py --in clips/raw/segment_front.mp4 --start 12 --duration 5
bash scripts/03_run_cosmos.sh
python scripts/02_detect_boxes_yolo.py --video outputs/cosmos_base.mp4 --out data/boxes/waymo_clean.json
bash scripts/04_run_helios_flood.sh
python scripts/05_render_trained.py
python scripts/06_render_untrained.py
bash scripts/07_encode_h264.sh
```

---

## Step 10b — Fallback path (Cosmos broke or ran out of time)

Skip Cosmos. The pipeline runs Helios directly on the trimmed Waymo clip
and uses YOLO for ground-truth boxes. The demo story is intact because
the visual contrast lives in the perception comparison, not the model
provenance.

```bash
cd /workspace/dreamloop
python scripts/01_trim_waymo.py --in clips/raw/segment_front.mp4 --start 12 --duration 5
cp outputs/waymo_clean.mp4 outputs/cosmos_base.mp4
python scripts/02_detect_boxes_yolo.py --video outputs/cosmos_base.mp4 --out data/boxes/waymo_clean.json
IN=/workspace/dreamloop/outputs/waymo_clean.mp4 bash scripts/04_run_helios_flood.sh
python scripts/05_render_trained.py
python scripts/06_render_untrained.py
bash scripts/07_encode_h264.sh
```

---

## Step 11 — Verify all five files

```bash
ls -la /workspace/dreamloop/outputs/*.mp4

for f in /workspace/dreamloop/outputs/*.mp4; do
  echo "=== $f ==="
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,pix_fmt,width,height,r_frame_rate,duration \
    -of default=nw=1 "$f"
done
```

Every file must show `codec_name=h264` and `pix_fmt=yuv420p`. If
anything is `yuv444p`, Safari won't play it during the demo — re-run
`scripts/07_encode_h264.sh`.

---

## Step 12 — Pull the files off the Spark

Open a fresh shell on **your laptop** (not in the container, not in the
SSH session):

```bash
mkdir -p ~/dreamloop_demo
scp <you>@<dgx-spark-host>:~/dreamloop-workspace/dreamloop/outputs/*.mp4 ~/dreamloop_demo/

ls -la ~/dreamloop_demo/
# Expect exactly five files:
#   waymo_clean.mp4  cosmos_base.mp4  helios_flood.mp4
#   perception_trained.mp4  perception_untrained.mp4
```

Open each in Chrome to confirm playback **before pitch time**. Do this
the moment the files exist on the Spark — SSH dies at the worst
possible moment.

---

## Time gates

- **End of Hour 2** — if Cosmos isn't installed and downloaded, switch
  to Step 10b. Don't keep fighting it.
- **End of Hour 4** — Helios must have produced one watchable flooded
  clip. If not, drop resolution to 640x384 and `num_frames` to 73, and
  re-test.
- **End of Hour 7** — all five files must exist on the Spark in some
  form. The last hour is polish only.

---

## Troubleshooting

**`libcudart.so.12: cannot open shared object file`**
A package was built against CUDA 12 and the Spark has CUDA 13. Use
`pip install <pkg> --no-deps` and install the non-torch deps by hand.

**`torch.cuda.is_available()` is False inside the container**
Host is missing NVIDIA Container Toolkit:
`sudo apt install nvidia-container-toolkit && sudo systemctl restart docker`.
Exit and re-run the `docker run` line from Step 3.

**Helios first chunks look static**
Set `is_skip_first_chunk: true` in `configs/flood_prompt.yaml`, or bump
the `image_noise_sigma_min/max` and `video_noise_sigma_min/max` values.

**Boxes drift across frames in `perception_trained.mp4`**
YOLO was run on a different video than the one being overlaid (likely
different resolution or trim). Rerun `scripts/02_detect_boxes_yolo.py`
against the exact video that goes into the overlay
(`outputs/helios_flood.mp4` after it lands).

**`ffprobe` shows `pix_fmt=yuv444p` on an output**
Re-run `bash scripts/07_encode_h264.sh`. Don't ship `yuv444p` — it
won't play in Safari or on iOS.