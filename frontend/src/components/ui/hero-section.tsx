'use client';

import React from 'react';
import {
  BookOpenText,
  ChevronRight,
  Download,
  PenLine,
  Search,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { BRAND_NAME, SUPPORT_EMAIL } from '@/lib/brand';
import { ExamplesGallery } from '@/components/examples-gallery';

function ErrorWithSupport({ message }: { message: string }) {
  return (
    <div>
      <div className="whitespace-pre-wrap">{message}</div>
      <p className="mt-2 text-xs text-pink-950/65">
        Something wrong? Email{' '}
        <a
          href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`${BRAND_NAME} — help`)}`}
          className="font-medium text-pink-900 underline underline-offset-2 hover:text-pink-700"
        >
          {SUPPORT_EMAIL}
        </a>
        {' '}and describe what you tried (book, character, or “Generate”).
      </p>
    </div>
  );
}

// Draw image on canvas, stamp brand watermark, return blob URL for download.
async function downloadWithWatermark(imgSrc: string, filename: string) {
  return new Promise<void>((resolve, reject) => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) { reject(new Error('canvas unsupported')); return; }

      ctx.drawImage(img, 0, 0);

      // Watermark settings
      const fontSize = Math.max(18, Math.round(canvas.width * 0.022));
      ctx.font = `600 ${fontSize}px sans-serif`;
      const text = `✦ ${BRAND_NAME}`;
      const padding = Math.round(fontSize * 0.7);
      const textW = ctx.measureText(text).width;
      const boxW = textW + padding * 2;
      const boxH = fontSize + padding * 1.4;
      const x = canvas.width - boxW - Math.round(canvas.width * 0.015);
      const y = canvas.height - boxH - Math.round(canvas.height * 0.015);

      // soft semi-transparent pill background
      ctx.save();
      ctx.globalAlpha = 0.60;
      ctx.fillStyle = '#fff0f6';
      ctx.beginPath();
      const r = boxH / 2;
      const anyCtx = ctx as any;
      if (typeof anyCtx.roundRect === 'function') {
        anyCtx.roundRect(x, y, boxW, boxH, r);
        ctx.fill();
      } else {
        // Fallback: no rounded rectangle support
        ctx.rect(x, y, boxW, boxH);
        ctx.fill();
      }
      ctx.restore();

      // text
      ctx.save();
      ctx.globalAlpha = 0.92;
      ctx.fillStyle = '#4a0030';
      ctx.font = `600 ${fontSize}px sans-serif`;
      ctx.textBaseline = 'middle';
      ctx.fillText(text, x + padding, y + boxH / 2);
      ctx.restore();

      canvas.toBlob((blob) => {
        if (!blob) { reject(new Error('blob error')); return; }
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        resolve();
      }, 'image/jpeg', 0.93);
    };
    img.onerror = () => reject(new Error('Image load failed'));
    img.src = imgSrc;
  });
}

type SceneVariantPayload = { emotion: string; pose: string; setting: string; notes: string };

// Small reusable component: image card with watermark download/regenerate button
function PortraitCard({
  imageUrl,
  altText,
  filename,
  onRegenerate,
  regenerating = false,
  onSceneVariant,
  sceneVariantBusy = false,
}: {
  imageUrl: string;
  altText: string;
  filename: string;
  onRegenerate?: () => Promise<void> | void;
  regenerating?: boolean;
  onSceneVariant?: (payload: SceneVariantPayload) => Promise<void>;
  sceneVariantBusy?: boolean;
}) {
  const [downloading, setDownloading] = React.useState(false);
  const [emotion, setEmotion] = React.useState('');
  const [pose, setPose] = React.useState('');
  const [setting, setSetting] = React.useState('');
  const [notes, setNotes] = React.useState('');

  const busy = regenerating || downloading || sceneVariantBusy;
  const canScene = Boolean(
    onSceneVariant &&
      (emotion.trim() || pose.trim() || setting.trim() || notes.trim()),
  );

  return (
    <div className="mt-3 rounded-2xl border border-pink-200 bg-white/60 p-3">
      <div className="mb-2 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Generated portrait</div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {onRegenerate && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onRegenerate()}
              className="inline-flex items-center gap-1.5 bg-white hover:bg-pink-50 disabled:opacity-50 text-pink-950 text-xs px-4 py-2 rounded-full font-medium transition ring-1 ring-pink-200"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {regenerating ? 'Regenerating…' : 'Regenerate'}
            </button>
          )}
          <button
            type="button"
            disabled={downloading || regenerating}
            onClick={async () => {
              setDownloading(true);
              try {
                await downloadWithWatermark(imageUrl, filename);
              } catch (e) {
                console.error('Download failed', e);
              } finally {
                setDownloading(false);
              }
            }}
            className="inline-flex items-center gap-1.5 bg-pink-950 hover:bg-pink-900 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-full font-medium transition"
          >
            <Download className="h-3.5 w-3.5" />
            {downloading ? 'Saving…' : 'Download'}
          </button>
        </div>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageUrl} alt={altText} className="w-full rounded-xl object-cover" />

      {onSceneVariant && (
        <details className="mt-3 rounded-xl border border-pink-100 bg-white/50 px-3 py-2 text-pink-950">
          <summary className="cursor-pointer text-xs font-semibold text-pink-900/80 outline-none marker:text-pink-600">
            New scene (same character)
          </summary>
          <p className="mt-2 text-[11px] leading-snug text-pink-950/65">
            Change emotion, pose, or place. We send your current portrait as a reference so the model keeps the same face
            as closely as the API allows — not a perfect guarantee, but much better than text-only.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <label className="block text-[11px] font-medium text-pink-900/70">
              Emotion / expression
              <input
                value={emotion}
                onChange={(e) => setEmotion(e.target.value)}
                placeholder="e.g. calm half-smile, thoughtful"
                className="mt-1 w-full rounded-lg border border-pink-200 bg-white/80 px-2 py-1.5 text-xs text-pink-950 outline-none placeholder:text-pink-950/35"
              />
            </label>
            <label className="block text-[11px] font-medium text-pink-900/70">
              Pose
              <input
                value={pose}
                onChange={(e) => setPose(e.target.value)}
                placeholder="e.g. three-quarter view, shoulders relaxed"
                className="mt-1 w-full rounded-lg border border-pink-200 bg-white/80 px-2 py-1.5 text-xs text-pink-950 outline-none placeholder:text-pink-950/35"
              />
            </label>
            <label className="block text-[11px] font-medium text-pink-900/70 sm:col-span-2">
              Place / setting
              <input
                value={setting}
                onChange={(e) => setSetting(e.target.value)}
                placeholder="e.g. sunlit library, rainy window behind"
                className="mt-1 w-full rounded-lg border border-pink-200 bg-white/80 px-2 py-1.5 text-xs text-pink-950 outline-none placeholder:text-pink-950/35"
              />
            </label>
            <label className="block text-[11px] font-medium text-pink-900/70 sm:col-span-2">
              Extra notes (optional)
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Lighting, wardrobe tweak, camera distance…"
                className="mt-1 w-full rounded-lg border border-pink-200 bg-white/80 px-2 py-1.5 text-xs text-pink-950 outline-none placeholder:text-pink-950/35"
              />
            </label>
          </div>
          <button
            type="button"
            disabled={!canScene || busy}
            onClick={async () => {
              if (!onSceneVariant || !canScene) return;
              await onSceneVariant({
                emotion: emotion.trim(),
                pose: pose.trim(),
                setting: setting.trim(),
                notes: notes.trim(),
              });
            }}
            className="mt-3 w-full rounded-full bg-pink-100 py-2 text-xs font-semibold text-pink-950 transition hover:bg-pink-200 disabled:opacity-45 sm:w-auto sm:px-6"
          >
            {sceneVariantBusy ? 'Generating new scene…' : 'Generate new scene'}
          </button>
        </details>
      )}
    </div>
  );
}

const MIN_GENERATE_SPINNER_MS = 1800;

async function readApiJson(res: Response): Promise<any> {
  const raw = await res.text();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    // Backend can occasionally return plain-text 500s (e.g., "Internal Server Error").
    // Normalize to a JSON-like object so UI errors stay user-friendly.
    return { success: false, error: raw.slice(0, 400) };
  }
}

/** Raw base64 without data: prefix, for /api/generate scene_variant.reference_image_base64 */
async function imageUrlToRawBase64(src: string): Promise<string | undefined> {
  if (!src) return undefined;
  if (src.startsWith('data:')) {
    const idx = src.indexOf(';base64,');
    if (idx !== -1) return src.slice(idx + 8);
    return undefined;
  }
  try {
    const res = await fetch(src);
    if (!res.ok) return undefined;
    const blob = await res.blob();
    const buf = await blob.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + chunk)));
    }
    return btoa(binary);
  } catch {
    return undefined;
  }
}

function trackEvent(name: string, params?: Record<string, unknown>) {
  if (typeof window === 'undefined') return;
  const gtag = (window as any).gtag;
  if (typeof gtag !== 'function') return;
  gtag('event', name, params || {});
}

function mapApiCharactersToCast(characters: unknown[]): { character_id: string; character_name: string }[] {
  return characters
    .map((c: any) => ({
      character_id: String(c?.character_id || ''),
      character_name: String(c?.character_name || ''),
    }))
    .filter((c) => c.character_id && c.character_name);
}

export default function HeroSection() {
  const [bookQuery, setBookQuery] = React.useState('');
  const [selectedBookId, setSelectedBookId] = React.useState<string>('');
  const [missingCharacterName, setMissingCharacterName] = React.useState('');
  const [missingStatus, setMissingStatus] = React.useState<string>('');
  const [cast, setCast] = React.useState<{ character_id: string; character_name: string }[]>([]);
  const [castLoading, setCastLoading] = React.useState(false);
  const [selectedCharId, setSelectedCharId] = React.useState<string>('');
  const [selectedCharName, setSelectedCharName] = React.useState<string>('');
  const [bookCharImageUrl, setBookCharImageUrl] = React.useState<string>('');
  const [bookCharGenerating, setBookCharGenerating] = React.useState(false);
  const [bookSceneBusy, setBookSceneBusy] = React.useState(false);
  const [bookCharError, setBookCharError] = React.useState<string>('');

  const [preparing, setPreparing] = React.useState(false);
  const [etaSeconds, setEtaSeconds] = React.useState<number>(45);
  const [countdown, setCountdown] = React.useState<number>(0);

  const [customPrompt, setCustomPrompt] = React.useState<string>('');
  const [customOut, setCustomOut] = React.useState<string>('');
  const [customImageUrl, setCustomImageUrl] = React.useState<string>('');
  const [customGenerating, setCustomGenerating] = React.useState(false);
  const [customSceneBusy, setCustomSceneBusy] = React.useState(false);
  const [customName, setCustomName] = React.useState<string>('Original character');

  const [books, setBooks] = React.useState<{ book_id: string; title: string; author?: string }[]>([]);
  const [booksLoading, setBooksLoading] = React.useState(false);
  const [booksError, setBooksError] = React.useState<string>('');

  const [usageRemaining, setUsageRemaining] = React.useState<number | null>(null);
  const [usageLimit, setUsageLimit] = React.useState<number>(5);
  const [showWalkthrough, setShowWalkthrough] = React.useState(false);
  const [historyLoading, setHistoryLoading] = React.useState(false);
  const [historyError, setHistoryError] = React.useState('');
  const [historyFilter, setHistoryFilter] = React.useState<'all' | 'book' | 'custom'>('all');
  const [historyItems, setHistoryItems] = React.useState<Array<{
    id: string;
    source_type?: string;
    character_name?: string;
    description?: string;
    image_url?: string;
    created_at?: string;
  }>>([]);

  const refreshUsage = React.useCallback(async () => {
    try {
      const res = await fetch('/api/usage', { cache: 'no-store' });
      const json = await res.json();
      if (json?.success) {
        setUsageRemaining(json.remaining_today ?? null);
        setUsageLimit(json.daily_limit ?? 5);
      }
    } catch {}
  }, []);

  const loadCastForBook = React.useCallback(async (bookId: string) => {
    if (!bookId) {
      setCast([]);
      return;
    }
    setCastLoading(true);
    try {
      const r = await fetch(`/api/characters?book_id=${encodeURIComponent(bookId)}`, { cache: 'no-store' });
      const j = await r.json();
      if (r.ok && j?.success && Array.isArray(j.characters)) {
        setCast(mapApiCharactersToCast(j.characters));
      } else {
        setCast([]);
      }
    } catch {
      setCast([]);
    } finally {
      setCastLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadCastForBook(selectedBookId);
  }, [selectedBookId, loadCastForBook]);

  React.useEffect(() => {
    if (!preparing) return;
    const startedAt = Date.now();
    setCountdown(etaSeconds);
    const t = window.setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000;
      const remaining = Math.max(0, Math.ceil(etaSeconds - elapsed));
      setCountdown(remaining);
      if (remaining <= 0) window.clearInterval(t);
    }, 250);
    return () => window.clearInterval(t);
  }, [preparing, etaSeconds]);

  React.useEffect(() => {
    refreshUsage();
    loadHistory();
  }, [refreshUsage]);

  React.useEffect(() => {
    try {
      const seen = window.localStorage.getItem('visulit_walkthrough_seen');
      if (!seen) setShowWalkthrough(true);
    } catch {}
  }, []);

  /** Single loader: full curated list when search is empty; debounced search when typing (fixes empty list after clearing search). */
  React.useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const q = bookQuery.trim();

    async function loadBooks() {
      setBooksLoading(true);
      setBooksError('');
      try {
        const url = q
          ? `/api/books?mode=curated&limit=80&query=${encodeURIComponent(q)}`
          : `/api/books?mode=curated&limit=80`;
        const res = await fetch(url, { cache: 'no-store', signal: controller.signal });
        const json = await res.json();
        if (!res.ok || !json?.success) throw new Error(json?.error || 'Failed to load books');
        const arr = Array.isArray(json.books) ? json.books : [];
        if (!cancelled) setBooks(arr);
      } catch (e: unknown) {
        if ((e as any)?.name === 'AbortError') return;
        if (!cancelled) setBooksError(e instanceof Error ? e.message : 'Failed to load books');
      } finally {
        if (!cancelled) setBooksLoading(false);
      }
    }

    const delayMs = q ? 250 : 0;
    const t = window.setTimeout(() => {
      loadBooks();
    }, delayMs);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(t);
    };
  }, [bookQuery]);

  function scrollToId(id: string) {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const filteredBooks = books;
  const filteredHistory = historyFilter === 'all'
    ? historyItems
    : historyItems.filter((h) => (h.source_type || '').toLowerCase() === historyFilter);

  async function loadHistory() {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const res = await fetch('/api/history', { cache: 'no-store' });
      const json = await res.json();
      if (!res.ok || !json?.success) throw new Error(json?.error || 'Failed to load history');
      setHistoryItems(Array.isArray(json.history) ? json.history : []);
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  }

  async function generateBookCharacter(forceNew = false) {
    if (!selectedCharId || bookCharGenerating) return;
    trackEvent('generate_clicked', { source_type: 'book' });
    setBookCharImageUrl('');
    setBookCharError('');
    setBookCharGenerating(true);
    const startedAt = Date.now();
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: selectedCharId,
          character_name: selectedCharName,
          auto_description: true,
          ...(forceNew ? { force_new: true } : {}),
        }),
      });
      const json = await readApiJson(res);
      if (!res.ok || !json?.success) {
        if (json?.limit_reached) {
          trackEvent('limit_reached', { source_type: 'book' });
        }
        throw new Error(
          json?.error ||
          `Generate failed (HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ''})`
        );
      }
      trackEvent('generate_success', {
        source_type: 'book',
        cached: Boolean(json?.cached),
      });
      setBookCharImageUrl(json.image_url || '');
      refreshUsage();
      loadHistory();
    } catch (e: unknown) {
      trackEvent('generate_failed', {
        source_type: 'book',
        error_message: e instanceof Error ? e.message.slice(0, 120) : 'Generate failed',
      });
      setBookCharError(e instanceof Error ? e.message : 'Generate failed');
    } finally {
      const elapsed = Date.now() - startedAt;
      const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
      if (remaining > 0) {
        await new Promise((r) => window.setTimeout(r, remaining));
      }
      setBookCharGenerating(false);
    }
  }

  async function generateCustomCharacter(forceNew = false) {
    const prompt = customPrompt.trim();
    if (!prompt || customGenerating) return;
    trackEvent('generate_clicked', { source_type: 'custom' });
    setCustomOut('');
    setCustomImageUrl('');
    setCustomGenerating(true);
    const startedAt = Date.now();
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_name: customName.trim() || 'Original character',
          description: prompt,
          ...(forceNew ? { force_new: true } : {}),
        }),
      });
      const json = await readApiJson(res);
      if (!res.ok || !json?.success) {
        if (json?.limit_reached) {
          trackEvent('limit_reached', { source_type: 'custom' });
        }
        throw new Error(
          json?.error ||
          `Generate failed (HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ''})`
        );
      }
      trackEvent('generate_success', {
        source_type: 'custom',
        cached: Boolean(json?.cached),
      });
      setCustomImageUrl(json.image_url || '');
      refreshUsage();
      loadHistory();
    } catch (e: unknown) {
      trackEvent('generate_failed', {
        source_type: 'custom',
        error_message: e instanceof Error ? e.message.slice(0, 120) : 'Generate failed',
      });
      setCustomOut(e instanceof Error ? e.message : 'Generate failed');
    } finally {
      const elapsed = Date.now() - startedAt;
      const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
      if (remaining > 0) {
        await new Promise((r) => window.setTimeout(r, remaining));
      }
      setCustomGenerating(false);
    }
  }

  async function generateBookSceneVariant(payload: SceneVariantPayload) {
    if (!selectedCharId || !bookCharImageUrl || bookSceneBusy) return;
    trackEvent('scene_variant_clicked', { source_type: 'book' });
    setBookCharError('');
    setBookSceneBusy(true);
    const startedAt = Date.now();
    try {
      const refB64 = await imageUrlToRawBase64(bookCharImageUrl);
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: selectedCharId,
          character_name: selectedCharName,
          scene_variant: payload,
          reference_image_base64: refB64,
          reference_image_url: bookCharImageUrl.startsWith('http') ? bookCharImageUrl : undefined,
        }),
      });
      const json = await readApiJson(res);
      if (!res.ok || !json?.success) {
        if (json?.limit_reached) {
          trackEvent('limit_reached', { source_type: 'book' });
        }
        throw new Error(
          json?.error ||
          `Scene change failed (HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ''})`
        );
      }
      trackEvent('scene_variant_success', { source_type: 'book' });
      setBookCharImageUrl(json.image_url || '');
      refreshUsage();
      loadHistory();
    } catch (e: unknown) {
      trackEvent('scene_variant_failed', {
        source_type: 'book',
        error_message: e instanceof Error ? e.message.slice(0, 120) : 'Scene change failed',
      });
      setBookCharError(e instanceof Error ? e.message : 'Scene change failed');
    } finally {
      const elapsed = Date.now() - startedAt;
      const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
      if (remaining > 0) {
        await new Promise((r) => window.setTimeout(r, remaining));
      }
      setBookSceneBusy(false);
    }
  }

  async function generateCustomSceneVariant(payload: SceneVariantPayload) {
    const base = customPrompt.trim();
    if (!base || !customImageUrl || customSceneBusy) return;
    trackEvent('scene_variant_clicked', { source_type: 'custom' });
    setCustomOut('');
    setCustomSceneBusy(true);
    const startedAt = Date.now();
    try {
      const refB64 = await imageUrlToRawBase64(customImageUrl);
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_name: customName.trim() || 'Original character',
          base_prompt: base,
          scene_variant: payload,
          reference_image_base64: refB64,
          reference_image_url: customImageUrl.startsWith('http') ? customImageUrl : undefined,
        }),
      });
      const json = await readApiJson(res);
      if (!res.ok || !json?.success) {
        if (json?.limit_reached) {
          trackEvent('limit_reached', { source_type: 'custom' });
        }
        throw new Error(
          json?.error ||
          `Scene change failed (HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ''})`
        );
      }
      trackEvent('scene_variant_success', { source_type: 'custom' });
      setCustomImageUrl(json.image_url || '');
      refreshUsage();
      loadHistory();
    } catch (e: unknown) {
      trackEvent('scene_variant_failed', {
        source_type: 'custom',
        error_message: e instanceof Error ? e.message.slice(0, 120) : 'Scene change failed',
      });
      setCustomOut(e instanceof Error ? e.message : 'Scene change failed');
    } finally {
      const elapsed = Date.now() - startedAt;
      const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
      if (remaining > 0) {
        await new Promise((r) => window.setTimeout(r, remaining));
      }
      setCustomSceneBusy(false);
    }
  }

  function buildCustomPrompt() {
    const name = (customName || '').trim() || 'Original character';
    return (
      `Portrait of ${name}. ` +
      'Style: tasteful literary portrait, soft lighting, neutral background. ' +
      'Avoid explicit copyrighted references.'
    );
  }

  return (
    <section className="w-full text-sm bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(255,182,213,0.55),transparent_60%),radial-gradient(ellipse_70%_50%_at_0%_0%,rgba(255,212,232,0.65),transparent_55%),linear-gradient(180deg,#fff7fb_0%,#fff_55%,#fff7fb_100%)]">
      {showWalkthrough && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="max-h-[min(90vh,32rem)] w-full max-w-lg overflow-y-auto rounded-3xl border border-pink-200 bg-white p-6 shadow-xl">
            <h3 className="text-xl font-semibold text-pink-950">Welcome to {BRAND_NAME}</h3>
            <p className="mt-2 text-sm text-pink-950/70">Quick 3-step walkthrough:</p>
            <ol className="mt-4 space-y-2 text-sm text-pink-950/80 list-decimal list-inside">
              <li>Choose a book and click <span className="font-semibold">Prepare book</span>.</li>
              <li>Pick a character and click <span className="font-semibold">Generate portrait</span>.</li>
              <li>Download or regenerate if you want another variation.</li>
            </ol>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                className="bg-pink-950 hover:bg-pink-900 text-white px-5 py-2.5 rounded-full font-medium transition"
                onClick={() => {
                  setShowWalkthrough(false);
                  try { window.localStorage.setItem('visulit_walkthrough_seen', '1'); } catch {}
                }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
      <nav className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-3 px-3 py-4 sm:px-4 md:px-16 lg:px-24 xl:px-32 md:py-6">
        <a href="#" aria-label={`${BRAND_NAME} home`} className="flex min-w-0 shrink-0 items-center gap-2 sm:gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-pink-200/70 text-pink-900 ring-1 ring-pink-300/40 sm:h-10 sm:w-10">
            <BookOpenText className="h-5 w-5" />
          </span>
          <span className="truncate font-semibold tracking-tight text-pink-950">{BRAND_NAME}</span>
        </a>
        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2 sm:flex-none sm:gap-3">
          {usageRemaining !== null && (
            <span
              className={`inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[11px] font-semibold ring-1 sm:px-3 sm:text-xs ${
                usageRemaining === 0
                  ? 'bg-red-50 text-red-700 ring-red-200'
                  : usageRemaining <= 2
                  ? 'bg-amber-50 text-amber-700 ring-amber-200'
                  : 'bg-pink-50 text-pink-800 ring-pink-200'
              }`}
            >
              <Sparkles className="h-3 w-3 shrink-0" />
              <span className="sm:hidden">
                {usageRemaining === 0 ? 'None left' : `${usageRemaining}/${usageLimit} left`}
              </span>
              <span className="hidden sm:inline">
                {usageRemaining === 0
                  ? 'No free generations left today'
                  : `${usageRemaining} of ${usageLimit} free today`}
              </span>
            </span>
          )}
          <button
            type="button"
            onClick={() => scrollToId('characters')}
            className="shrink-0 rounded-full bg-pink-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-pink-900 sm:px-5 sm:py-3 sm:text-base"
          >
            Try it free
          </button>
        </div>
      </nav>

      <div id="top" />

      <div className="px-4">
        <div className="mx-auto mt-20 flex w-full max-w-3xl flex-col items-stretch gap-3 rounded-3xl border border-pink-200 bg-white/60 px-4 py-3 text-center backdrop-blur sm:mt-24 sm:flex-row sm:flex-wrap sm:items-center sm:justify-center sm:gap-x-4 sm:gap-y-2 sm:text-left md:mt-20">
          <div className="flex items-start justify-center gap-2 sm:min-w-0 sm:flex-1 sm:items-center sm:justify-start">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-pink-700 sm:mt-0" />
            <span className="text-left text-sm text-pink-950/80 sm:text-base">
              Quotes are extracted from the original book text (no inventions)
            </span>
          </div>
          <button
            type="button"
            onClick={() => scrollToId('characters')}
            className="inline-flex shrink-0 items-center justify-center gap-1 rounded-full py-1.5 text-sm font-medium text-pink-900 hover:text-pink-700 sm:py-0"
          >
            <span>See examples</span>
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <h1 className="mx-auto mt-8 max-w-[900px] px-4 text-center text-3xl font-semibold text-balance text-pink-950 sm:text-4xl md:text-6xl lg:text-7xl">
        Meet your favorite characters with {BRAND_NAME} — {usageLimit} free generations daily
      </h1>

      <p className="mx-auto mt-6 max-w-2xl px-4 text-center text-sm text-pink-950/70 md:text-base">
        {BRAND_NAME} extracts character lists and appearance quotes from public-domain books, then builds photorealistic portrait prompts
        you can reuse, tweak, and regenerate in seconds.
      </p>

      <div className="mx-auto mt-5 w-full max-w-2xl px-4 text-center">
        <div className="rounded-2xl border border-pink-200 bg-white/70 px-4 py-3 text-sm text-pink-950/85 shadow-sm backdrop-blur">
          <span className="font-semibold text-pink-950">Free to try</span>
          {' · '}
          <span>
            {usageLimit} portrait generations per day — no credit card
          </span>
          {' · '}
          <span className="text-pink-950/90">No signup required</span>
        </div>
      </div>

      {usageRemaining !== null && (
        <p className="mx-auto mt-3 max-w-2xl px-4 text-center text-xs font-medium text-pink-900/70">
          Today&apos;s generations:{' '}
          <span className="text-pink-950">
            {usageRemaining} of {usageLimit} remaining
          </span>
        </p>
      )}

      <div className="mx-auto mt-8 flex w-full flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => scrollToId('characters')}
          className="bg-pink-950 hover:bg-pink-900 text-white px-6 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
        >
          <Search className="h-4 w-4" />
          Find characters
        </button>
        <button
          type="button"
          onClick={() => scrollToId('custom')}
          className="flex items-center gap-2 border border-pink-200 bg-white/60 hover:bg-pink-50 rounded-full px-6 py-3 text-pink-950"
        >
          <PenLine className="h-4 w-4" />
          Create your own character
        </button>
      </div>

      <div className="h-24 md:h-28" />

      {/* BOOK PICKER */}
      <div id="characters" className="mx-auto w-full max-w-5xl scroll-mt-24 px-4 md:px-16 lg:px-24 xl:px-32 pb-16">
        <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-4 py-2 ring-1 ring-pink-200 text-pink-950 w-max">
            <Search className="h-4 w-4 text-pink-700" />
            <span className="font-semibold">Find characters</span>
          </div>

          <h2 className="mt-4 text-2xl md:text-3xl font-semibold text-pink-950">
            Start with one book, let {BRAND_NAME} prepare the cast
          </h2>
          <p className="mt-3 max-w-2xl text-pink-950/70">
            Search by title, pick from our curated list, then prepare the book. If a character is missing, type the name and we'll add
            them by searching the book text.
          </p>
          <p className="mt-2 text-xs text-pink-900/65">
            40+ curated picks · Extended catalog matches when your title isn&apos;t on the shortlist · Quote-grounded portraits
          </p>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            {/* LEFT: book search + cast */}
            <div>
              <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Book search</div>
              <div className="mt-2 flex items-center gap-2 rounded-2xl border border-pink-200 bg-white/70 px-4 py-3">
                <Search className="h-4 w-4 text-pink-700" />
                <input
                  value={bookQuery}
                  onChange={(e) => setBookQuery(e.target.value)}
                  placeholder="Search curated titles — full catalog expands matches…"
                  className="w-full bg-transparent text-sm text-pink-950 placeholder:text-pink-950/40 outline-none"
                />
              </div>

              <div className="mt-3 max-h-64 overflow-auto rounded-2xl border border-pink-200 bg-white/70">
                {booksLoading ? (
                  <div className="px-4 py-4 text-sm text-pink-950/60">Loading books…</div>
                ) : booksError ? (
                  <div className="px-4 py-4 text-sm text-red-700">
                    <ErrorWithSupport message={booksError} />
                  </div>
                ) : filteredBooks.map((b) => (
                  <button
                    key={b.book_id}
                    type="button"
                    onClick={() => {
                      setSelectedBookId(b.book_id);
                      setMissingStatus('');
                      setSelectedCharId('');
                      setSelectedCharName('');
                      setBookCharImageUrl('');
                      setBookCharError('');
                    }}
                    className={[
                      'w-full text-left px-4 py-3 border-b border-pink-100 hover:bg-pink-50 transition',
                      selectedBookId === b.book_id ? 'bg-pink-50 font-semibold' : '',
                    ].join(' ')}
                  >
                    <div className="font-semibold text-pink-950">{b.title}</div>
                    <div className="text-xs text-pink-950/70">{b.author}</div>
                  </button>
                ))}
                {!booksLoading && !booksError && !filteredBooks.length && (
                  <div className="px-4 py-4 text-sm text-pink-950/60">
                    {bookQuery.trim() ? (
                      <>
                        No matches for &quot;{bookQuery.trim()}&quot;. Try another keyword, or{' '}
                        <button
                          type="button"
                          className="font-medium text-pink-900 underline underline-offset-2 hover:text-pink-700"
                          onClick={() => setBookQuery('')}
                        >
                          clear search
                        </button>{' '}
                        to show the full curated list.
                      </>
                    ) : (
                      'No books returned. Check your connection and refresh the page.'
                    )}
                  </div>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={!selectedBookId || preparing}
                  onClick={async () => {
                    if (!selectedBookId || preparing) return;
                    trackEvent('prepare_book_clicked');
                    setMissingStatus('');
                    setCast([]);
                    setSelectedCharId('');
                    setSelectedCharName('');
                    setBookCharImageUrl('');
                    setBookCharError('');
                    setPreparing(true);
                    setEtaSeconds(45);
                    try {
                      const res = await fetch('/api/prepare_book', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ book_id: selectedBookId, overwrite: false, main_limit: 18 }),
                      });
                      const json = await res.json();
                      if (!res.ok || !json?.success) throw new Error(json?.error || 'Prepare failed');
                      trackEvent('prepare_book_success', {
                        cached: Boolean(json?.cached),
                        count: Number(json?.count || 0),
                      });

                      const eta = Number(json.eta_seconds || 45);
                      setEtaSeconds(Number.isFinite(eta) ? eta : 45);

                      const chars = Array.isArray(json.characters) ? json.characters : null;
                      if (chars) {
                        setCast(mapApiCharactersToCast(chars));
                      } else {
                        await loadCastForBook(selectedBookId);
                      }

                      setMissingStatus('Prepared.');
                    } catch (e: unknown) {
                      trackEvent('prepare_book_failed', {
                        error_message: e instanceof Error ? e.message.slice(0, 120) : 'Prepare failed',
                      });
                      setMissingStatus(e instanceof Error ? e.message : 'Prepare failed');
                    } finally {
                      setPreparing(false);
                      setCastLoading(false);
                    }
                  }}
                  className="bg-pink-950 hover:bg-pink-900 disabled:opacity-50 text-white px-5 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  {preparing ? 'Preparing…' : 'Prepare book'}
                </button>
              </div>

              {preparing ? (
                <div className="mt-3 text-sm text-pink-950/70">Preparing… ~{countdown || etaSeconds}s left</div>
              ) : (
                missingStatus && (
                  <div className="mt-3 break-words text-sm text-pink-950/70">{missingStatus}</div>
                )
              )}

              {/* CAST + GENERATE */}
              <div className="mt-5 rounded-2xl border border-pink-200 bg-white/60 p-4">
                <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Cast</div>
                {castLoading ? (
                  <div className="mt-2 text-sm text-pink-950/60">Loading characters…</div>
                ) : cast.length ? (
                  <>
                    <select
                      value={selectedCharId}
                      onChange={(e) => {
                        const id = e.target.value;
                        setSelectedCharId(id);
                        setBookCharImageUrl('');
                        setBookCharError('');
                        if (!id) {
                          setSelectedCharName('');
                          return;
                        }
                        const c = cast.find((x) => x.character_id === id);
                        setSelectedCharName(c?.character_name || '');
                      }}
                      className="mt-2 w-full rounded-2xl border border-pink-200 bg-white/70 px-4 py-3 text-sm text-pink-950 outline-none"
                    >
                      <option value="">— Select a character —</option>
                      {cast.map((c) => (
                        <option key={c.character_id} value={c.character_id}>
                          {c.character_name}
                        </option>
                      ))}
                    </select>

                    {selectedCharId && (
                      <div className="mt-3">
                        {usageRemaining !== null && (
                          <p className={`mb-2 text-xs font-medium ${usageRemaining === 0 ? 'text-red-600' : 'text-pink-900/60'}`}>
                            {usageRemaining === 0
                              ? 'No free generations left for today. Come back tomorrow!'
                              : `${usageRemaining} free generation${usageRemaining === 1 ? '' : 's'} left today`}
                          </p>
                        )}
                        <button
                          type="button"
                          disabled={bookCharGenerating || bookSceneBusy || usageRemaining === 0}
                          onClick={() => generateBookCharacter()}
                          className="inline-flex w-full min-h-[44px] items-center justify-center gap-2 rounded-full bg-pink-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-pink-900 disabled:opacity-50 sm:text-base"
                        >
                          <Sparkles className="h-4 w-4 shrink-0" />
                          <span className="text-center leading-snug">
                            {bookCharGenerating
                              ? 'Generating portrait…'
                              : `Generate portrait of ${selectedCharName || 'character'}`}
                          </span>
                        </button>
                        {(bookCharGenerating || bookSceneBusy) && (
                          <div className="mt-2 text-xs text-center text-pink-950/60">
                            {bookSceneBusy ? 'Changing scene… this may take up to a minute.' : 'This may take up to a minute…'}
                          </div>
                        )}
                        {bookCharImageUrl && !bookCharGenerating && (
                          <PortraitCard
                            imageUrl={bookCharImageUrl}
                            altText={`Portrait of ${selectedCharName}`}
                            filename={`${selectedCharName.replace(/\s+/g, '-').toLowerCase()}-portrait.jpg`}
                            onRegenerate={() => generateBookCharacter(true)}
                            regenerating={bookCharGenerating || bookSceneBusy}
                            onSceneVariant={generateBookSceneVariant}
                            sceneVariantBusy={bookSceneBusy}
                          />
                        )}
                        {bookCharError && !bookCharGenerating && !bookSceneBusy && (
                          <div className="mt-2 text-xs text-red-700">
                            <ErrorWithSupport message={bookCharError} />
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : !selectedBookId ? (
                  <div className="mt-2 text-sm text-pink-950/60">Select a book above to load the cast.</div>
                ) : (
                  <div className="mt-2 text-sm text-pink-950/60">
                    No characters yet. Prepare the book, or add someone below — additions are saved for everyone on this site.
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT: missing character */}
            <div>
              <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">
                Missing a character?
              </div>
              <div className="mt-2 rounded-2xl border border-pink-200 bg-white/70 p-4">
                <div className="text-sm font-semibold text-pink-950">Didn't find someone in the cast?</div>
                <div className="mt-1 text-sm text-pink-950/70">
                  Type the name as in the book. We search the text and add them to the shared cast — visible to all visitors, not just your browser.
                </div>
                <div className="mt-4 flex items-center gap-2 rounded-2xl border border-pink-200 bg-white/70 px-4 py-3">
                  <PenLine className="h-4 w-4 text-pink-700" />
                  <input
                    value={missingCharacterName}
                    onChange={(e) => setMissingCharacterName(e.target.value)}
                    placeholder="e.g. John Brooke"
                    className="w-full bg-transparent text-sm text-pink-950 placeholder:text-pink-950/40 outline-none"
                  />
                </div>
                <div className="mt-4 flex items-center gap-3">
                  <button
                    type="button"
                    disabled={!selectedBookId || !missingCharacterName.trim()}
                    onClick={async () => {
                      const name = missingCharacterName.trim();
                      if (!selectedBookId || !name) return;
                      setMissingStatus('');
                      try {
                        const res = await fetch('/api/add_character', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ book_id: selectedBookId, character_name: name }),
                        });
                        const json = await res.json();
                        if (!res.ok || !json?.success) throw new Error(json?.error || 'Failed to add character');
                        setMissingStatus(`Added: ${json?.character?.character_name || name}`);
                        setMissingCharacterName('');
                        const newId = String(json?.character?.character_id || '');
                        const newName = String(json?.character?.character_name || name);
                        await loadCastForBook(selectedBookId);
                        if (newId) {
                          setSelectedCharId(newId);
                          setSelectedCharName(newName);
                        }
                      } catch (e: unknown) {
                        setMissingStatus(e instanceof Error ? e.message : 'Failed to add character');
                      } finally {
                        setCastLoading(false);
                      }
                    }}
                    className="bg-pink-100 hover:bg-pink-200 disabled:opacity-50 text-pink-950 px-5 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
                  >
                    <Search className="h-4 w-4" />
                    Add character
                  </button>
                  {/* Technical book_id not shown to keep UI clean */}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CUSTOM CHARACTER */}
      <div id="custom" className="mx-auto w-full max-w-6xl px-4 md:px-16 lg:px-24 xl:px-32 pb-20">
        <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-pink-50 px-4 py-2 ring-1 ring-pink-200 text-pink-950 w-max">
            <PenLine className="h-4 w-4 text-pink-700" />
            <span className="font-semibold">Your own character</span>
          </div>
          <div className="mt-4 grid gap-8 lg:grid-cols-2 lg:items-start">
            <div>
              <h2 className="text-2xl md:text-3xl font-semibold text-pink-950">Create a branded {BRAND_NAME} prompt in 30 seconds</h2>
              <p className="mt-3 text-pink-950/70 max-w-xl">
                Use a guided form (hair, eyes, era, clothing) to generate a clean prompt in the {BRAND_NAME} style. Your prompt stays on
                this page for easy reuse and fast iteration.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => scrollToId('top')}
                  className="bg-white/70 hover:bg-white text-pink-950 px-5 py-3 rounded-full font-medium transition ring-1 ring-pink-200 inline-flex items-center gap-2"
                >
                  <BookOpenText className="h-4 w-4" />
                  Back to top
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const p = buildCustomPrompt();
                    setCustomPrompt((prev) => prev || p);
                    setCustomOut('');
                    setCustomImageUrl('');
                  }}
                  className="bg-pink-950 hover:bg-pink-900 text-white px-5 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  Build prompt
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-pink-200 bg-gradient-to-br from-white to-pink-50 p-5">
              <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Prompt</div>
              <div className="mt-3 grid gap-3">
                <div>
                  <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Name</div>
                  <input
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    className="mt-2 w-full rounded-2xl border border-pink-200 bg-white/70 px-4 py-3 text-sm text-pink-950 outline-none"
                    placeholder="Character name…"
                  />
                </div>
                <div>
                  <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Edit / extend</div>
                  <textarea
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    className="mt-2 w-full min-h-[120px] rounded-2xl border border-pink-200 bg-white/70 px-4 py-3 text-sm text-pink-950 outline-none"
                    placeholder="Build a prompt, then edit it here…"
                  />
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      const p = buildCustomPrompt();
                      setCustomPrompt((prev) => (prev ? prev : p));
                      setCustomOut('');
                      setCustomImageUrl('');
                    }}
                    className="bg-white/70 hover:bg-white text-pink-950 px-5 py-3 rounded-full font-medium transition ring-1 ring-pink-200 inline-flex items-center gap-2"
                  >
                    <PenLine className="h-4 w-4" />
                    Use template
                  </button>
                  <button
                    type="button"
                    disabled={!customPrompt.trim() || customGenerating || customSceneBusy || usageRemaining === 0}
                    onClick={() => generateCustomCharacter()}
                    className="bg-pink-950 hover:bg-pink-900 disabled:opacity-50 text-white px-5 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    {customGenerating ? 'Generating…' : 'Generate'}
                  </button>
                </div>

                {(customGenerating || customSceneBusy) && (
                  <div className="rounded-2xl border border-pink-200 bg-white/60 p-4 text-center text-sm text-pink-950/70">
                    {customSceneBusy
                      ? 'Changing scene… this may take up to a minute.'
                      : 'Generating portrait… this may take up to a minute.'}
                  </div>
                )}
                {customImageUrl && !customGenerating && (
                  <PortraitCard
                    imageUrl={customImageUrl}
                    altText="Generated portrait"
                    filename={`${(customName || 'portrait').replace(/\s+/g, '-').toLowerCase()}-portrait.jpg`}
                    onRegenerate={() => generateCustomCharacter(true)}
                    regenerating={customGenerating || customSceneBusy}
                    onSceneVariant={generateCustomSceneVariant}
                    sceneVariantBusy={customSceneBusy}
                  />
                )}
                {customOut && !customGenerating && !customSceneBusy && (
                  <div className="rounded-2xl border border-pink-200 bg-white/60 p-4">
                    <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Error</div>
                    <div className="mt-2 text-sm text-red-700 leading-relaxed">
                      <ErrorWithSupport message={customOut} />
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-4 flex items-center gap-2 text-xs text-pink-900/70">
                <Sparkles className="h-4 w-4 text-pink-700" />
                Your generated prompt and portrait are ready for reuse.
              </div>
            </div>
          </div>
        </div>
      </div>

      <ExamplesGallery />

      {/* HISTORY */}
      <div className="mx-auto w-full max-w-6xl px-4 md:px-16 lg:px-24 xl:px-32 pb-20">
        <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl md:text-3xl font-semibold text-pink-950">History</h2>
            <div className="flex items-center gap-2">
              {(['all', 'book', 'custom'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setHistoryFilter(f)}
                  className={[
                    'px-3 py-1.5 rounded-full text-xs font-medium ring-1 transition',
                    historyFilter === f
                      ? 'bg-pink-950 text-white ring-pink-950'
                      : 'bg-white/70 text-pink-950 ring-pink-200 hover:bg-pink-50',
                  ].join(' ')}
                >
                  {f === 'all' ? 'All' : f === 'book' ? 'Book' : 'Custom'}
                </button>
              ))}
              <button
                type="button"
                onClick={loadHistory}
                className="px-3 py-1.5 rounded-full text-xs font-medium ring-1 ring-pink-200 text-pink-950 bg-white/70 hover:bg-pink-50 transition"
              >
                Refresh
              </button>
            </div>
          </div>
          {historyError && <div className="mt-3 text-sm text-red-700"><ErrorWithSupport message={historyError} /></div>}
          {historyLoading ? (
            <div className="mt-4 text-sm text-pink-950/70">Loading history…</div>
          ) : filteredHistory.length === 0 ? (
            <div className="mt-4 text-sm text-pink-950/70">No generations yet.</div>
          ) : (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {filteredHistory.slice(0, 12).map((h) => (
                <div key={h.id} className="rounded-2xl border border-pink-200 bg-white/70 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-pink-950">{h.character_name || 'Character'}</div>
                    <span className="text-xs text-pink-900/60 uppercase">{h.source_type || 'unknown'}</span>
                  </div>
                  {h.image_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={h.image_url} alt={h.character_name || 'History portrait'} className="mt-2 w-full rounded-xl object-cover" />
                  )}
                  <div className="mt-2 text-xs text-pink-950/70 line-clamp-3">{h.description || 'No prompt saved.'}</div>
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-full text-xs font-medium ring-1 ring-pink-200 text-pink-950 bg-white hover:bg-pink-50 transition"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(h.description || '');
                        } catch {}
                      }}
                    >
                      Copy prompt
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* FAQ */}
      <div className="mx-auto w-full max-w-6xl px-4 md:px-16 lg:px-24 xl:px-32 pb-20">
        <div className="mx-auto max-w-3xl rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-8 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h3 className="text-xl md:text-2xl font-semibold text-pink-950">FAQ</h3>
            <button
              type="button"
              onClick={() => scrollToId('gallery')}
              className="text-sm font-medium text-pink-900 underline underline-offset-2 hover:text-pink-700"
            >
              Portrait gallery ↑
            </button>
          </div>
            <div className="mt-4 space-y-3 text-sm text-pink-950/80">
              <details className="rounded-2xl border border-pink-200 bg-white/70 p-3">
                <summary className="cursor-pointer font-medium text-pink-950">Why these quotes?</summary>
                <p className="mt-2">We prioritize lines with stable visual details: face, hair, eyes, clothing, figure, and color terms.</p>
              </details>
              <details className="rounded-2xl border border-pink-200 bg-white/70 p-3">
                <summary className="cursor-pointer font-medium text-pink-950">Why does the portrait differ from my imagination?</summary>
                <p className="mt-2">The prompt is quote-first. When source text is sparse, the model fills gaps with neutral, era-consistent details.</p>
              </details>
              <details className="rounded-2xl border border-pink-200 bg-white/70 p-3">
                <summary className="cursor-pointer font-medium text-pink-950">Can I regenerate?</summary>
                <p className="mt-2">Yes, use the Regenerate button under each portrait card for a new variation.</p>
              </details>
              <details className="rounded-2xl border border-pink-200 bg-white/70 p-3">
                <summary className="cursor-pointer font-medium text-pink-950">Can I change scene but keep the same face?</summary>
                <p className="mt-2">
                  Use <span className="font-medium">New scene (same character)</span> under a portrait: describe emotion, pose, and place.
                  We send your current image as a reference and stress identity in the prompt. Results vary by model; perfect likeness is not guaranteed without a provider that accepts reference images (see server env <code className="text-xs">IMAGE_REFERENCE_BASE64_FIELD</code>).
                </p>
              </details>
            </div>
        </div>
      </div>

      <footer className="border-t border-pink-200/60 bg-white/50">
        <div className="mx-auto w-full max-w-6xl px-4 md:px-16 lg:px-24 xl:px-32 py-10 flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
          <div className="text-pink-950 font-semibold">{BRAND_NAME}</div>
          <div className="text-pink-950/70 text-xs text-center md:text-right">
            <span className="block md:inline">Quotes-first extraction · Literary portraits</span>
            <span className="mx-2 hidden md:inline">·</span>
            <Link
              href="/cookies"
              className="text-pink-900 underline underline-offset-2 hover:text-pink-700"
            >
              Cookies
            </Link>
            <span className="mx-2 hidden md:inline">·</span>
            <a
              href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`${BRAND_NAME} — support`)}`}
              className="text-pink-900 underline underline-offset-2 hover:text-pink-700"
            >
              {SUPPORT_EMAIL}
            </a>
          </div>
        </div>
      </footer>
    </section>
  );
}
