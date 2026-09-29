import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

// Favicon: the two offset bars (amber + bright) on obsidian.
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          gap: 3,
          background: "#08080a",
          paddingBottom: 7,
        }}
      >
        <div style={{ width: 6, height: 15, background: "#eab308", borderRadius: 2 }} />
        <div style={{ width: 6, height: 20, background: "#facc15", borderRadius: 2 }} />
      </div>
    ),
    { ...size },
  );
}
