import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(145deg, #fce7f3 0%, #fbcfe8 40%, #831843 100%)",
          borderRadius: 36,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 120,
            height: 120,
            borderRadius: 28,
            background: "#4a0030",
            color: "#fce7f3",
            fontSize: 68,
            fontWeight: 700,
            fontFamily: "Georgia, serif",
          }}
        >
          V
        </div>
      </div>
    ),
    { ...size },
  );
}
