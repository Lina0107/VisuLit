import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { CookieConsentRoot } from "@/components/cookie-consent-root";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VisuLit",
  description:
    "VisuLit — literary character portraits from real book quotes. Public-domain books, tasteful prompts.",
  openGraph: {
    title: "VisuLit",
    description:
      "AI portraits of literary characters grounded in real book quotes.",
    type: "website",
    siteName: "VisuLit",
  },
  twitter: {
    card: "summary_large_image",
    title: "VisuLit",
    description:
      "AI portraits of literary characters grounded in real book quotes.",
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
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <CookieConsentRoot gaMeasurementId={gaId} />
        {children}
      </body>
    </html>
  );
}
