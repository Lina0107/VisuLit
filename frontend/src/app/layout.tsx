import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { CookieConsentRoot } from "@/components/cookie-consent-root";
import { BRAND_NAME, SITE_URL } from "@/lib/brand";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: BRAND_NAME,
  description:
    "VisuLit — literary character portraits from real book quotes. Public-domain books, tasteful prompts.",
  icons: {
    icon: [{ url: "/visulit-logo.svg", type: "image/svg+xml" }],
    apple: [{ url: "/visulit-logo.svg", type: "image/svg+xml" }],
  },
  openGraph: {
    title: BRAND_NAME,
    description:
      "AI portraits of literary characters grounded in real book quotes.",
    type: "website",
    siteName: BRAND_NAME,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: `${BRAND_NAME} preview` }],
  },
  twitter: {
    card: "summary_large_image",
    title: BRAND_NAME,
    description:
      "AI portraits of literary characters grounded in real book quotes.",
    images: ["/twitter-image"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-2TBVVWWD2S";

  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased overflow-x-hidden`}
      >
        <CookieConsentRoot gaMeasurementId={gaId} />
        {children}
      </body>
    </html>
  );
}
