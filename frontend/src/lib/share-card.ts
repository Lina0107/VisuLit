import { BRAND_NAME, SITE_URL } from '@/lib/brand';

export type ShareCardText = {
  name: string;
  /** Book title; empty for a custom character. */
  book?: string;
  /** Line from the book the portrait is based on; empty for a custom character. */
  quote?: string;
};

const W = 1080;
const H = 1350;
const PHOTO_H = 930;
const PAD = 72;

/** Shorten a long book passage to one readable line for the card. */
export function quoteForCard(raw: string | undefined, max = 150): string {
  const text = (raw || '').replace(/[_*]/g, '').replace(/\s+/g, ' ').replace(/^["“”'‘’\s]+|["“”'‘’\s]+$/g, '').trim();
  if (!text) return '';
  if (text.length <= max) return text;
  // First full sentence, if it fits. A period after a title (Mr., Mrs., Dr.) is not an end.
  const end = /[.!?](?=\s|$)/g;
  for (let m = end.exec(text); m; m = end.exec(text)) {
    const sentence = text.slice(0, m.index + 1);
    if (sentence.length > max) break;
    if (sentence.length >= 40 && !/\b(Mr|Mrs|Ms|Dr|St|Mme|Mlle)\.$/.test(sentence)) return sentence;
  }
  const cut = text.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), 60)).replace(/[,;:\-–—]+$/, '')}…`;
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = [];
  let line = '';
  for (const word of text.split(' ')) {
    const next = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(next).width > maxWidth) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Image load failed'));
    img.src = src;
  });
}

/**
 * Draws a 4:5 card for social feeds: the portrait on top, then the quote,
 * the character and book, and the site address. Returns a JPEG blob.
 */
export async function renderShareCard(imgSrc: string, text: ShareCardText): Promise<Blob> {
  const img = await loadImage(imgSrc);
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas unsupported');

  ctx.fillStyle = '#fff7fb';
  ctx.fillRect(0, 0, W, H);

  // Portrait: cover the top area, biased upward so the face stays in frame.
  const scale = Math.max(W / img.naturalWidth, PHOTO_H / img.naturalHeight);
  const dw = img.naturalWidth * scale;
  const dh = img.naturalHeight * scale;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, W, PHOTO_H);
  ctx.clip();
  ctx.drawImage(img, (W - dw) / 2, (PHOTO_H - dh) * 0.2, dw, dh);
  ctx.restore();

  const quote = quoteForCard(text.quote);
  const maxWidth = W - PAD * 2;
  ctx.textBaseline = 'alphabetic';
  let y = PHOTO_H + 78;

  if (quote) {
    let size = 44;
    let lines: string[] = [];
    for (; size >= 30; size -= 2) {
      ctx.font = `italic ${size}px Georgia, 'Times New Roman', serif`;
      lines = wrap(ctx, `“${quote}”`, maxWidth);
      if (lines.length <= 4) break;
    }
    ctx.fillStyle = '#3b0a24';
    for (const line of lines.slice(0, 4)) {
      ctx.fillText(line, PAD, y);
      y += Math.round(size * 1.28);
    }
    y += 14;
  } else {
    y += 20;
  }

  ctx.fillStyle = '#3b0a24';
  ctx.font = `600 ${quote ? 30 : 52}px Georgia, 'Times New Roman', serif`;
  const nameLine = wrap(ctx, text.name, maxWidth)[0] || text.name;
  ctx.fillText(nameLine, PAD, y + (quote ? 14 : 40));
  if (text.book) {
    ctx.fillStyle = 'rgba(59,10,36,0.6)';
    ctx.font = `400 26px Georgia, 'Times New Roman', serif`;
    ctx.fillText(wrap(ctx, text.book, maxWidth)[0] || text.book, PAD, y + (quote ? 52 : 86));
  }

  // Site address, bottom right.
  const site = SITE_URL.replace(/^https?:\/\//, '').replace(/\/$/, '');
  ctx.font = '600 26px Arial, Helvetica, sans-serif';
  ctx.fillStyle = '#9d174d';
  const label = `${BRAND_NAME} · ${site}`;
  ctx.fillText(label, W - PAD - ctx.measureText(label).width, H - 44);

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('blob error'))), 'image/jpeg', 0.92);
  });
}

export async function downloadShareCard(imgSrc: string, text: ShareCardText, filename: string) {
  const blob = await renderShareCard(imgSrc, text);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
