# DreamLoop UI — Setup Guide

## Start in 3 commands

```bash
cd dreamloop-ui
npm install
npm run dev
```

Your dashboard is now live at:
- **Local:** http://localhost:5173
- **Network (share with judges):** http://192.168.x.x:5173  ← Vite prints this on startup

The `--host` flag is already set in vite.config.js so any device on the same WiFi can hit it.

---

## Connecting real data from Person 3

Replace the mock `MOCK_SCENARIOS` data in `App.jsx` with a live fetch from `metrics.json`:

```js
useEffect(() => {
  if (!running) return;
  const interval = setInterval(async () => {
    const res = await fetch('/metrics.json');
    const data = await res.json();
    setCurrent(data);
  }, 1000);
  return () => clearInterval(interval);
}, [running]);
```

Put `metrics.json` in the `public/` folder — Vite serves it automatically at `/metrics.json`.

Person 3 writes to: `dreamloop-ui/public/metrics.json`

**Agree on this schema with Person 3 immediately:**
```json
{
  "speed": 65,
  "friction": 0.38,
  "risk": 58,
  "infra": "NOMINAL",
  "label": "Standing water detected"
}
```

---

## Connecting real video panels

Each of the 4 `<VideoPanel>` components in the grid is a placeholder.
Replace with `<video>` tags once Person 2 has clips:

```jsx
<video
  src="/videos/helios_flood_01.mp4"
  autoPlay
  loop
  muted
  playsInline
  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
/>
```

Put `.mp4` files in `public/videos/` and they serve instantly — no config needed.

---

## Fallback mode

If the DGX pipeline stalls during the demo, the mock scenario data
(built into `App.jsx`) runs perfectly offline. Just hit RUN and
the dashboard animates through both scenarios with realistic numbers.

Keep this as your safety net.
