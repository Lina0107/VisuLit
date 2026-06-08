import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(145deg, #831843 0%, #4a0030 100%)",
          borderRadius: 7,
        }}
      >
        <div
          style={{
            color: "#fce7f3",
            fontSize: 20,
            fontWeight: 700,
            fontFamily: "Georgia, serif",
            letterSpacing: "-0.02em",
          }}
        >
          V
        </div>
      </div>
    ),
    { ...size },
  );
}
