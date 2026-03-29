export const COOKIE_CONSENT_KEY = 'visulit_cookie_consent';

/** essential = no Google Analytics; analytics = GA4 allowed */
export type CookieConsentValue = 'essential' | 'analytics';

export function getStoredConsent(): CookieConsentValue | null {
  if (typeof window === 'undefined') return null;
  const v = localStorage.getItem(COOKIE_CONSENT_KEY);
  if (v === 'essential' || v === 'analytics') return v;
  return null;
}

export function setStoredConsent(v: CookieConsentValue) {
  localStorage.setItem(COOKIE_CONSENT_KEY, v);
  window.dispatchEvent(new CustomEvent('visulit-cookie-consent'));
}
