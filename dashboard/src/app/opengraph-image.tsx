import { ImageResponse } from "next/og";

export const alt = "Parallax — low-latency prediction-market intelligence";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Social preview: obsidian canvas, amber accent, on-brand.
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "radial-gradient(1000px 500px at 78% -10%, rgba(234,179,8,0.18), transparent), #08080a",
          padding: "72px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 6 }}>
            <div style={{ width: 10, height: 30, background: "#eab308", borderRadius: 4 }} />
            <div style={{ width: 10, height: 40, background: "#facc15", borderRadius: 4 }} />
          </div>
          <div style={{ fontSize: 30, color: "#f4f5f3", fontWeight: 600 }}>Parallax</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 76,
              color: "#f4f5f3",
              fontWeight: 700,
              lineHeight: 1.06,
              letterSpacing: "-0.03em",
            }}
          >
            <div style={{ display: "flex" }}>Markets move fast.</div>
            <div style={{ display: "flex", gap: 20 }}>
              <span style={{ color: "#facc15" }}>Parallax</span>
              <span>moves faster.</span>
            </div>
          </div>
          <div style={{ display: "flex", fontSize: 28, color: "#9a9aa2", maxWidth: 900 }}>
            A low-latency pipeline that models calibrated probabilities and flags logical and
            cross-source mispricings. Read-only.
          </div>
        </div>

        <div style={{ display: "flex", gap: 40, fontSize: 22, color: "#9a9aa2", fontFamily: "monospace" }}>
          <span>194k events / s</span>
          <span>&lt;40µs p50</span>
          <span>2 detectors</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
