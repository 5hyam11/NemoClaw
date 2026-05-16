import { useState, useEffect, useRef } from "react";

// #region agent log
const debugLog = (location, message, data, hypothesisId) => {
  fetch("http://127.0.0.1:7353/ingest/8bcebfee-df1d-41b5-b75b-5399f9e91c98", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "83c992" },
    body: JSON.stringify({
      sessionId: "83c992",
      location,
      message,
      data,
      hypothesisId,
      timestamp: Date.now(),
      runId: "pre-fix",
    }),
  }).catch(() => {});
};
// #endregion

/**
 * Panels 1–3: same flood clip at each pipeline stage (unchanged by top buttons).
 * Panel 4: untrained vs DreamLoop result on that Helios flood scene.
 * Top buttons: simulate vehicle + I2V metrics only (not different source footage).
 */
const VIDEO_ASSETS = {
  waymo: "/videos/waymo_input.avi",
  cosmos: "/videos/cosmos_geometry.avi",
  helios: "/videos/dreamloop_blizzard.avi", // UI prefers .mp4 sibling when present (see srcCandidates)
  resultUntrained: "/videos/result_untrained_storm.avi",
  resultTrained: "/videos/result_trained_storm.avi",
  pedestrian: "/videos/pedestrian_example.avi",
};

const SCENARIO_MODES = {
  baseline: {
    buttonLabel: "No I2V",
    headline: "Flood — unprotected",
    description: "No roadside beacon · AV holds speed · collision risk rises",
    panel4Caption: "Untrained model — boxes flicker and lose vehicles in the storm",
    resultSrc: VIDEO_ASSETS.resultUntrained,
    resultBadge: "FAILING IN STORM",
    resultTone: "fail",
  },
  i2v: {
    buttonLabel: "I2V intervention",
    headline: "Flood — I2V protected",
    description: "V2X beacon warns AV · slows before standing water · risk stays low",
    panel4Caption: "DreamLoop-trained — tight boxes through rain and standing water",
    resultSrc: VIDEO_ASSETS.resultTrained,
    resultBadge: "TRACKING IN STORM",
    resultTone: "success",
  },
};

