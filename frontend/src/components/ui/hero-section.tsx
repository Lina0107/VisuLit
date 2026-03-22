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
import { BRAND_NAME, SUPPORT_EMAIL } from '@/lib/brand';

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

// Small reusable component: image card with watermark download button
function PortraitCard({ imageUrl, altText, filename }: { imageUrl: string; altText: string; filename: string }) {
  const [downloading, setDownloading] = React.useState(false);

  return (
    <div className="mt-3 rounded-2xl border border-pink-200 bg-white/60 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold text-pink-900/70 uppercase tracking-wider">Generated portrait</div>
        <button
          type="button"
          disabled={downloading}
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
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageUrl} alt={altText} className="w-full rounded-xl object-cover" />
    </div>
  );
}

const MIN_GENERATE_SPINNER_MS = 1800;

function quoteText(q: any): string {
  if (!q) return '';
  if (typeof q === 'string') return q;
  if (typeof q.quote === 'string') return q.quote;
  return '';
}

function pickFirstMatchingQuote(items: any[], allowKeywords: string[], rejectPatterns: RegExp[]): string {
  const kws = allowKeywords.map((k) => k.toLowerCase());
  for (const it of items || []) {
    const txt = (quoteText(it) || '').trim();
    if (!txt) continue;
    if (rejectPatterns.some((re) => re.test(txt))) continue;
    if (kws.length === 0) return txt;
    const lower = txt.toLowerCase();
    if (kws.some((kw) => lower.includes(kw))) return txt;
  }
  for (const it of items || []) {
    const txt = (quoteText(it) || '').trim();
    if (!txt) continue;
    if (rejectPatterns.some((re) => re.test(txt))) continue;
    return txt;
  }
  return '';
}

function pickBestAppearanceQuote(items: any[]): string {
  const rejectMeta = [/CHAPTER/i, /Heading to Chapter/i, /Tailpiece/i];

  const groups: Array<{ keywords: string[]; weight: number }> = [
    { keywords: ['eyes', 'eye', 'brow', 'cheek', 'complexion', 'lips', 'face', 'countenance', 'handsome', 'beautiful'], weight: 10 },
    { keywords: ['hair', 'ringlet', 'curly', 'locks'], weight: 9 },
    { keywords: ['gown', 'petticoat', 'dress', 'coat', 'clothe', 'clothing'], weight: 7 },
    { keywords: ['figure', 'height', 'tall', 'slender', 'stature'], weight: 6 },
    { keywords: ['red', 'blue', 'gray', 'grey', 'green', 'black', 'brown', 'white'], weight: 5 },
  ];

  let best = '';
  let bestScore = -1;

  for (const it of items || []) {
    const txt = (quoteText(it) || '').trim();
    if (!txt) continue;
    if (rejectMeta.some((re) => re.test(txt))) continue;

    const lower = txt.toLowerCase();
    let score = 0;
    for (const g of groups) {
      if (g.keywords.some((kw) => lower.includes(kw))) score += g.weight;
    }

    if (score > bestScore) {
      bestScore = score;
      best = txt;
    }
  }

  // fallback to the first non-empty
  if (best) return best;
  for (const it of items || []) {
    const txt = (quoteText(it) || '').trim();
    if (txt) return txt;
  }
  return '';
}

