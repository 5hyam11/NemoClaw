import { useState, useEffect, useRef, useCallback } from "react";

/** Temp asset keys → weather: waymo = normal, cosmos = rainy, helios = blizzard */
const VIDEO_ASSETS = {
  waymo: "/videos/dreamloop_sunny.avi",
  cosmos: "/videos/dreamloop_waymo.avi",
  helios: "/videos/dreamloop_blizzard.avi",
};

const WEATHER_COLUMNS = [
  {
    key: "waymo",
    pipeline: "Waymo",
    weather: "Normal",
    badge: "CLEAR",
    badgeTone: "neutral",
    src: VIDEO_ASSETS.waymo,
    footnote: "public/videos/dreamloop_sunny.mp4",
  },
  {
    key: "cosmos",
    pipeline: "Cosmos",
    weather: "Rainy",
    badge: "RAIN",
    badgeTone: "pipeline",
    src: VIDEO_ASSETS.cosmos,
    footnote: "public/videos/dreamloop_waymo.mp4",
  },
  {
    key: "helios",
    pipeline: "Helios",
    weather: "Blizzard",
    badge: "SNOW",
    badgeTone: "flood",
    src: VIDEO_ASSETS.helios,
    footnote: "public/videos/dreamloop_blizzard.mp4",
  },
];

/** Fallback when public/detections/{key}.json is missing (run scripts/run_yolo_tracking.py) */
const MOCK_CARS = [
  { id: 1, x: 0.12, y: 0.52, w: 0.14, h: 0.11, parked: true, label: "car", conf: 0.72 },
  { id: 2, x: 0.38, y: 0.48, w: 0.16, h: 0.12, parked: false, label: "car", conf: 0.91 },
  { id: 3, x: 0.58, y: 0.44, w: 0.18, h: 0.14, parked: false, label: "car", conf: 0.89 },
  { id: 4, x: 0.78, y: 0.5, w: 0.12, h: 0.1, parked: true, label: "car", conf: 0.68 },
];

const DETECTION_URLS = {
  waymo: "/detections/waymo.json",
  cosmos: "/detections/cosmos.json",
  helios: "/detections/helios.json",
};

/** Match scripts/yolo_tracking_config.yaml parked.score_threshold */
const DEFAULT_PARKED_SCORE_THRESHOLD = 0.55;

function parkedScoreThreshold(trackData) {
  return trackData?.parkedConfig?.scoreThreshold ?? DEFAULT_PARKED_SCORE_THRESHOLD;
}

function isParked(car, trackData) {
  if (car.parked === true) return true;
  const score = car.parkedScore;
  if (typeof score === "number") return score >= parkedScoreThreshold(trackData);
  return false;
}

