import { useState, useEffect, useRef } from "react";

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
    value > 70 ? "#E24B4A" : value > 40 ? "#EF9F27" : "#1D9E75";
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: "#888", letterSpacing: "0.08em", textTransform: "uppercase" }}>Collision Risk</span>
        <span style={{ fontSize: 13, fontWeight: 600, color }}>{value}%</span>
      </div>
      <div style={{ height: 6, background: "#1a1f2e", borderRadius: 3, overflow: "hidden" }}>
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
      background: "#0d1117",
      border: "1px solid #1e2535",
      borderRadius: 8,
      padding: "12px 14px",
      borderTop: accent ? `2px solid ${accent}` : "1px solid #1e2535",
    }}>
      <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent || "#e8eaf0", fontFamily: "'JetBrains Mono', monospace" }}>
        {value}<span style={{ fontSize: 12, fontWeight: 400, marginLeft: 3, color: "#555" }}>{unit}</span>
      </div>
    </div>
  );
}

function VideoPanel({ title, label, trained }) {
  return (
    <div style={{
      background: "#080b10",
      border: "1px solid #1e2535",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
    }}>
      <div style={{
        padding: "8px 14px",
        borderBottom: "1px solid #1e2535",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "#8892a4", letterSpacing: "0.06em", textTransform: "uppercase" }}>{title}</span>
        {label && (
          <span style={{
            fontSize: 10,
            padding: "2px 8px",
            borderRadius: 4,
            background: trained ? "#0f3d2a" : "#2a0f0f",
            color: trained ? "#1D9E75" : "#E24B4A",
            fontWeight: 600,
            letterSpacing: "0.05em",
          }}>{label}</span>
        )}
      </div>
      <div style={{
        flex: 1,
        minHeight: 140,
        background: trained
          ? "linear-gradient(135deg, #061a10 0%, #0a2818 100%)"
          : "linear-gradient(135deg, #15060a 0%, #200a10 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", inset: 0,
          backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 29px, #ffffff08 30px), repeating-linear-gradient(90deg, transparent, transparent 29px, #ffffff05 30px)",
        }} />
        <div style={{ textAlign: "center", position: "relative" }}>
          <div style={{ fontSize: 11, color: "#444", marginBottom: 6 }}>
            {trained ? "📹 Trained model tracking" : "📹 Baseline model"}
          </div>
          <div style={{ fontSize: 10, color: "#333", fontFamily: "monospace" }}>
            Drop video file here or connect Helios feed
          </div>
        </div>
        {!trained && (
          <div style={{
            position: "absolute", top: 8, right: 8,
            width: 8, height: 8, borderRadius: "50%",
            background: "#E24B4A",
            boxShadow: "0 0 6px #E24B4A",
            animation: "blink 1.2s infinite",
          }} />
        )}
      </div>
    </div>
  );
}

