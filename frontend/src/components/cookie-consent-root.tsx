'use client';

import React from 'react';
import Link from 'next/link';
import Script from 'next/script';
import {
  COOKIE_CONSENT_KEY,
  type CookieConsentValue,
  setStoredConsent,
} from '@/lib/cookie-consent';

function readConsent(): CookieConsentValue | null | 'unset' {
  if (typeof window === 'undefined') return 'unset';
  const v = localStorage.getItem(COOKIE_CONSENT_KEY);
  if (v === 'essential' || v === 'analytics') return v;
  return 'unset';
}

export function CookieConsentRoot({ gaMeasurementId }: { gaMeasurementId: string }) {
  /** null = not yet read from localStorage (avoid banner flash on load) */
  const [consent, setConsent] = React.useState<CookieConsentValue | 'unset' | null>(null);

  React.useEffect(() => {
    setConsent(readConsent());
    const onChange = () => setConsent(readConsent());
    window.addEventListener('visulit-cookie-consent', onChange);
    window.addEventListener('storage', onChange);
    return () => {
      window.removeEventListener('visulit-cookie-consent', onChange);
      window.removeEventListener('storage', onChange);
    };
  }, []);

  const choose = (v: CookieConsentValue) => {
    setStoredConsent(v);
    setConsent(v);
  };

  const showBanner = consent === 'unset';
  const allowAnalytics = consent === 'analytics';

  return (
    <>
      {allowAnalytics && gaMeasurementId ? (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`}
            strategy="afterInteractive"
          />
          <Script id="ga-gtag-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${gaMeasurementId}');
            `}
          </Script>
        </>
      ) : null}

      {showBanner ? (
        <div
          className="fixed inset-x-0 bottom-0 z-[100] border-t border-pink-200 bg-white/95 px-4 py-4 shadow-[0_-8px_30px_rgba(120,60,90,0.12)] backdrop-blur-sm md:px-6"
          role="dialog"
          aria-label="Cookie preferences"
        >
          <div className="mx-auto flex max-w-4xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-pink-950/90 md:max-w-xl">
              We use essential cookies so the app works (including a technical ID for daily free
              limits). With your permission we also load{' '}
              <span className="font-medium text-pink-950">Google Analytics</span> to understand
              usage. See our{' '}
              <Link
                href="/cookies"
                className="font-medium text-pink-900 underline underline-offset-2 hover:text-pink-700"
              >
                Cookie policy
              </Link>
              .
            </p>
            <div className="flex flex-shrink-0 flex-wrap gap-2 md:justify-end">
              <button
                type="button"
                onClick={() => choose('essential')}
                className="rounded-full bg-white px-4 py-2.5 text-sm font-medium text-pink-950 ring-1 ring-pink-200 transition hover:bg-pink-50"
              >
                Essential only
              </button>
              <button
                type="button"
                onClick={() => choose('analytics')}
                className="rounded-full bg-pink-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-pink-900"
              >
                Accept analytics
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
