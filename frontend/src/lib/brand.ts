/**
 * Product branding. Change SUPPORT_EMAIL via NEXT_PUBLIC_SUPPORT_EMAIL at build time.
 */
export const BRAND_NAME = 'VisuLit';

export const SUPPORT_EMAIL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_SUPPORT_EMAIL) ||
  'hello@visulit.com';
