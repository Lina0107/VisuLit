'use client';

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { BRAND_NAME } from '@/lib/brand';
import { GALLERY_ITEMS, type GalleryItem } from '@/lib/gallery-manifest';

function GallerySlide({ item, index, visible }: { item: GalleryItem; index: number; visible: boolean }) {
  const [failed, setFailed] = React.useState(false);
  const title = item.character.trim() || `Portrait ${index + 1}`;
  const subtitle = item.book.trim();

  return (
    <figure
      className={`col-start-1 row-start-1 w-full transition-opacity duration-500 ease-out ${
        visible ? 'z-10 opacity-100' : 'z-0 opacity-0 pointer-events-none'
      }`}
      aria-hidden={!visible}
    >
      <div className="overflow-hidden rounded-3xl border border-pink-200 bg-white shadow-[0_20px_50px_rgba(120,60,90,0.12)] ring-1 ring-pink-100/80">
        <div className="relative aspect-[3/4] w-full bg-gradient-to-b from-pink-50/90 to-white">
          {!failed ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.imageSrc}
              alt={title}
              className="h-full w-full object-cover"
              loading={visible ? 'eager' : 'lazy'}
              decoding="async"
              onError={() => setFailed(true)}
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-3 text-center text-xs text-pink-900/55">
              <span className="font-medium text-pink-900/70">Add image</span>
              <code className="rounded-lg bg-pink-50 px-2 py-1 text-[10px] text-pink-950/80">
                public/gallery/{String(index + 1).padStart(2, '0')}.jpg
              </code>
            </div>
          )}
        </div>
        <figcaption className="border-t border-pink-100 bg-white/90 px-5 py-4 text-center">
          <div className="text-lg font-semibold tracking-tight text-pink-950 sm:text-xl">{title}</div>
          {subtitle ? (
            <div className="mt-1 text-sm text-pink-950/65">{subtitle}</div>
          ) : null}
        </figcaption>
      </div>
    </figure>
  );
}

export function ExamplesGallery() {
  const [index, setIndex] = React.useState(0);
  const total = GALLERY_ITEMS.length;
  const sectionRef = React.useRef<HTMLElement>(null);

  const go = React.useCallback(
    (delta: number) => {
      setIndex((i) => (i + delta + total) % total);
    },
    [total],
  );

  React.useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        go(-1);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        go(1);
      }
    };
    el.addEventListener('keydown', onKey);
    return () => el.removeEventListener('keydown', onKey);
  }, [go]);

  return (
    <section
      ref={sectionRef}
      id="gallery"
      tabIndex={0}
      className="mx-auto w-full max-w-6xl scroll-mt-24 px-4 pb-20 outline-none md:px-16 lg:px-24 xl:px-32"
      aria-labelledby="gallery-heading"
    >
      <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
        <h2 id="gallery-heading" className="text-2xl font-semibold text-pink-950 md:text-3xl">
          Portrait gallery
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-pink-950/75">
          Photoreal examples from {BRAND_NAME} — the same quote-first flow: prepare a book, pick a character, generate.
        </p>

        <div className="relative mt-8 md:mt-10">
          <div className="pointer-events-none absolute inset-0 -z-10 mx-auto max-w-lg rounded-full bg-pink-200/25 blur-3xl" />

          <div className="flex items-center justify-center gap-3 sm:gap-6">
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="Previous portrait"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-pink-200 bg-white/90 text-pink-950 shadow-sm transition hover:border-pink-300 hover:bg-pink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-400 sm:h-12 sm:w-12"
            >
              <ChevronLeft className="h-5 w-5 sm:h-6 sm:w-6" />
            </button>

            <div className="grid w-full max-w-[min(100%,20rem)] sm:max-w-xs md:max-w-sm [&>*]:col-start-1 [&>*]:row-start-1">
              {GALLERY_ITEMS.map((item, i) => (
                <GallerySlide key={item.id} item={item} index={i} visible={i === index} />
              ))}
            </div>

            <button
              type="button"
              onClick={() => go(1)}
              aria-label="Next portrait"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-pink-200 bg-white/90 text-pink-950 shadow-sm transition hover:border-pink-300 hover:bg-pink-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-400 sm:h-12 sm:w-12"
            >
              <ChevronRight className="h-5 w-5 sm:h-6 sm:w-6" />
            </button>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            {GALLERY_ITEMS.map((item, i) => (
              <button
                key={item.id}
                type="button"
                aria-label={`Show ${item.character}`}
                aria-current={i === index ? 'true' : undefined}
                onClick={() => setIndex(i)}
                className={`h-2 rounded-full transition-all duration-300 ${
                  i === index ? 'w-7 bg-pink-800' : 'w-2 bg-pink-300/80 hover:bg-pink-400'
                }`}
              />
            ))}
          </div>

          <p className="mt-3 text-center text-xs font-medium text-pink-950/50">
            {GALLERY_ITEMS[index]?.character}
            <span className="mx-1.5 text-pink-300">·</span>
            {index + 1} of {total}
          </p>
        </div>
      </div>
    </section>
  );
}