function useDetectionTracks() {
  const [tracks, setTracks] = useState({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        Object.entries(DETECTION_URLS).map(async ([key, url]) => {
          try {
            const res = await fetch(url);
            if (!res.ok) return [key, null];
            return [key, await res.json()];
          } catch {
            return [key, null];
          }
        }),
      );
      if (!cancelled) {
        setTracks(Object.fromEntries(entries.filter(([, v]) => v)));
        setLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return { tracks, loaded, hasReal: Object.keys(tracks).length > 0 };
}

/** Nearest exported frame to current video time */
function sampleCars(trackData, videoTime) {
  if (!trackData?.frames?.length) return MOCK_CARS;
  const frames = trackData.frames;
  let best = frames[0];
  let bestDt = Math.abs((best.t ?? 0) - videoTime);
  for (let i = 1; i < frames.length; i++) {
    const dt = Math.abs((frames[i].t ?? 0) - videoTime);
    if (dt < bestDt) {
      bestDt = dt;
      best = frames[i];
    }
  }
  return best.cars?.length ? best.cars : MOCK_CARS;
}

const PERCEPTION_TABS = {
  raw: {
    id: "raw",
    label: "Raw feed",
    short: "No boxes",
    badge: "BASELINE",
    badgeTone: "neutral",
    description: "Waymo · Cosmos · Helios weather passes — no perception overlay",
    overlay: "none",
  },
  partial: {
    id: "partial",
    label: "YOLOv8 · partial",
    short: "All cars",
    badge: "PARTIAL TRAIN",
    badgeTone: "warn",
    description: "YOLOv8 detects every vehicle — parked cars still boxed (flicker in harsh weather)",
    overlay: "partial",
  },
  trained: {
    id: "trained",
    label: "YOLOv8 · DreamLoop",
    short: "Moving only",
    badge: "FULLY TRAINED",
    badgeTone: "success",
    description: "DreamLoop fine-tune suppresses parked vehicles — boxes only on traffic in-lane",
    overlay: "trained",
  },
};

const SCENARIO_MODES = {
  baseline: {
    buttonLabel: "No I2V",
    headline: "Multi-weather perception",
    description: "Compare clear, rain, and blizzard on the same route",
  },
  i2v: {
    buttonLabel: "I2V intervention",
    headline: "Multi-weather · I2V protected",
    description: "V2X beacon active — metrics reflect protected drive",
  },
};

const MOCK_SCENARIOS = {
  baseline: [
    { speed: 65, friction: 0.82, risk: 12, infra: "NOMINAL", label: "Clear conditions" },
    { speed: 62, friction: 0.71, risk: 18, infra: "NOMINAL", label: "Light rain ahead" },
    { speed: 58, friction: 0.55, risk: 28, infra: "NOMINAL", label: "Reduced visibility" },
    { speed: 52, friction: 0.41, risk: 38, infra: "NOMINAL", label: "Blizzard band" },
    { speed: 48, friction: 0.32, risk: 44, infra: "NOMINAL", label: "Parked clutter — high FP risk" },
    { speed: 45, friction: 0.28, risk: 41, infra: "NOMINAL", label: "Lane clear — moving targets only" },
  ],
  i2v: [
    { speed: 65, friction: 0.82, risk: 12, infra: "NOMINAL", label: "Approaching zone" },
    { speed: 58, friction: 0.74, risk: 18, infra: "BEACON ACTIVE", label: "V2X ping received" },
    { speed: 48, friction: 0.68, risk: 22, infra: "DECELERATING", label: "AV decelerating" },
    { speed: 38, friction: 0.55, risk: 19, infra: "DECELERATING", label: "Weather band" },
    { speed: 35, friction: 0.41, risk: 14, infra: "SAFE SPEED", label: "Parked filtered — stable track" },
    { speed: 35, friction: 0.39, risk: 11, infra: "SAFE SPEED", label: "Passage complete" },
  ],
};

function useMetrics(scenario, running) {
  const [frame, setFrame] = useState(0);
  const [history, setHistory] = useState([]);
  const intervalRef = useRef(null);

  useEffect(() => {
    setFrame(0);
    setHistory([]);
  }, [scenario]);

  useEffect(() => {
    if (!running) {
      clearInterval(intervalRef.current);
      return;
    }
    const frames = MOCK_SCENARIOS[scenario];
    intervalRef.current = setInterval(() => {
      setFrame((f) => {
        const next = f < frames.length - 1 ? f + 1 : f;
        setHistory((h) => [...h.slice(-19), frames[next]]);
        return next;
      });
    }, 1200);
    return () => clearInterval(intervalRef.current);
  }, [running, scenario]);

  const current = MOCK_SCENARIOS[scenario][frame];
  return { current, history, frame, total: MOCK_SCENARIOS[scenario].length };
}

function RiskBar({ value }) {
  const color =
    value > 70 ? "#D63B3A" : value > 40 ? "#D48806" : "#168F66";
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: "#7A8496", letterSpacing: "0.08em", textTransform: "uppercase" }}>Collision Risk</span>
        <span style={{ fontSize: 13, fontWeight: 600, color }}>{value}%</span>
      </div>
      <div style={{ height: 6, background: "#E8EDF4", borderRadius: 3, overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${value}%`,
            background: color,
            borderRadius: 3,
            transition: "width 0.8s ease, background 0.8s ease",
          }}
        />
      </div>
    </div>
  );
}

function MetricCard({ label, value, unit, accent }) {
  return (
    <div style={{
      background: "#FFFFFF",
      border: "1px solid #DDE4EE",
      borderRadius: 8,
      padding: "12px 14px",
      borderTop: accent ? `2px solid ${accent}` : "1px solid #DDE4EE",
      boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
    }}>
      <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent || "#2D3548", fontFamily: "'JetBrains Mono', monospace" }}>
        {value}<span style={{ fontSize: 12, fontWeight: 400, marginLeft: 3, color: "#8B95A8" }}>{unit}</span>
      </div>
    </div>
  );
}

function srcCandidates(src) {
  if (!src) return [];
  if (/\.avi$/i.test(src)) return [src.replace(/\.avi$/i, ".mp4"), src];
  return [src];
}

const BADGE_STYLES = {
  neutral: { bg: "#EEF1F6", color: "#5C6778" },
  pipeline: { bg: "#E8F0FA", color: "#2E6BA8" },
  flood: { bg: "#E8EEF8", color: "#3B5F8C" },
  warn: { bg: "#FEF6E6", color: "#B8740A" },
  success: { bg: "#E6F5EE", color: "#168F66" },
};

function jitter(box, t, id, amount = 0.012) {
  const phase = id * 1.7;
  return {
    x: box.x + Math.sin(t * 3.2 + phase) * amount,
    y: box.y + Math.cos(t * 2.8 + phase) * amount * 0.6,
    w: box.w + Math.sin(t * 4 + phase) * amount * 0.4,
    h: box.h + Math.cos(t * 3.5 + phase) * amount * 0.3,
  };
}

function drawDetections(ctx, w, h, overlayMode, videoTime, weatherKey, cars, trackData) {
  const weatherJitter = weatherKey === "helios" ? 0.018 : weatherKey === "cosmos" ? 0.01 : 0.006;
  const useMock = cars === MOCK_CARS;
  const inferLabel = trackData?.model
    ? `${trackData.model} @ ${trackData.imgsz || "?"}px`
    : "YOLOv8n";

  cars.forEach((car) => {
    const base = useMock
      ? jitter(car, videoTime, car.id, overlayMode === "partial" ? weatherJitter : 0.004)
      : car;
    const parked = isParked(car, trackData);
    const px = base.x * w;
    const py = base.y * h;
    const pw = base.w * w;
    const ph = base.h * h;

    if (overlayMode === "trained" && parked) {
      if (useMock) {
        ctx.save();
        ctx.strokeStyle = "rgba(120, 130, 150, 0.35)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1;
        ctx.strokeRect(px, py, pw, ph);
        ctx.fillStyle = "rgba(30, 38, 56, 0.55)";
        ctx.font = "10px JetBrains Mono, monospace";
        ctx.fillText("parked · suppressed", px + 4, py + ph - 6);
        ctx.restore();
      }
      return;
    }

    if (overlayMode === "partial" && parked) {
      const flicker = Math.sin(videoTime * 9 + car.id * 2.1) > -0.15;
      if (!flicker) return;
    }

    const conf = car.conf ?? (
      overlayMode === "partial" && parked
        ? 0.55 + Math.abs(Math.sin(videoTime * 5 + car.id)) * 0.25
        : 0.88 + Math.abs(Math.sin(videoTime * 2 + car.id)) * 0.1
    );

    const color = parked && overlayMode === "partial" ? "#D48806" : "#00E5A0";
    const lineW = parked && overlayMode === "partial" ? 1.5 : 2;

    ctx.strokeStyle = color;
    ctx.lineWidth = lineW;
    ctx.strokeRect(px, py, pw, ph);

    const tag = `${car.label} ${conf.toFixed(2)}`;
    const tagW = ctx.measureText ? 0 : 0;
    void tagW;
    ctx.font = "bold 11px JetBrains Mono, monospace";
    const tw = ctx.measureText(tag).width + 8;
    const th = 16;
    ctx.fillStyle = color;
    ctx.fillRect(px, Math.max(0, py - th), tw, th);
    ctx.fillStyle = "#0B1220";
    ctx.fillText(tag, px + 4, Math.max(12, py - 5));

    if (overlayMode === "partial" && parked) {
      ctx.fillStyle = "rgba(212, 136, 6, 0.85)";
      ctx.font = "9px Inter, sans-serif";
      const hint = typeof car.parkedScore === "number" ? `parked ${car.parkedScore.toFixed(2)}` : "parked?";
      ctx.fillText(hint, px + 4, py + ph - 4);
    }
  });

  if (overlayMode === "partial") {
    ctx.fillStyle = "rgba(15, 23, 42, 0.72)";
    ctx.font = "10px Inter, sans-serif";
    ctx.fillText(`${inferLabel} · all vehicles · parked shown`, 8, h - 10);
  } else if (overlayMode === "trained") {
    ctx.fillStyle = "rgba(15, 23, 42, 0.72)";
    ctx.font = "10px Inter, sans-serif";
    const th = parkedScoreThreshold(trackData);
    ctx.fillText(`${inferLabel} · DreamLoop · parked score < ${th} only`, 8, h - 10);
  }
}

function YoloOverlay({ videoRef, overlayMode, weatherKey, trackData, active }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  const paint = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !active || overlayMode === "none") return;

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.floor(rect.width * dpr));
    const h = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, w, h);
    const cars = sampleCars(trackData, video.currentTime || 0);
    drawDetections(ctx, w, h, overlayMode, video.currentTime || 0, weatherKey, cars, trackData);
  }, [videoRef, overlayMode, weatherKey, trackData, active]);

  useEffect(() => {
    if (!active || overlayMode === "none") {
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
      }
      cancelAnimationFrame(rafRef.current);
      return;
    }

    const loop = () => {
      paint();
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, overlayMode, paint]);

  if (overlayMode === "none") return null;

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 3,
      }}
    />
  );
}

function WeatherVideoPanel({ column, overlayMode, trackData }) {
  const badgeStyle = BADGE_STYLES[column.badgeTone] || BADGE_STYLES.neutral;
  const [resolvedSrc, setResolvedSrc] = useState(null);
  const [videoOk, setVideoOk] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    setVideoOk(false);
    setVideoError(false);
    if (!column.src) {
      setResolvedSrc("");
      return;
    }
    let cancelled = false;
    const candidates = srcCandidates(column.src);

    (async () => {
      let chosen = column.src;
      for (const url of candidates) {
        try {
          const res = await fetch(url, { method: "HEAD" });
          if (res.ok) {
            chosen = url;
            break;
          }
        } catch {
          /* try next */
        }
      }
      if (!cancelled) setResolvedSrc(chosen);
    })();

    return () => { cancelled = true; };
  }, [column.src, column.key]);

  return (
    <div style={{
      background: "#FFFFFF",
      border: "1px solid #DDE4EE",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      height: "100%",
      minHeight: 280,
      boxShadow: "0 1px 3px rgba(15, 23, 42, 0.05)",
    }}>
      <div style={{
        padding: "10px 14px",
        borderBottom: "1px solid #E8EDF4",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 8,
        background: "#FAFBFD",
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#1E2638" }}>{column.pipeline}</div>
          <div style={{ fontSize: 11, color: "#6B7689", marginTop: 2 }}>{column.weather}</div>
        </div>
        <span style={{
          fontSize: 10,
          padding: "2px 8px",
          borderRadius: 4,
          background: badgeStyle.bg,
          color: badgeStyle.color,
          fontWeight: 600,
          letterSpacing: "0.05em",
          flexShrink: 0,
        }}>{column.badge}</span>
      </div>

      <div style={{ flex: 1, minHeight: 200, background: "#0F1419", position: "relative", overflow: "hidden" }}>
        {(!videoOk || videoError) && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            padding: 12, textAlign: "center",
            background: "linear-gradient(135deg, #1a2233 0%, #0f1419 100%)",
            zIndex: 2,
          }}>
            <div style={{ fontSize: 10, color: "#9AA5B8", fontFamily: "monospace", marginBottom: 4 }}>{resolvedSrc || column.src}</div>
            <div style={{ fontSize: 10, color: "#7A8496", lineHeight: 1.4 }}>{column.footnote}</div>
            {videoError && (
              <div style={{ fontSize: 10, color: "#D63B3A", marginTop: 8, lineHeight: 1.4, maxWidth: 220 }}>
                Cannot play clip. Re-encode: python scripts/avi_to_mp4.py
              </div>
            )}
          </div>
        )}
        {resolvedSrc && (
          <video
            ref={videoRef}
            key={resolvedSrc}
            src={resolvedSrc}
            autoPlay
            loop
            muted
            playsInline
            preload="auto"
            onLoadedData={() => {
              setVideoOk(true);
              setVideoError(false);
            }}
            onError={() => {
              setVideoOk(false);
              setVideoError(true);
            }}
            style={{
              width: "100%", height: "100%", objectFit: "cover",
              position: "relative", zIndex: 1,
              display: videoOk && !videoError ? "block" : "none",
            }}
          />
        )}
        <YoloOverlay
          videoRef={videoRef}
          overlayMode={overlayMode}
          weatherKey={column.key}
          trackData={trackData}
          active={videoOk && !videoError}
        />
      </div>
    </div>
  );
}

function InfraStatus({ status }) {
  const colors = {
    NOMINAL: { bg: "#E8F5EE", text: "#168F66", dot: "#168F66" },
    "BEACON ACTIVE": { bg: "#FEF6E6", text: "#B8740A", dot: "#D48806" },
    DECELERATING: { bg: "#FEF6E6", text: "#B8740A", dot: "#D48806" },
    "SAFE SPEED": { bg: "#E8F5EE", text: "#168F66", dot: "#168F66" },
  };
  const c = colors[status] || colors.NOMINAL;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      background: c.bg, borderRadius: 6, padding: "6px 12px",
      border: `1px solid ${c.dot}33`,
    }}>
      <div style={{ width: 7, height: 7, borderRadius: "50%", background: c.dot }} />
      <span style={{ fontSize: 11, fontWeight: 700, color: c.text, letterSpacing: "0.08em" }}>{status}</span>
    </div>
  );
}

export default function App() {
  const [scenario] = useState("baseline");
  const [perceptionTab, setPerceptionTab] = useState("raw");
  const [running, setRunning] = useState(false);
  const { tracks: detectionTracks, loaded: detectionsLoaded, hasReal: hasRealDetections } = useDetectionTracks();
  const { current, history, frame, total } = useMetrics(scenario, running);
  const mode = SCENARIO_MODES[scenario];
  const tab = PERCEPTION_TABS[perceptionTab];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#F0F3F8",
      color: "#3D4659",
      fontFamily: "'Inter', system-ui, sans-serif",
      padding: "0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        button { cursor: pointer; font-family: inherit; }
      `}</style>

      <div style={{
        borderBottom: "1px solid #DDE4EE",
        padding: "14px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "#FAFBFD",
        boxShadow: "0 1px 0 rgba(15, 23, 42, 0.04)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #2DB88A, #3B7FC4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
            color: "#fff",
          }}>⟳</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#1E2638", letterSpacing: "-0.01em" }}>DreamLoop</div>
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase" }}>YOLOv8 · parked-car filter · weather matrix</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={() => setRunning((r) => !r)}
            style={{
              padding: "6px 18px",
              borderRadius: 6,
              border: "none",
              background: running ? "#FCE8E8" : "#168F66",
              color: running ? "#D63B3A" : "#fff",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.04em",
              transition: "all 0.2s",
              boxShadow: running ? "none" : "0 1px 3px rgba(22, 143, 102, 0.25)",
            }}
          >
            {running ? "■ STOP" : "▶ RUN"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", minHeight: "calc(100vh - 61px)" }}>
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{
            background: "#FFFFFF",
            border: "1px solid #DDE4EE",
            borderRadius: 8,
            padding: "10px 16px",
            boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
          }}>
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>
              Perception mode
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#1E2638" }}>{mode.headline}</div>
                <div style={{ fontSize: 11, color: "#6B7689", marginTop: 2 }}>{tab.description}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 11, color: "#8B95A8" }}>Frame {frame + 1}/{total}</span>
                <InfraStatus status={current.infra} />
              </div>
            </div>
          </div>

          <div style={{
            display: "flex",
            gap: 6,
            flexWrap: "wrap",
            padding: 4,
            background: "#EEF1F6",
            borderRadius: 8,
            border: "1px solid #DDE4EE",
          }}>
            {Object.values(PERCEPTION_TABS).map((t) => {
              const active = perceptionTab === t.id;
              const tone = BADGE_STYLES[t.badgeTone] || BADGE_STYLES.neutral;
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    setPerceptionTab(t.id);
                    setRunning(false);
                  }}
                  style={{
                    flex: "1 1 140px",
                    padding: "10px 12px",
                    borderRadius: 6,
                    border: active ? "1px solid #168F66" : "1px solid transparent",
                    background: active ? "#FFFFFF" : "transparent",
                    textAlign: "left",
                    transition: "all 0.2s",
                    boxShadow: active ? "0 1px 3px rgba(15, 23, 42, 0.08)" : "none",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: active ? "#168F66" : "#4A5568" }}>{t.label}</span>
                    <span style={{
                      fontSize: 9,
                      padding: "2px 6px",
                      borderRadius: 3,
                      background: tone.bg,
                      color: tone.color,
                      fontWeight: 600,
                    }}>{t.badge}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "#8B95A8", marginTop: 4 }}>{t.short}</div>
                </button>
              );
            })}
          </div>

          <div style={{
            padding: "8px 16px",
            borderRadius: 6,
            background: current.risk > 70 ? "#FDF0F0" : current.risk > 40 ? "#FEF8EB" : "#EDF8F3",
            border: `1px solid ${current.risk > 70 ? "#D63B3A44" : current.risk > 40 ? "#D4880644" : "#168F6644"}`,
            fontSize: 12,
            color: current.risk > 70 ? "#C42E2D" : current.risk > 40 ? "#B8740A" : "#168F66",
            fontWeight: 600,
            letterSpacing: "0.04em",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            ▸ {current.label}
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 12,
            flex: 1,
            alignItems: "stretch",
            minHeight: 320,
          }}>
            {WEATHER_COLUMNS.map((col) => (
              <WeatherVideoPanel
                key={col.key}
                column={col}
                overlayMode={tab.overlay}
                trackData={detectionTracks[col.key]}
              />
            ))}
          </div>

          <div style={{
            background: "#FFFFFF",
            border: "1px solid #DDE4EE",
            borderRadius: 8,
            padding: "10px 16px",
            boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
          }}>
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>Risk timeline</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 40 }}>
              {history.map((h, i) => {
                const color = h.risk > 70 ? "#D63B3A" : h.risk > 40 ? "#D48806" : "#168F66";
                return (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: `${(h.risk / 100) * 40}px`,
                      background: color,
                      borderRadius: 2,
                      opacity: 0.35 + (i / Math.max(history.length, 1)) * 0.65,
                      transition: "height 0.4s ease",
                    }}
                  />
                );
              })}
              {history.length === 0 && (
                <span style={{ fontSize: 11, color: "#9AA5B8" }}>Hit RUN to animate metrics</span>
              )}
            </div>
          </div>
        </div>

        <div style={{
          borderLeft: "1px solid #DDE4EE",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          background: "#FAFBFD",
        }}>
          <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase" }}>Live metrics</div>

          <MetricCard
            label="Vehicle Speed"
            value={current.speed}
            unit="MPH"
            accent={current.speed > 55 ? "#D63B3A" : current.speed > 40 ? "#D48806" : "#168F66"}
          />
          <MetricCard
            label="Road Friction"
            value={current.friction.toFixed(2)}
            unit="μ"
            accent={current.friction < 0.2 ? "#D63B3A" : current.friction < 0.5 ? "#D48806" : "#168F66"}
          />

          <div style={{
            background: "#FFFFFF",
            border: "1px solid #DDE4EE",
            borderRadius: 8,
            padding: "12px 14px",
            boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
          }}>
            <RiskBar value={current.risk} />
          </div>

          <div style={{
            background: "#FFFFFF",
            border: "1px solid #DDE4EE",
            borderRadius: 8,
            padding: "12px 14px",
            boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
          }}>
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>Infrastructure</div>
            <InfraStatus status={current.infra} />
          </div>

          <div style={{
            marginTop: "auto",
            background: "#FFFFFF",
            border: "1px solid #DDE4EE",
            borderRadius: 8,
            padding: "12px 14px",
            boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
          }}>
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>Perception stack</div>
            {[
              { name: "YOLOv8n detector", status: perceptionTab === "raw" ? "idle" : "active" },
              { name: "Parked-car filter", status: perceptionTab === "trained" ? "active" : perceptionTab === "partial" ? "learning" : "idle" },
              { name: "Weather passes", status: "ready" },
              { name: "NemoClaw train", status: running ? "active" : "idle" },
            ].map((p) => (
              <div key={p.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: "#6B7689" }}>{p.name}</span>
                <span style={{
                  fontSize: 10,
                  padding: "2px 7px",
                  borderRadius: 4,
                  background: p.status === "active" ? "#E6F5EE" : p.status === "ready" || p.status === "learning" ? "#E8F0FA" : "#EEF1F6",
                  color: p.status === "active" ? "#168F66" : p.status === "ready" || p.status === "learning" ? "#2E6BA8" : "#8B95A8",
                  fontWeight: 600,
                }}>{p.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
