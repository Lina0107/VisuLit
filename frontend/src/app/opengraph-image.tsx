import { ImageResponse } from 'next/og';
import { BRAND_NAME } from '@/lib/brand';

export const runtime = 'edge';
export const alt = `${BRAND_NAME} — literary portraits from real book quotes`;
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(145deg, #fff0f6 0%, #fce7f3 45%, #fdf2f8 100%)',
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 120,
            height: 120,
            borderRadius: 32,
            background: '#fbcfe8',
            border: '3px solid #f9a8d4',
            marginBottom: 28,
            fontSize: 64,
            fontWeight: 700,
            color: '#4a0030',
          }}
        >
          V
        </div>
        <div style={{ fontSize: 72, fontWeight: 700, color: '#4a0030', letterSpacing: -2 }}>
          {BRAND_NAME}
        </div>
        <div
          style={{
            marginTop: 20,
            fontSize: 32,
            color: '#831843',
            opacity: 0.85,
            maxWidth: 900,
            textAlign: 'center',
            lineHeight: 1.35,
          }}
        >
          Literary character portraits grounded in real book quotes
        </div>
      </div>
    ),
    { ...size },
  );
}