function pickBestEvidenceQuote(items: any[]): string {
  const rejectMeta = [/CHAPTER/i, /Heading to Chapter/i, /Tailpiece/i, /Journal/i, /Diary/i];
  return pickFirstMatchingQuote(
    items,
    // prefer a real sentence-ish evidence chunk
    ['said', 'went', 'walk', 'danced', 'entered', 'obliged', 'had been', 'mr', 'miss', 'bennet', 'darcy', 'she', 'he'],
    rejectMeta
  );
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
  const [bookCharError, setBookCharError] = React.useState<string>('');

  const [preparing, setPreparing] = React.useState(false);
  const [etaSeconds, setEtaSeconds] = React.useState<number>(45);
  const [countdown, setCountdown] = React.useState<number>(0);

  const [customPrompt, setCustomPrompt] = React.useState<string>('');
  const [customOut, setCustomOut] = React.useState<string>('');
  const [customImageUrl, setCustomImageUrl] = React.useState<string>('');
  const [customGenerating, setCustomGenerating] = React.useState(false);
  const [customName, setCustomName] = React.useState<string>('Original character');

  const [books, setBooks] = React.useState<{ book_id: string; title: string; author?: string }[]>([]);
  const [booksLoading, setBooksLoading] = React.useState(false);
  const [booksError, setBooksError] = React.useState<string>('');

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

  const lastQueryRef = React.useRef<string>('');

  React.useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function loadInitial() {
      setBooksLoading(true);
      setBooksError('');
      try {
        const res = await fetch(`/api/books?mode=curated&limit=80`, {
          cache: 'no-store',
          signal: controller.signal,
        });
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

    loadInitial();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  React.useEffect(() => {
    const q = bookQuery.trim();
    if (q === lastQueryRef.current) return;
    lastQueryRef.current = q;

    if (!q) return;

    let cancelled = false;
    const controller = new AbortController();

    async function loadSearch() {
      setBooksLoading(true);
      setBooksError('');
      try {
        const res = await fetch(
          `/api/books?mode=curated&limit=80&query=${encodeURIComponent(q)}`,
          { cache: 'no-store', signal: controller.signal },
        );
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

    const t = window.setTimeout(loadSearch, 250);
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
      <nav className="flex items-center justify-between p-4 md:px-16 lg:px-24 xl:px-32 md:py-6 w-full">
        <a href="#" aria-label={`${BRAND_NAME} home`} className="flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-pink-200/70 text-pink-900 ring-1 ring-pink-300/40">
            <BookOpenText className="h-5 w-5" />
          </span>
          <span className="font-semibold tracking-tight text-pink-950">{BRAND_NAME}</span>
        </a>
        <button
          type="button"
          onClick={() => scrollToId('characters')}
          className="bg-pink-950 hover:bg-pink-900 text-white px-5 py-3 rounded-full font-medium transition"
        >
          Get started
        </button>
      </nav>

      <div id="top" />

      <div className="flex items-center gap-2 border border-pink-200 hover:border-pink-300/70 rounded-full w-max mx-auto px-4 py-2 mt-24 md:mt-20 bg-white/60 backdrop-blur">
        <Sparkles className="h-4 w-4 text-pink-700" />
        <span className="text-pink-950/80">Quotes are extracted from the original book text (no inventions)</span>
        <button
          type="button"
          onClick={() => scrollToId('characters')}
          className="flex items-center gap-1 font-medium text-pink-900 hover:text-pink-700"
        >
          <span>See examples</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <h1 className="text-4xl md:text-7xl font-semibold max-w-[900px] text-center mx-auto mt-8 text-pink-950">
        Bring your favourite characters to life
      </h1>

      <p className="text-sm md:text-base mx-auto max-w-2xl text-center mt-6 max-md:px-2 text-pink-950/70">
        We extract character lists and visual appearance quotes straight from public-domain books, then build a high-quality portrait
        prompt you can reuse.
      </p>

      <div className="mx-auto w-full flex items-center justify-center gap-3 mt-8 flex-wrap">
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
      <div id="characters" className="mx-auto w-full max-w-5xl px-4 md:px-16 lg:px-24 xl:px-32 pb-16">
        <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-4 py-2 ring-1 ring-pink-200 text-pink-950 w-max">
            <Search className="h-4 w-4 text-pink-700" />
            <span className="font-semibold">Find characters</span>
          </div>

          <h2 className="mt-4 text-2xl md:text-3xl font-semibold text-pink-950">
            Choose a book from the list and prepare its characters
          </h2>
          <p className="mt-3 text-pink-950/70 max-w-2xl">
            Search by title, pick from our curated list, then prepare the book. If a character is missing, type the name and we'll add
            them by searching the book text.
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
                  placeholder="Type a book title…"
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
                      setCast([]);
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
                  <div className="px-4 py-4 text-sm text-pink-950/60">No matches.</div>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={!selectedBookId || preparing}
                  onClick={async () => {
                    if (!selectedBookId || preparing) return;
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

                      const eta = Number(json.eta_seconds || 45);
                      setEtaSeconds(Number.isFinite(eta) ? eta : 45);

                      const chars = Array.isArray(json.characters) ? json.characters : null;
                      if (chars) {
                        setCast(
                          chars
                            .map((c: any) => ({
                              character_id: String(c.character_id || ''),
                              character_name: String(c.character_name || ''),
                            }))
                            .filter((c: any) => c.character_id && c.character_name),
                        );
                      } else {
                        setCastLoading(true);
                        const r2 = await fetch(`/api/characters?book_id=${encodeURIComponent(selectedBookId)}`, { cache: 'no-store' });
                        const j2 = await r2.json();
                        if (r2.ok && j2?.success && Array.isArray(j2.characters)) {
                          setCast(
                            j2.characters
                              .map((c: any) => ({
                                character_id: String(c.character_id || ''),
                                character_name: String(c.character_name || ''),
                              }))
                              .filter((c: any) => c.character_id && c.character_name),
                          );
                        }
                      }

                      setMissingStatus('Prepared.');
                    } catch (e: unknown) {
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
                missingStatus && <div className="mt-3 text-sm text-pink-950/70">{missingStatus}</div>
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
                      onChange={async (e) => {
                        const id = e.target.value;
                        setSelectedCharId(id);
                        setBookCharImageUrl('');
                        setBookCharError('');
                        if (!id || !selectedBookId) { setSelectedCharName(''); return; }
                        try {
                          const r = await fetch(`/api/characters?book_id=${encodeURIComponent(selectedBookId)}`, { cache: 'no-store' });
                          const j = await r.json();
                          if (!r.ok || !j?.success) return;
                          const full = Array.isArray(j.characters) ? j.characters : [];
                          const found = full.find((x: any) => String(x.character_id) === id);
                          if (found) {
                            setSelectedCharName(found.character_name || '');
                            const apq = Array.isArray(found.appearance_quotes) ? found.appearance_quotes : [];
                            const evq = Array.isArray(found.evidence_quotes) ? found.evidence_quotes : [];
                            const bestA = pickBestAppearanceQuote(apq);
                            const bestE = pickBestEvidenceQuote(evq);
                            const firstA = bestA ? `Appearance: "${bestA}"` : 'No appearance quote.';
                            const firstE = bestE ? `Evidence: "${bestE}"` : '';
                            setMissingStatus([found.character_name, firstA, firstE].filter(Boolean).join('  ·  '));
                          }
                        } catch {}
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
                        <button
                          type="button"
                          disabled={bookCharGenerating}
                          onClick={async () => {
                            if (!selectedCharId || bookCharGenerating) return;
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
                                }),
                              });
                              const json = await res.json();
                              if (!res.ok || !json?.success) throw new Error(json?.error || 'Generate failed');
                              setBookCharImageUrl(json.image_url || '');
                            } catch (e: unknown) {
                              setBookCharError(e instanceof Error ? e.message : 'Generate failed');
                            } finally {
                              const elapsed = Date.now() - startedAt;
                              const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
                              if (remaining > 0) {
                                await new Promise((r) => window.setTimeout(r, remaining));
                              }
                              setBookCharGenerating(false);
                            }
                          }}
                          className="w-full bg-pink-950 hover:bg-pink-900 disabled:opacity-50 text-white px-5 py-3 rounded-full font-medium transition inline-flex items-center justify-center gap-2"
                        >
                          <Sparkles className="h-4 w-4" />
                          {bookCharGenerating
                            ? 'Generating portrait…'
                            : `Generate portrait of ${selectedCharName || 'character'}`}
                        </button>
                        {bookCharGenerating && (
                          <div className="mt-2 text-xs text-center text-pink-950/60">This may take up to a minute…</div>
                        )}
                        {bookCharImageUrl && !bookCharGenerating && (
                          <PortraitCard
                            imageUrl={bookCharImageUrl}
                            altText={`Portrait of ${selectedCharName}`}
                            filename={`${selectedCharName.replace(/\s+/g, '-').toLowerCase()}-portrait.jpg`}
                          />
                        )}
                        {bookCharError && !bookCharGenerating && (
                          <div className="mt-2 text-xs text-red-700">
                            <ErrorWithSupport message={bookCharError} />
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="mt-2 text-sm text-pink-950/60">Prepare a book to see characters here.</div>
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
                  Type the character name exactly as it appears in the book. We'll search the text and add them to this page.
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

                        setCastLoading(true);
                        const r2 = await fetch(`/api/characters?book_id=${encodeURIComponent(selectedBookId)}`, { cache: 'no-store' });
                        const j2 = await r2.json();
                        if (r2.ok && j2?.success && Array.isArray(j2.characters)) {
                          setCast(
                            j2.characters
                              .map((c: any) => ({
                                character_id: String(c.character_id || ''),
                                character_name: String(c.character_name || ''),
                              }))
                              .filter((c: any) => c.character_id && c.character_name),
                          );
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
              <h2 className="text-2xl md:text-3xl font-semibold text-pink-950">Create a tasteful portrait prompt in 30 seconds</h2>
              <p className="mt-3 text-pink-950/70 max-w-xl">
                Use a guided form (hair, eyes, era, clothing) to generate a clean prompt. Your prompt is kept on this page for easy reuse.
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
                    disabled={!customPrompt.trim() || customGenerating}
                    onClick={async () => {
                      const prompt = customPrompt.trim();
                      if (!prompt || customGenerating) return;
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
                          }),
                        });
                        const json = await res.json();
                        if (!res.ok || !json?.success) throw new Error(json?.error || 'Generate failed');
                        setCustomImageUrl(json.image_url || '');
                      } catch (e: unknown) {
                        setCustomOut(e instanceof Error ? e.message : 'Generate failed');
                      } finally {
                        const elapsed = Date.now() - startedAt;
                        const remaining = MIN_GENERATE_SPINNER_MS - elapsed;
                        if (remaining > 0) {
                          await new Promise((r) => window.setTimeout(r, remaining));
                        }
                        setCustomGenerating(false);
                      }
                    }}
                    className="bg-pink-950 hover:bg-pink-900 disabled:opacity-50 text-white px-5 py-3 rounded-full font-medium transition inline-flex items-center gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    {customGenerating ? 'Generating…' : 'Generate'}
                  </button>
                </div>

                {customGenerating && (
                  <div className="rounded-2xl border border-pink-200 bg-white/60 p-4 text-center text-sm text-pink-950/70">
                    Generating portrait… this may take up to a minute.
                  </div>
                )}
                {customImageUrl && !customGenerating && (
                  <PortraitCard
                    imageUrl={customImageUrl}
                    altText="Generated portrait"
                    filename={`${(customName || 'portrait').replace(/\s+/g, '-').toLowerCase()}-portrait.jpg`}
                  />
                )}
                {customOut && !customGenerating && (
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

      <footer className="border-t border-pink-200/60 bg-white/50">
        <div className="mx-auto w-full max-w-6xl px-4 md:px-16 lg:px-24 xl:px-32 py-10 flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
          <div className="text-pink-950 font-semibold">{BRAND_NAME}</div>
          <div className="text-pink-950/70 text-xs text-center md:text-right">
            <span className="block md:inline">Quotes-first extraction · Literary portraits</span>
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
