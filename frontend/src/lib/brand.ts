/**
 * Product branding. Change SUPPORT_EMAIL via NEXT_PUBLIC_SUPPORT_EMAIL at build time.
 */
export const BRAND_NAME = 'VisuLit';

export const SITE_URL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_SITE_URL) ||
  'https://visulit.com';

export const SUPPORT_EMAIL =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_SUPPORT_EMAIL) ||
  'visulitapp@gmail.com';
