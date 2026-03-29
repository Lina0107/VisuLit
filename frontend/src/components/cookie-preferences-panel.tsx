'use client';

import React from 'react';
import { getStoredConsent, setStoredConsent, type CookieConsentValue } from '@/lib/cookie-consent';

export function CookiePreferencesPanel() {
  const [current, setCurrent] = React.useState<CookieConsentValue | null>(null);

  React.useEffect(() => {
    setCurrent(getStoredConsent());
  }, []);

  const apply = (v: CookieConsentValue) => {
    const prev = getStoredConsent();
    setStoredConsent(v);
    setCurrent(v);
    if (prev === 'analytics' && v === 'essential') {
      window.location.reload();
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-pink-200 bg-white/80 p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-pink-900/60">Current setting</p>
      <p className="mt-1 text-sm font-medium text-pink-950">
        {current === null
          ? 'Not set yet (open the main page to see the banner)'
          : current === 'analytics'
            ? 'Analytics allowed'
            : 'Essential only (no Google Analytics)'}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => apply('essential')}
          className="rounded-full bg-white px-4 py-2 text-sm font-medium text-pink-950 ring-1 ring-pink-200 transition hover:bg-pink-50"
        >
          Use essential only
        </button>
        <button
          type="button"
          onClick={() => apply('analytics')}
          className="rounded-full bg-pink-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-pink-900"
        >
          Allow analytics
        </button>
      </div>
    </div>
  );
}
