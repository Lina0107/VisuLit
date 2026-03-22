## Product Type and Positioning

- **Type of product**: Web platform (Flask‑based web app, future SaaS‑ready).
- **Product name**: **VisuLit** (Next.js UI + Flask API).
- **User support**: public support address `hello@visulit.com` (override in production via `NEXT_PUBLIC_SUPPORT_EMAIL` in the frontend build).
- **Target audience**:
  - Avid readers of classic literature (primarily women 18–40) who emotionally привязаны к героям книг.
  - Bookstagram / BookTok creators and bloggers, которые хотят визуальный контент по книгам.
  - Writers and fanfic authors who need visual references for their own characters.
- **Core problem**:
  - AI image models often hallucinate or ignore the actual text of a book.
  - Readers rarely see characters “drawn” именно по авторским описаниям (цитатам).
  - Для собственных персонажей людям сложно собрать ясное, структурированное текстовое описание.
- **Core value**:
  - Extract main characters and appearance‑focused quotes directly from public‑domain books.
  - Build clean, focused English prompts that stay close to the text.
  - Let users gently construct prompts for their own characters without needing to “speak AI language”.
- **Primary market**: US / global English‑speaking market.
- **Languages** (current / planned):
  - Current UI: English.
  - Planned: additional locale wrappers for RU and others, but prompts and book processing stay in English for now.
- **Local considerations**:
  - Payment and auth are not yet implemented, but design should assume:
    - Stripe (USD) and possibly regional cards later.
    - Social auth via Google / Apple for US users.

---

## Core Features

### 1. Book‑Based Character Extraction
- **What it does**:
  - Imports public‑domain books via Gutendex.
  - Detects candidate character names, clusters aliases, and selects main characters with GPT.
  - Extracts appearance‑focused quotes and context evidence.
- **Example use**:
  - A US reader selects “Pride and Prejudice”, hits **Prepare book**, and sees Elizabeth Bennet, Mr Darcy and others with supporting quotes.
- **Value**:
  - Trustworthy, text‑grounded character list.
  - Saves hours vs. manual scrolling and highlighting.

### 2. Appearance Quotes Discovery
- **What it does**:
  - Scans the full book text, segments it into sentences, finds windows around character names.
  - Filters only appearance‑relevant snippets using curated keyword sets and GPT re‑ranking.
- **Example use**:
  - A BookTok creator wants to describe Jo March’s look; the app surfaces 2–6 short quotes about her hair, clothes, and posture.
- **Value**:
  - “Evidence‑based” visuals; reduces hallucination risk when later feeding prompts to image models.

### 3. Prompt Builder from Book Quotes
- **What it does**:
  - Takes a character + their appearance quotes and constructs a compact English prompt for image generation (without extra GPT calls).
- **Example use**:
  - User clicks a main character; the app auto‑fills a hidden or visible prompt (e.g. “Portrait of Jo March from ‘Little Women’…”) ready to be sent to Nano Banana or any model.
- **Value**:
  - Bridges “raw literary text” and “model‑friendly prompt” without extra cost.

### 4. Gentle Custom Character Builder
- **What it does**:
  - Provides a guided form for custom characters: name, age, era, vibe, hair, eyes, build, clothing, extra notes.
  - Builds a clean English prompt from those fields.
- **Example use**:
  - An indie romance writer describes her own heroine (modern US city, warm & kind, soft curls, linen dress); the platform assembles a prompt she can reuse in any AI editor.
- **Value**:
  - Lowers barrier for non‑technical users; no need to know prompt jargon.

### 5. Per‑User Character History
- **What it does**:
  - Saves each preview (book‑based or custom) as a history record tied to a user cookie.
  - Shows recent characters on the landing and inside both flows.
- **Example use**:
  - A returning reader instantly sees recently explored characters and prompts; can click to reuse them in the custom flow.
- **Value**:
  - Continuity and “workspace” feeling; encourages repeated use and experimentation.

### 6. Future: Image Generation Integration (Nano Banana or similar)
- **What it will do**:
  - Use existing prompt builders to call an external image API.
  - Store prompt + seed + resulting image URL in history for reproducibility.
- **Value**:
  - Turns the current text‑analysis tool into a full “from book to portrait” experience.

---

## Key Pages and Screens

### 1. Landing Page (Home)
- **Content**:
  - Brand area (logo + name + short tagline).
  - Hero section with two primary CTAs:
    - “Find characters” (book‑based flow).
    - “Create your own character” (custom flow).
  - “Product in action” teaser: example character cards (Darcy, Jo March, Heathcliff, etc.).
  - “Popular books” strip driven from `books.json`.
  - User’s recent characters history.
- **Marketing aspects**:
  - Clear one‑sentence value proposition.
  - Social proof section (“Product in action”) that can later be filled with real examples.
  - SEO: title/description around “AI character visualizer from books”, “book character portraits”, “literary character prompts”.
- **Technology**:
  - Static HTML + JS.
  - Smooth view switching between landing/book/custom (no full page reload).

### 2. Book Flow Screen
- **Content**:
  - Mode selector: Curated / All Gutenberg.
  - Search input, book dropdown.
  - Controls: “How many main characters” (12/18/24), “Overwrite cached characters”.
  - Prepare status, progress bar, phase messages.
  - Main characters dropdown.
  - Quotes & prompt panel with appearance + evidence quotes, optional manual prompt, mock preview output, user history.
