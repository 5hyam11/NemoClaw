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

Clips are served from `public/videos/`. Vite exposes anything in `public/` at the site root, so `public/videos/foo.mp4` is available as `/videos/foo.mp4`.

### 1. Add or replace files (easiest)

Create the folder if needed, then drop in MP4s with **these exact names**:

| File | Panel | What it should be |
|------|--------|-------------------|
| `waymo_input.mp4` | 01 — Waymo input | Clean baseline Waymo clip (same clip every run) |
| `cosmos_geometry.mp4` | 02 — Cosmos geometry | Same clip with bounding boxes burned in |
| `helios_flood.mp4` | 03 — Helios flood render | Flood weather on that scene (rain, standing water, spray) |
| `result_untrained_storm.mp4` | 04 — Before | Glitchy / lost boxes in the storm (untrained) |
| `result_trained_storm.mp4` | 04 — After | Stable boxes through the flood (DreamLoop-trained) |

Optional later:

| File | Purpose |
|------|---------|
| `pedestrian_example.mp4` | Second scenario (not wired in the UI yet; path reserved in `App.jsx`) |

**No rebuild required** — save the file, refresh the browser. While **RUN** is active, videos loop with `autoPlay` (muted).

### 2. Use different filenames

Edit `VIDEO_ASSETS` at the top of `src/App.jsx`:

```js
const VIDEO_ASSETS = {
  waymo: "/videos/your_waymo_clip.mp4",
  cosmos: "/videos/your_cosmos_clip.mp4",
  helios: "/videos/your_helios_clip.mp4",
  resultUntrained: "/videos/your_untrained_result.mp4",
  resultTrained: "/videos/your_trained_result.mp4",
  pedestrian: "/videos/pedestrian_example.mp4",
};
```

Paths must start with `/videos/` if files live under `public/videos/`.

### Tips

- Prefer **H.264 MP4** for broad browser support.
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

If upstream video generation is not ready, **RUN** still animates realistic mock numbers. Use that for dry runs; drop real MP4s into `public/videos/` when clips are available.

---

## Project layout

```
dreamloop-ui/
├── public/
│   └── videos/          ← put MP4s here
├── src/
│   ├── App.jsx          ← panels, metrics, VIDEO_ASSETS paths
│   └── main.jsx
├── index.html
├── package.json
└── vite.config.js       ← port 5173, host enabled
```
