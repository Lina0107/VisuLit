import { GALLERY_ITEMS } from '@/lib/gallery-manifest';

const FEATURED = GALLERY_ITEMS.filter((item) => item.quote);

/**
 * First-screen proof: the portraits themselves, each with the line from the
 * book it was built on. A swipeable strip on phones, a row on wider screens.
 */
export function HeroShowcase({ onPick }: { onPick: () => void }) {
  return (
    <div className="mx-auto mt-10 w-full max-w-6xl md:mt-14 md:px-8">
      <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-4 [scrollbar-width:none] md:grid md:grid-cols-5 md:gap-4 md:overflow-visible md:px-0 md:pb-0 [&::-webkit-scrollbar]:hidden">
        {FEATURED.map((item, i) => (
          <li
            key={item.id}
            className={`w-[68vw] max-w-[280px] shrink-0 snap-center md:w-auto md:max-w-none ${
              i % 2 === 1 ? 'md:translate-y-6' : ''
            }`}
          >
            <button
              type="button"
              onClick={onPick}
              aria-label={`${item.character}, ${item.book}. Make your own portrait`}
              className="group relative block aspect-[3/4.3] w-full overflow-hidden rounded-3xl bg-pink-100 text-left shadow-[0_18px_40px_rgba(120,60,90,0.18)] ring-1 ring-pink-200/70 transition duration-300 hover:-translate-y-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-500 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={item.imageSrc}
                alt={`Portrait of ${item.character}`}
                className="h-full w-full object-cover"
                loading={i < 2 ? 'eager' : 'lazy'}
                decoding="async"
              />
              <span className="absolute inset-x-0 bottom-0 flex flex-col gap-2 bg-gradient-to-t from-[#2a0b1c]/95 via-[#2a0b1c]/70 to-transparent px-4 pb-4 pt-16 text-white">
                <span className="font-serif text-[15px] italic leading-snug text-pink-50 md:text-sm lg:text-[15px]">
                  &ldquo;{item.quote}&rdquo;
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider text-pink-100/90">
                  {item.character}
                  <span className="block font-normal normal-case tracking-normal text-pink-100/65">{item.book}</span>
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
