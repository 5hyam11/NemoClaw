# DreamLoop UI

Web dashboard for the flood demo: four pipeline video panels, live-style metrics, and a before/after perception comparison.

## Requirements

- [Node.js](https://nodejs.org/) 18+ (includes `npm`)

## Boot up the web UI

From the repo root:

```bash
cd NemoClaw/dreamloop-ui
npm install
npm run dev
```

Open the URL Vite prints in the terminal:

| Where | URL |
|--------|-----|
| This machine | http://localhost:5173 |
| Other devices on the same Wi‑Fi | `http://<your-lan-ip>:5173` (shown as **Network** in the terminal) |

`npm run dev` runs Vite with `--host`, so judges or teammates on the same network can open the dashboard from a phone or laptop without extra config.

### Other commands

```bash
npm run build    # production bundle → dist/
npm run preview  # serve the built site locally (also uses --host)
```

---

## How to use the dashboard

1. **Start the dev server** (see above) and open http://localhost:5173.
2. **No I2V** — flood scenario without roadside beacon (default). Metrics simulate high speed and rising collision risk when you press **RUN**.
3. **▶ RUN** — advances mock metrics every ~1.2s (speed, friction, risk, infrastructure status, event label, risk timeline). Press **■ STOP** to pause.
4. **Video panels** — panels 1–3 show the same scene through the pipeline; panel 4 shows **before** (untrained) and **after** (DreamLoop) side by side in one box. The active scenario gets a green outline on the matching half of panel 4.
5. **I2V intervention** — currently commented out in `src/App.jsx`. Uncomment that button when you want the protected-drive story and trained-side highlight again.

If video files are missing, placeholders show the expected path under each panel. Metrics still run from built-in mock data.

---

## Replace videos

Clips are served from `public/videos/`. Vite exposes anything in `public/` at the site root, so `public/videos/foo.avi` is available as `/videos/foo.avi`.

The UI expects **AVI** files by default (typical pipeline output). You can point `VIDEO_ASSETS` at `.mp4` or other extensions if you change the paths in `App.jsx`.

### 1. Add or replace files (easiest)

Create the folder if needed, then copy your AVIs with **these exact names**:

| File | Panel | What it should be |
|------|--------|-------------------|
| `waymo_input.avi` | 01 — Waymo input | Clean baseline Waymo clip (same clip every run) |
| `cosmos_geometry.avi` | 02 — Cosmos geometry | Same clip with bounding boxes burned in |
| `helios_flood.avi` | 03 — Helios flood render | Flood weather on that scene (rain, standing water, spray) |
| `result_untrained_storm.avi` | 04 — Before | Glitchy / lost boxes in the storm (untrained) |
| `result_trained_storm.avi` | 04 — After | Stable boxes through the flood (DreamLoop-trained) |

Optional later:

| File | Purpose |
|------|---------|
| `pedestrian_example.avi` | Second scenario (not wired in the UI yet; path reserved in `App.jsx`) |

**No rebuild required** — save the file, refresh the browser. While **RUN** is active, videos loop with `autoPlay` (muted).

If your files use different names, either rename them to match the table or update `VIDEO_ASSETS` in `src/App.jsx` (see below).

### 2. Use different filenames

Edit `VIDEO_ASSETS` at the top of `src/App.jsx`:

```js
const VIDEO_ASSETS = {
  waymo: "/videos/your_waymo_clip.avi",
  cosmos: "/videos/your_cosmos_clip.avi",
  helios: "/videos/your_helios_clip.avi",
  resultUntrained: "/videos/your_untrained_result.avi",
  resultTrained: "/videos/your_trained_result.avi",
  pedestrian: "/videos/pedestrian_example.avi",
};
```

Paths must start with `/videos/` if files live under `public/videos/`.

### 3. If a clip does not play in the browser

HTML `<video>` support for AVI depends on the codec inside the file (often fine on Chrome/Edge for MJPEG or some H.264 AVIs; less reliable on Safari).

If a panel stays on the placeholder after refresh:

1. Open DevTools → **Network** and confirm the `.avi` returns **200** (file path/name correct).
2. Try the same clip in the browser address bar: `http://localhost:5173/videos/waymo_input.avi`.
3. Re-encode to MP4 for the demo (keeps quality, works everywhere), then either replace the file or update paths:

```bash
ffmpeg -i waymo_input.avi -c:v libx264 -crf 23 -an waymo_input.mp4
```

Then set e.g. `waymo: "/videos/waymo_input.mp4"` in `VIDEO_ASSETS`.

### Tips

- Keep clips **short and loop-friendly**; the UI sets `loop` on all `<video>` elements.
- Panels 1–3 should be the **same underlying scene** at different processing stages; panel 4 compares two perception outputs on the Helios flood footage.

---

## Live metrics (optional)

By default, metrics come from `MOCK_SCENARIOS` in `App.jsx`. To drive the sidebar from a file instead, put `metrics.json` in `public/` and fetch it on an interval while **RUN** is active.

Example schema:

```json
{
  "speed": 65,
  "friction": 0.38,
  "risk": 58,
  "infra": "NOMINAL",
  "label": "Standing water detected"
}
```

See comments in `App.jsx` or wire a `fetch('/metrics.json')` loop in `useMetrics` when your pipeline is ready.

---

## Fallback demo mode

If upstream video generation is not ready, **RUN** still animates realistic mock numbers. Use that for dry runs; drop real AVIs into `public/videos/` when clips are available.

---

## Project layout

```
dreamloop-ui/
├── public/
│   └── videos/          ← put AVIs here (or MP4 if you change paths)
├── src/
│   ├── App.jsx          ← panels, metrics, VIDEO_ASSETS paths
│   └── main.jsx
├── index.html
├── package.json
└── vite.config.js       ← port 5173, host enabled
```