function InfraStatus({ status }) {
  const colors = {
    NOMINAL: { bg: "#0d1f0d", text: "#1D9E75", dot: "#1D9E75" },
    "BEACON ACTIVE": { bg: "#1a1a0a", text: "#EF9F27", dot: "#EF9F27" },
    DECELERATING: { bg: "#1a1400", text: "#EF9F27", dot: "#EF9F27" },
    "SAFE SPEED": { bg: "#0d1f0d", text: "#1D9E75", dot: "#1D9E75" },
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

  const handleScenario = (s) => {
    setRunning(false);
    setScenario(s);
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060911",
      color: "#c8cdd8",
      fontFamily: "'Inter', system-ui, sans-serif",
      padding: "0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        button { cursor: pointer; font-family: inherit; }
      `}</style>

      {/* Header */}
      <div style={{
        borderBottom: "1px solid #1e2535",
        padding: "14px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "#080c14",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #1D9E75, #185FA5)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
          }}>⟳</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#e8eaf0", letterSpacing: "-0.01em" }}>DreamLoop</div>
            <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.1em", textTransform: "uppercase" }}>I2V Safe Driving Edition</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["baseline", "i2v"].map((s) => (
              <button
                key={s}
                onClick={() => handleScenario(s)}
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: scenario === s ? "1px solid #1D9E75" : "1px solid #1e2535",
                  background: scenario === s ? "#0a2418" : "transparent",
                  color: scenario === s ? "#1D9E75" : "#555",
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  transition: "all 0.2s",
                }}
              >
                {s === "baseline" ? "Baseline" : "I2V Intervention"}
              </button>
            ))}
          </div>
          <button
            onClick={() => setRunning((r) => !r)}
            style={{
              padding: "6px 18px",
              borderRadius: 6,
              border: "none",
              background: running ? "#3d1010" : "#1D9E75",
              color: running ? "#E24B4A" : "#fff",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.04em",
              transition: "all 0.2s",
            }}
          >
            {running ? "■ STOP" : "▶ RUN"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", minHeight: "calc(100vh - 61px)" }}>

        {/* Main panels */}
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>

          {/* Status bar */}
          <div style={{
            background: "#0d1117",
            border: "1px solid #1e2535",
            borderRadius: 8,
            padding: "10px 16px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 11, color: "#444", letterSpacing: "0.08em", textTransform: "uppercase" }}>Scenario</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#8892a4" }}>
                {scenario === "baseline" ? "Unprotected — No I2V Infrastructure" : "Protected — V2X Smart Beacon Active"}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ fontSize: 11, color: "#444" }}>Frame {frame + 1}/{total}</span>
              <InfraStatus status={current.infra} />
            </div>
          </div>

          {/* Event label */}
          <div style={{
            padding: "8px 16px",
            borderRadius: 6,
            background: current.risk > 70 ? "#1a0808" : current.risk > 40 ? "#141000" : "#081410",
            border: `1px solid ${current.risk > 70 ? "#E24B4A44" : current.risk > 40 ? "#EF9F2744" : "#1D9E7544"}`,
            fontSize: 12,
            color: current.risk > 70 ? "#E24B4A" : current.risk > 40 ? "#EF9F27" : "#1D9E75",
            fontWeight: 600,
            letterSpacing: "0.04em",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            ▸ {current.label}
          </div>

          {/* 4-panel video grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, flex: 1 }}>
            <VideoPanel title="01 — Waymo Input" label="RAW CLIP" />
            <VideoPanel title="02 — Cosmos Geometry" label="PHYSICS LOCK" />
            <VideoPanel title="03 — Helios Flood Render" label="UNTRAINED" trained={false} />
            <VideoPanel title="04 — DreamLoop Result" label="TRAINED" trained={true} />
          </div>

          {/* Risk history spark */}
          <div style={{
            background: "#0d1117",
            border: "1px solid #1e2535",
            borderRadius: 8,
            padding: "10px 16px",
          }}>
            <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>Risk timeline</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 40 }}>
              {history.map((h, i) => {
                const color = h.risk > 70 ? "#E24B4A" : h.risk > 40 ? "#EF9F27" : "#1D9E75";
                return (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: `${(h.risk / 100) * 40}px`,
                      background: color,
                      borderRadius: 2,
                      opacity: 0.4 + (i / history.length) * 0.6,
                      transition: "height 0.4s ease",
                    }}
                  />
                );
              })}
              {history.length === 0 && (
                <span style={{ fontSize: 11, color: "#333" }}>Run a scenario to see timeline</span>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar metrics */}
        <div style={{
          borderLeft: "1px solid #1e2535",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          background: "#080c14",
        }}>
          <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.1em", textTransform: "uppercase" }}>Live Metrics</div>

          <MetricCard
            label="Vehicle Speed"
            value={current.speed}
            unit="MPH"
            accent={current.speed > 55 ? "#E24B4A" : current.speed > 40 ? "#EF9F27" : "#1D9E75"}
          />
          <MetricCard
            label="Road Friction"
            value={current.friction.toFixed(2)}
            unit="μ"
            accent={current.friction < 0.2 ? "#E24B4A" : current.friction < 0.5 ? "#EF9F27" : "#1D9E75"}
          />

          <div style={{
            background: "#0d1117",
            border: "1px solid #1e2535",
            borderRadius: 8,
            padding: "12px 14px",
          }}>
            <RiskBar value={current.risk} />
          </div>

          <div style={{
            background: "#0d1117",
            border: "1px solid #1e2535",
            borderRadius: 8,
            padding: "12px 14px",
          }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>Infrastructure</div>
            <InfraStatus status={current.infra} />
          </div>

          {/* Pipeline status */}
          <div style={{
            marginTop: "auto",
            background: "#0d1117",
            border: "1px solid #1e2535",
            borderRadius: 8,
            padding: "12px 14px",
          }}>
            <div style={{ fontSize: 10, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>Pipeline</div>
            {[
              { name: "Cosmos-Drive", status: "ready" },
              { name: "Helios V2V", status: "ready" },
              { name: "NemoClaw", status: running ? "active" : "idle" },
              { name: "Result Feed", status: running ? "active" : "idle" },
            ].map((p) => (
              <div key={p.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: "#666" }}>{p.name}</span>
                <span style={{
                  fontSize: 10,
                  padding: "2px 7px",
                  borderRadius: 4,
                  background: p.status === "active" ? "#0a2418" : p.status === "ready" ? "#0d1a2a" : "#111",
                  color: p.status === "active" ? "#1D9E75" : p.status === "ready" ? "#185FA5" : "#444",
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