- **Marketing aspects**:
  - Subcopy explains that preparation runs once and is cached.
  - Microcopy reinforces that this tool stays close to the book text (no heavy hallucinations).
- **Technology**:
  - Frontend calls:
    - `GET /api/books`
    - `POST /api/prepare_book`
    - `GET /api/characters`
    - `POST /api/generate` (mock stage).
  - Animated progress bar, optimistic UI.

### 3. Custom Character Screen
- **Content**:
  - Guided form: name, age, era, vibe, hair, eyes, skin, build, clothing, extra notes.
  - “Build prompt” button.
  - Prompt textarea + mock preview + history.
- **Marketing aspects**:
  - Copy emphasizes gentle, tasteful, book‑inspired aesthetic (no need to over‑specify or sexualize characters).
  - Reinforces that this is a tool both for readers and writers.
- **Technology**:
  - Pure JS prompt building, no extra GPT.
  - `POST /api/generate` called with `source_type="custom"` to log history.

### 4. (Future) Dedicated History / Library Page
- **Purpose**:
  - Show all past characters, filter by source type (book/custom), search by name/book.
  - Quick actions: “Open in book flow”, “Open in custom flow”, “Copy prompt”.
- **Marketing aspects**:
  - Feels like a personal gallery / deck of characters.

### 5. (Future) About / How It Works / FAQ
- **Purpose**:
  - Explain pipeline in human terms.
  - Cover safety / limitations (“we rely on public domain texts”, “no copyrighted IP”).
  - Boost trust and SEO.

---

## Marketing and Growth

### Calls to Action (CTAs)

- **Primary CTAs**:
  - “Find characters” (hero button).
  - “Create your own character”.
- **Secondary CTAs**:
  - “Prepare book” inside book flow.
  - “Build prompt” and “Preview image (mock)” in custom flow.
  - Future: “Generate portrait”, “Save to collection”, “Share”.

### Social Proof and Content

- **Social proof (planned)**:
  - Real examples of text → portrait (once image generation is online).
  - Short case stories from readers (“I finally saw Jo March the way Alcott wrote her”).
  - Logos or mentions if integrated with book clubs / reading apps.

### SEO Strategy (initial)

- **Core keywords (EN)**:
  - book character visualizer, AI character from book,
  - book character image generator,
  - literary character portrait,
  - book‑based AI portraits.
- **On‑page**:
  - Proper `<title>` and meta description per view (later via templating).
  - Semantic headings (H1 for hero, H2 for sections).
  - Copy that naturally includes book/character phrases.

### Localization and Region

- **Region focus**: US / global English‑speaking readers.
- **Localization**:
  - English UI and prompts by default.
  - The pipeline is independent of region (works with any public‑domain English text).
  - Later: optional Russian interface for CIS users, but prompts remain in English for AI.

### Integrations (future)

- Payment: Stripe, Apple Pay / Google Pay for premium features (extra generations, higher limits).
- Social: share links to Twitter/X, Instagram, Pinterest, BookTok.
- Auth: OAuth via Google / Apple ID for simple sign‑in.

---

## Technology Stack

- **Frontend**:
  - HTML templates (`index.html`) served by Flask.
  - Vanilla JavaScript (fetch, DOM manipulation) for API calls and UI state.
  - Custom CSS (no heavy frameworks) tailored to the bookish dark UI.
- **Backend**:
  - Python + Flask.
  - Data storage in JSON files under `data/`:
    - `books.json`, `curated_books.json`, `characters.json`, `usage.json`, `history.json`.
  - `import_books.py` for Gutendex import.
- **AI / NLP**:
  - AITunnel API (OpenAI‑compatible) for:
    - clustering and main‑character selection,
    - re‑ranking appearance quotes.
  - Local regex‑based heuristics for name detection and appearance keyword filtering.
- **Additional tools (planned)**:
  - Background workers for long‑running `prepare_book` tasks.
  - Swappable integration for Nano Banana or other image APIs.
  - Optional persistent DB (PostgreSQL) if JSON files become a bottleneck.

---

## Design Guidelines

- **Inspiration**:
  - BookVision‑style dark premium aesthetic: literary, slightly cinematic, but not “gaming” sci‑fi.
  - Soft, rounded shapes with subtle glows instead of harsh neon.
- **Color palette**:
  - Background: deep navy / ink (`#020617` / `#020617` with gradients).
  - Cards: semi‑transparent dark panels with soft borders.
  - Accents: warm gold (`#fbbf24`), soft green (`#22c55e`), cool cyan for secondary highlights.
  - Text: off‑white for primary (`#e5e7eb`), muted gray for secondary.
- **Tone**:
  - Warm, book‑lover friendly, slightly poetic, not technical.
  - Feminine‑leaning but gender‑neutral: smooth shapes, gentle motion, soft colors.
- **Interaction**:
  - Subtle hover animations on cards and buttons (small lift + shadow).
  - Animated progress bar for book preparation.
  - Smooth section transitions (no page reload).
- **Responsiveness**:
  - Single‑column layout on mobile for all flows.
  - Controls stay large and thumb‑friendly.