const MOCK_SCENARIOS = {
  baseline: [
    { speed: 65, friction: 0.82, risk: 12, infra: "NOMINAL", label: "Approaching zone" },
    { speed: 65, friction: 0.61, risk: 31, infra: "NOMINAL", label: "Entering flood zone" },
    { speed: 64, friction: 0.38, risk: 58, infra: "NOMINAL", label: "Standing water detected" },
    { speed: 63, friction: 0.19, risk: 79, infra: "NOMINAL", label: "Hydroplane onset" },
    { speed: 62, friction: 0.08, risk: 94, infra: "NOMINAL", label: "CRITICAL — loss of traction" },
    { speed: 61, friction: 0.04, risk: 98, infra: "NOMINAL", label: "COLLISION RISK" },
  ],
  i2v: [
    { speed: 65, friction: 0.82, risk: 12, infra: "NOMINAL", label: "Approaching zone" },
    { speed: 58, friction: 0.74, risk: 18, infra: "BEACON ACTIVE", label: "V2X ping received" },
    { speed: 48, friction: 0.68, risk: 22, infra: "DECELERATING", label: "AV decelerating" },
    { speed: 38, friction: 0.55, risk: 19, infra: "DECELERATING", label: "Entering flood zone" },
    { speed: 35, friction: 0.41, risk: 14, infra: "SAFE SPEED", label: "Standing water — safe" },
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

/** Prefer browser-playable MP4 over MJPEG AVI when both exist under public/videos/ */
function srcCandidates(src) {
  if (!src) return [];
  if (/\.avi$/i.test(src)) return [src.replace(/\.avi$/i, ".mp4"), src];
  return [src];
}

const BADGE_STYLES = {
  neutral: { bg: "#EEF1F6", color: "#5C6778" },
  pipeline: { bg: "#E8F0FA", color: "#2E6BA8" },
  flood: { bg: "#E8EEF8", color: "#3B5F8C" },
  fail: { bg: "#FCE8E8", color: "#D63B3A" },
  success: { bg: "#E6F5EE", color: "#168F66" },
};

function VideoPanel({ title, badge, badgeTone = "neutral", src, caption, footnote, playing }) {
  const badgeStyle = BADGE_STYLES[badgeTone] || BADGE_STYLES.neutral;
  const [resolvedSrc, setResolvedSrc] = useState(null);
  const [videoOk, setVideoOk] = useState(false);
  const [videoError, setVideoError] = useState(false);

  useEffect(() => {
    setVideoOk(false);
    setVideoError(false);
    if (!src) {
      setResolvedSrc("");
      return;
    }
    let cancelled = false;
    const candidates = srcCandidates(src);

    (async () => {
      // #region agent log
      debugLog("App.jsx:VideoPanel:useEffect", "panel mount src", { src, title, candidates }, "H5");
      // #endregion
      let chosen = src;
      for (const url of candidates) {
        try {
          const res = await fetch(url, { method: "HEAD" });
          // #region agent log
          debugLog(
            "App.jsx:VideoPanel:HEAD",
            "asset HTTP check",
            {
              src,
              url,
              title,
              status: res.status,
              ok: res.ok,
              contentType: res.headers.get("content-type"),
              contentLength: res.headers.get("content-length"),
            },
            res.ok ? "H2" : "H2"
          );
          // #endregion
          if (res.ok) {
            chosen = url;
            break;
          }
        } catch (err) {
          // #region agent log
          debugLog("App.jsx:VideoPanel:HEAD", "asset fetch failed", { url, title, err: String(err) }, "H2");
          // #endregion
        }
      }
      if (!cancelled) {
        // #region agent log
        debugLog("App.jsx:VideoPanel:resolve", "chosen playable src", { src, chosen, title }, "H4");
        // #endregion
        setResolvedSrc(chosen);
      }
    })();

    return () => { cancelled = true; };
  }, [src, title]);

  return (
    <div style={{
      background: "#FFFFFF",
      border: "1px solid #DDE4EE",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      height: "100%",
      boxShadow: "0 1px 3px rgba(15, 23, 42, 0.05)",
    }}>
      <div style={{
        padding: "8px 14px",
        borderBottom: "1px solid #E8EDF4",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 8,
        background: "#FAFBFD",
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#5C6778", letterSpacing: "0.06em", textTransform: "uppercase" }}>{title}</div>
          {caption && (
            <div style={{ fontSize: 10, color: "#8B95A8", marginTop: 3, lineHeight: 1.35 }}>{caption}</div>
          )}
        </div>
        {badge && (
          <span style={{
            fontSize: 10,
            padding: "2px 8px",
            borderRadius: 4,
            background: badgeStyle.bg,
            color: badgeStyle.color,
            fontWeight: 600,
            letterSpacing: "0.05em",
            flexShrink: 0,
          }}>{badge}</span>
        )}
      </div>
      <div style={{ flex: 1, minHeight: 140, background: "#EEF1F6", position: "relative", overflow: "hidden" }}>
        {(!videoOk || videoError) && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            padding: 12, textAlign: "center",
            background: "linear-gradient(135deg, #F4F7FB 0%, #EEF2F8 100%)",
            zIndex: 2,
          }}>
            <div style={{ fontSize: 10, color: "#7A8496", fontFamily: "monospace", marginBottom: 4 }}>{resolvedSrc || src || "awaiting clip"}</div>
            <div style={{ fontSize: 10, color: "#9AA5B8", lineHeight: 1.4 }}>{footnote}</div>
            {videoError && (
              <div style={{ fontSize: 10, color: "#D63B3A", marginTop: 8, lineHeight: 1.4, maxWidth: 220 }}>
                Cannot play {resolvedSrc || src}. Re-encode to H.264 MP4: python scripts/avi_to_mp4.py
              </div>
            )}
          </div>
        )}
        {resolvedSrc && (
          <video
            key={resolvedSrc}
            src={resolvedSrc}
            autoPlay
            loop
            muted
            playsInline
            preload="auto"
            onLoadedData={(e) => {
              const v = e.currentTarget;
              // #region agent log
              debugLog(
                "App.jsx:VideoPanel:onLoadedData",
                "video decoded",
                { src, resolvedSrc, title, w: v.videoWidth, h: v.videoHeight, duration: v.duration, runId: "post-fix" },
                "H5"
              );
              // #endregion
              setVideoOk(true);
              setVideoError(false);
            }}
            onError={(e) => {
              const v = e.currentTarget;
              const err = v.error;
              // #region agent log
              debugLog(
                "App.jsx:VideoPanel:onError",
                "video element error",
                {
                  src,
                  resolvedSrc,
                  title,
                  code: err?.code,
                  message: err?.message,
                  runId: "post-fix",
                  MEDIA_ERR_ABORTED: 1,
                  MEDIA_ERR_NETWORK: 2,
                  MEDIA_ERR_DECODE: 3,
                  MEDIA_ERR_SRC_NOT_SUPPORTED: 4,
                },
                err?.code === 4 ? "H4" : err?.code === 3 ? "H1" : "H1"
              );
              // #endregion
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
      </div>
    </div>
  );
}

function ResultComparePanel({ scenario, playing }) {
  const mode = SCENARIO_MODES[scenario];
  const untrained = SCENARIO_MODES.baseline;
  const trained = SCENARIO_MODES.i2v;

  return (
    <div style={{
      background: "#FFFFFF",
      border: "1px solid #DDE4EE",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      height: "100%",
      boxShadow: "0 1px 3px rgba(15, 23, 42, 0.05)",
    }}>
      <div style={{
        padding: "8px 14px",
        borderBottom: "1px solid #E8EDF4",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 8,
        background: "#FAFBFD",
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#5C6778", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            04 — Before / after
          </div>
          <div style={{ fontSize: 10, color: "#8B95A8", marginTop: 3, lineHeight: 1.35 }}>
            Same Helios flood · green outline = active run
          </div>
        </div>
        <span style={{
          fontSize: 10,
          padding: "2px 8px",
          borderRadius: 4,
          background: (BADGE_STYLES[mode.resultTone] || BADGE_STYLES.neutral).bg,
          color: (BADGE_STYLES[mode.resultTone] || BADGE_STYLES.neutral).color,
          fontWeight: 600,
          letterSpacing: "0.05em",
          flexShrink: 0,
        }}>
          {mode.resultBadge}
        </span>
      </div>

      <div style={{
        flex: 1,
        minHeight: 140,
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        background: "#EEF1F6",
      }}>
        {[untrained, trained].map((side) => {
          const active = side === mode;
          return (
            <div
              key={side.buttonLabel}
              style={{
                position: "relative",
                minHeight: 140,
                borderRight: side === untrained ? "1px solid #DDE4EE" : undefined,
                opacity: active ? 1 : 0.55,
                outline: active ? "2px solid #168F66" : "none",
                outlineOffset: -2,
                overflow: "hidden",
              }}
            >
              <div style={{
                position: "absolute", top: 6, left: 6, right: 6, zIndex: 2,
                fontSize: 9, fontWeight: 700, letterSpacing: "0.04em",
                padding: "2px 6px", borderRadius: 3, textAlign: "center",
                background: active ? "#168F66" : "rgba(255,255,255,0.92)",
                color: active ? "#fff" : "#5C6778",
              }}>
                {side === untrained ? "Before · untrained" : "After · DreamLoop"}
              </div>
              {side.resultSrc && (
                <video
                  src={side.resultSrc}
                  autoPlay={playing && active}
                  loop
                  muted
                  playsInline
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                />
              )}
            </div>
          );
        })}
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
  const [scenario, setScenario] = useState("baseline");
  const [running, setRunning] = useState(false);
  const { current, history, frame, total } = useMetrics(scenario, running);
  const mode = SCENARIO_MODES[scenario];

  const handleScenario = (s) => {
    setRunning(false);
    setScenario(s);
  };

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
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase" }}>I2V Safe Driving · Flood demo</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["baseline"].map((s) => (
              <button
                key={s}
                onClick={() => handleScenario(s)}
                title={SCENARIO_MODES[s].description}
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: scenario === s ? "1px solid #168F66" : "1px solid #DDE4EE",
                  background: scenario === s ? "#E6F5EE" : "#FFFFFF",
                  color: scenario === s ? "#168F66" : "#7A8496",
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: "0.04em",
                  transition: "all 0.2s",
                }}
              >
                {SCENARIO_MODES[s].buttonLabel}
              </button>
            ))}
            {/* I2V intervention — re-enable when ready
            <button
              key="i2v"
              onClick={() => handleScenario("i2v")}
              title={SCENARIO_MODES.i2v.description}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: scenario === "i2v" ? "1px solid #168F66" : "1px solid #DDE4EE",
                background: scenario === "i2v" ? "#E6F5EE" : "#FFFFFF",
                color: scenario === "i2v" ? "#168F66" : "#7A8496",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: "0.04em",
                transition: "all 0.2s",
              }}
            >
              {SCENARIO_MODES.i2v.buttonLabel}
            </button>
            */}
          </div>
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
              Driving simulation (panels 1–3 stay the same clip)
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#1E2638" }}>{mode.headline}</div>
                <div style={{ fontSize: 11, color: "#6B7689", marginTop: 2 }}>{mode.description}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 11, color: "#8B95A8" }}>Frame {frame + 1}/{total}</span>
                <InfraStatus status={current.infra} />
              </div>
            </div>
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

          {/* Pipeline explainer
          <div style={{
            padding: "8px 12px",
            borderRadius: 6,
            background: "#EEF1F6",
            border: "1px dashed #C5D0E0",
            fontSize: 10,
            color: "#6B7689",
            lineHeight: 1.45,
          }}>
            <strong style={{ color: "#4A5568" }}>Pipeline (same for both buttons):</strong>{" "}
            Waymo raw → Cosmos bboxes → Helios flood weather → Panel 4 compares perception with vs without DreamLoop training.
            Optional later: <code style={{ fontSize: 9 }}>public/videos/pedestrian_example.avi</code>
          </div>
          */}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, flex: 1, alignItems: "stretch" }}>
            <VideoPanel
              title="01 — Waymo input"
              badge="RAW CLIP"
              badgeTone="neutral"
              src={VIDEO_ASSETS.waymo}
              caption="Clean baseline Waymo footage — same clip every time"
              footnote="public/videos/waymo_input.avi"
              playing={running}
            />
            <VideoPanel
              title="02 — Cosmos geometry"
              badge="BBOX OVERLAY"
              badgeTone="pipeline"
              src={VIDEO_ASSETS.cosmos}
              caption="Same clip with bounding boxes burned in (Person 2)"
              footnote="public/videos/cosmos_geometry.avi"
              playing={running}
            />
            <VideoPanel
              title="03 — Helios flood render"
              badge="FLOOD SCENE"
              badgeTone="flood"
              src={VIDEO_ASSETS.helios}
              caption="Rain, standing water, spray on top of Cosmos geometry"
              footnote="public/videos/dreamloop_blizzard.mp4 (or .avi)"
              playing={running}
            />
            <ResultComparePanel scenario={scenario} playing={running} />
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
                      opacity: 0.35 + (i / history.length) * 0.65,
                      transition: "height 0.4s ease",
                    }}
                  />
                );
              })}
              {history.length === 0 && (
                <span style={{ fontSize: 11, color: "#9AA5B8" }}>Hit RUN to animate metrics for the selected button</span>
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
            <div style={{ fontSize: 10, color: "#8B95A8", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>Pipeline</div>
            {[
              { name: "Cosmos-Drive", status: "ready" },
              { name: "Helios V2V", status: "ready" },
              { name: "NemoClaw", status: running ? "active" : "idle" },
              { name: "Result Feed", status: running ? "active" : "idle" },
            ].map((p) => (
              <div key={p.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: "#6B7689" }}>{p.name}</span>
                <span style={{
                  fontSize: 10,
                  padding: "2px 7px",
                  borderRadius: 4,
                  background: p.status === "active" ? "#E6F5EE" : p.status === "ready" ? "#E8F0FA" : "#EEF1F6",
                  color: p.status === "active" ? "#168F66" : p.status === "ready" ? "#2E6BA8" : "#8B95A8",
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
