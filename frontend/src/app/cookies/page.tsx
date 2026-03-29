import type { Metadata } from 'next';
import Link from 'next/link';
import { BRAND_NAME } from '@/lib/brand';
import { CookiePreferencesPanel } from '@/components/cookie-preferences-panel';

export const metadata: Metadata = {
  title: `Cookie policy · ${BRAND_NAME}`,
  description: `How ${BRAND_NAME} uses cookies and similar technologies.`,
};

export default function CookiePolicyPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-pink-50/80 via-white to-violet-50/40 text-pink-950">
      <div className="mx-auto max-w-2xl px-4 py-12 md:py-16">
        <p className="text-sm text-pink-900/60">
          <Link href="/" className="font-medium text-pink-900 underline underline-offset-2 hover:text-pink-700">
            ← Back to {BRAND_NAME}
          </Link>
        </p>
        <h1 className="mt-6 text-3xl font-semibold tracking-tight text-pink-950">Cookie policy</h1>
        <p className="mt-2 text-sm text-pink-950/70">Last updated: March 2026</p>

        <div className="mt-10 space-y-8 text-sm leading-relaxed text-pink-950/85">
          <section>
            <h2 className="text-base font-semibold text-pink-950">What this site stores</h2>
            <p className="mt-2">
              {BRAND_NAME} is a web app that turns public-domain literary quotes into portrait prompts. Storing
              book text and metadata on our servers is <strong>not</strong> the same as storing personal data
              about you — it is fixed catalog content, similar to a digital library.
            </p>
            <p className="mt-2">
              We do store a small amount of information <strong>about your use of the app</strong> so it can
              function: for example a first-party technical cookie with a random ID (to apply daily free
              generation limits) and, if you allow it, analytics that help us see which features are used.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-pink-950">Essential cookies &amp; similar storage</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                <strong>user_id (cookie)</strong> — random identifier set by our server when you generate a
                portrait, used with server-side counters so free daily limits work. These are first-party and
                considered strictly necessary for the service you request.
              </li>
              <li>
                <strong>visulit_cookie_consent (browser local storage)</strong> — remembers whether you chose
                “Essential only” or “Accept analytics” so we do not show the banner on every visit.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-pink-950">Analytics (optional)</h2>
            <p className="mt-2">
              If you click <strong>Accept analytics</strong>, we load <strong>Google Analytics 4</strong> to
              collect aggregated usage statistics (pages, events). We do not load GA until you opt in. Google’s
              privacy terms apply to how they process that data.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-pink-950">AI providers</h2>
            <p className="mt-2">
              When you generate a portrait, text prompts are sent to our AI providers to produce images and
              (where applicable) text. That is not a “cookie” but it is important to know: those requests leave
              your browser or our server and are processed by third-party infrastructure. See our forthcoming
              privacy policy for a fuller list of processors.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-pink-950">Server-side data</h2>
            <p className="mt-2">
              Our backend may keep short summaries of generations (e.g. prompt text and image URL) keyed to your
              technical ID for in-app history and support. This is separate from public book files.
            </p>
          </section>

          <section id="manage">
            <h2 className="text-base font-semibold text-pink-950">Change your choice</h2>
            <p className="mt-2">
              You can switch between essential-only mode and analytics at any time. If you turn analytics off,
              we reload the page so Google scripts are no longer active in your session.
            </p>
            <CookiePreferencesPanel />
          </section>
        </div>
      </div>
    </div>
  );
}
