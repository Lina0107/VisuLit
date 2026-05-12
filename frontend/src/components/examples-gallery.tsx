'use client';

import React from 'react';
import { BRAND_NAME } from '@/lib/brand';
import { GALLERY_ITEMS, type GalleryItem } from '@/lib/gallery-manifest';

function GalleryTile({ item, index }: { item: GalleryItem; index: number }) {
  const [failed, setFailed] = React.useState(false);

  const title = item.character.trim() || `Portrait ${index + 1}`;
  const subtitle = item.book.trim();

  return (
    <figure className="overflow-hidden rounded-2xl border border-pink-200 bg-white/70 shadow-sm">
      <div className="relative aspect-[3/4] w-full bg-gradient-to-b from-pink-50/80 to-white">
        {!failed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.imageSrc}
            alt={title}
            className="h-full w-full object-cover"
            loading="lazy"
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
      <figcaption className="border-t border-pink-100 px-3 py-2.5">
        <div className="text-sm font-semibold text-pink-950">{title}</div>
        {subtitle ? (
          <div className="mt-0.5 text-xs text-pink-950/65">{subtitle}</div>
        ) : null}
      </figcaption>
    </figure>
  );
}

export function ExamplesGallery() {
  return (
    <section
      id="gallery"
      className="mx-auto w-full max-w-6xl scroll-mt-24 px-4 pb-20 md:px-16 lg:px-24 xl:px-32"
      aria-labelledby="gallery-heading"
    >
      <div className="rounded-3xl border border-pink-200 bg-white/70 p-6 md:p-10 shadow-[0_18px_50px_rgba(120,60,90,0.10)]">
        <h2 id="gallery-heading" className="text-2xl font-semibold text-pink-950 md:text-3xl">
          Portrait gallery
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-pink-950/75">
          Photoreal examples from {BRAND_NAME} — the same quote-first flow: prepare a book, pick a character, generate.
        </p>

        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5">
          {GALLERY_ITEMS.map((item, index) => (
            <GalleryTile key={item.id} item={item} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
