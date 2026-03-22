# app.py
from flask import Flask, request, jsonify, make_response, render_template
from flask_cors import CORS
import json
import os
import hashlib
from datetime import datetime, timezone
import requests
import uuid
import re
import time

from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# -------------------- setup --------------------
_DOTENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
# Force-load dotenv from the project folder and override any existing env vars.
# This prevents stale AITUNNEL_* values from being kept in the running process.
load_dotenv(dotenv_path=_DOTENV_PATH, override=True)

app = Flask(__name__, template_folder="templates")
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

DATA_DIR = "data"
BOOKS_FILE = os.path.join(DATA_DIR, "books.json")
CURATED_FILE = os.path.join(DATA_DIR, "curated_books.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
USAGE_FILE = os.path.join(DATA_DIR, "usage.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

DAILY_FREE_LIMIT = 3

AITUNNEL_API_KEY = os.getenv("AITUNNEL_API_KEY", "").strip()
AITUNNEL_BASE_URL = os.getenv("AITUNNEL_BASE_URL", "https://api.aitunnel.ru/v1").strip()
AITUNNEL_MODEL = os.getenv("AITUNNEL_MODEL", "gpt-4o-mini").strip()

os.makedirs(DATA_DIR, exist_ok=True)


# -------------------- json helpers --------------------
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_book_by_id(book_id: str):
    """Cheap helper: load a single book dict by book_id."""
    if not book_id:
        return None
    books = load_json(BOOKS_FILE, [])
    return next((b for b in books if b.get("book_id") == book_id), None)


def append_history_record(user_id: str, record: dict, per_user_limit: int = 40):
    """
    Append a generation record to history.json for a given user.
    Keeps only the latest `per_user_limit` records per user to avoid unbounded growth.
    """
    items = load_json(HISTORY_FILE, [])
    if not isinstance(items, list):
        items = []

    rec = dict(record)
    rec["user_id"] = user_id
    rec.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    items.append(rec)

    # trim per user
    by_user = {}
    for r in items:
        uid = r.get("user_id")
        if not uid:
            continue
        by_user.setdefault(uid, []).append(r)

    trimmed = []
    for uid, recs in by_user.items():
        recs_sorted = sorted(
            recs,
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )
        trimmed.extend(recs_sorted[:per_user_limit])

    save_json(HISTORY_FILE, trimmed)


def init_files():
    for path, default in [
        (BOOKS_FILE, []),
        (CURATED_FILE, []),
        (CHARACTERS_FILE, []),
        (USAGE_FILE, {}),
        (HISTORY_FILE, []),
    ]:
        if not os.path.exists(path):
            save_json(path, default)


init_files()


# -------------------- usage / cookies --------------------
def get_user_id(req):
    uid = req.cookies.get("user_id")
    if uid:
        return uid
    ip = req.remote_addr or "unknown"
    return hashlib.md5(ip.encode("utf-8")).hexdigest()


def today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_and_update_usage(user_id):
    usage = load_json(USAGE_FILE, {})
    t = today_key()

    if t not in usage:
        usage[t] = {}

    used = int(usage[t].get(user_id, 0))
    if used >= DAILY_FREE_LIMIT:
        return False, 0

    used += 1
    usage[t][user_id] = used
    save_json(USAGE_FILE, usage)

    return True, max(0, DAILY_FREE_LIMIT - used)


def get_remaining_today(user_id):
    """Return remaining daily free generations without incrementing usage."""
    usage = load_json(USAGE_FILE, {})
    t = today_key()
    if t not in usage:
        return DAILY_FREE_LIMIT
    used = int(usage[t].get(user_id, 0))
    return max(0, DAILY_FREE_LIMIT - used)


# -------------------- gutenberg cleaning --------------------
def clean_gutenberg_text(text: str) -> str:
    if not text:
        return ""
    start_markers = [
        "*** START OF THIS PROJECT GUTENBERG",
        "*** START OF THE PROJECT GUTENBERG",
        "START OF THIS PROJECT GUTENBERG",
    ]
    end_markers = [
        "*** END OF THIS PROJECT GUTENBERG",
        "*** END OF THE PROJECT GUTENBERG",
        "END OF THIS PROJECT GUTENBERG",
    ]

    for m in start_markers:
        if m in text:
            text = text.split(m, 1)[-1]
            break
    for m in end_markers:
        if m in text:
            text = text.split(m, 1)[0]
            break

    return text


# -------------------- name normalization / clustering --------------------
TITLE_CANON = {
    "mr": "Mr.", "mrs": "Mrs.", "miss": "Miss", "ms": "Ms.", "dr": "Dr.",
    "prof": "Prof.", "capt": "Capt.", "captain": "Captain",
    "col": "Col.", "colonel": "Colonel", "maj": "Maj.", "major": "Major",
    "gen": "Gen.", "general": "General", "lt": "Lt.", "lieutenant": "Lieutenant",
    "rev": "Rev.", "reverend": "Rev.", "sir": "Sir", "lady": "Lady", "lord": "Lord",
}

LEADING_JUNK = {"while", "although", "even", "and", "but", "then", "so", "because"}
SINGLE_JUNK = {
    "said", "says", "she", "he", "him", "her", "they", "them", "you", "i", "we",
    "chapter", "volume", "book", "part", "act", "scene",
    "project", "gutenberg", "copyright", "license",
}
PHRASE_JUNK = {
    "Project Gutenberg", "United States", "United Kingdom", "Great Britain", "New York"
}


def normalize_name(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    s = re.sub(r"^[\"'“”‘’\(\)\[\]\{\}]+|[\"'“”‘’\(\)\[\]\{\}]+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)

    if len(s) < 2:
        return ""

    parts = s.split(" ")

    if parts and parts[0].lower() in LEADING_JUNK:
        parts = parts[1:]
    if not parts:
        return ""

    if len(parts) == 1 and parts[0].lower().strip(".") in SINGLE_JUNK:
        return ""

    first = parts[0].rstrip(".").lower()
    if first in TITLE_CANON and len(parts) >= 2:
        parts[0] = TITLE_CANON[first]
        parts[1] = parts[1][:1].upper() + parts[1][1:]
        s = " ".join(parts)
        return s

    def cap_token(t):
        if t.lower() in {"de", "von", "van", "da", "di", "del", "la", "le"}:
            return t.lower()
        return t[:1].upper() + t[1:] if t else t

    parts = [cap_token(p) for p in parts]
    s = " ".join(parts)

    if s in PHRASE_JUNK:
        return ""
    return s


def is_title_form(name: str) -> bool:
    return bool(re.match(r"^(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sir|Lady|Lord|Rev\.|Captain|Colonel|Major|General|Lt\.)\s+", name))


def last_name_of(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return parts[-1]
    return ""


def cluster_candidates(names):
    normed = []
    seen = set()
    for n in names:
        nn = normalize_name(n)
        if not nn:
            continue
        key = nn.lower()
        if key in seen:
            continue
        seen.add(key)
        normed.append(nn)

    buckets = {}
    singles = []
    for n in normed:
        ln = last_name_of(n)
        if ln:
            buckets.setdefault(ln.lower(), []).append(n)
        else:
            singles.append(n)

    clusters = []
    for _, items in buckets.items():
        items = sorted(items, key=lambda x: (0 if is_title_form(x) else 1, -len(x), x))
        clusters.append(items)

    for n in singles:
        clusters.append([n])

    return clusters


# -------------------- fast candidate extraction --------------------
VERBS = r"(said|replied|asked|exclaimed|cried|answered|murmured|whispered|shouted|remarked|observed|continued|added)"
ACTION_VERBS = r"(turned|looked|smiled|nodded|shook|frowned|laughed|stopped|walked|came|went|ran|sat|stood)"

FAMILY_PATTERNS = re.compile(
    r"\b(her|his|their|the)\s+(mother|father|sister|brother|aunt|uncle|daughter|son|wife|husband|cousin|niece|nephew)\b",
    re.IGNORECASE
)
RELATION_CONTEXT = re.compile(
    r"\b([A-Z][a-z]{2,})\b[^.]{0,40}?\b(mother|father|sister|brother|aunt|uncle|daughter|son|wife|husband|cousin)\b",
    re.IGNORECASE
)

def extract_candidates_from_text(text: str, book_title: str, max_len=260000):
    text = clean_gutenberg_text(text)
    if len(text) > max_len:
        text = text[:max_len]

    candidates = set()

    # full names
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b", text):
        candidates.add(f"{m.group(1)} {m.group(2)}")

    # titled names
    for m in re.finditer(r"\b(Mr|Mrs|Miss|Ms|Dr|Sir|Lady|Lord|Mme|Mlle)\.?\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", text):
        candidates.add(f"{m.group(1)} {m.group(2)}")

    # speech verbs
    for m in re.finditer(rf"\b([A-Z][a-z]{{2,}})\b\s+{VERBS}\b", text):
        candidates.add(m.group(1))
    for m in re.finditer(rf"\b{VERBS}\b\s+([A-Z][a-z]{{2,}})\b", text):
        candidates.add(m.group(1))

    # action verbs
    for m in re.finditer(rf"\b([A-Z][a-z]{{2,}})\b\s+{ACTION_VERBS}\b", text):
        candidates.add(m.group(1))

    # names near family relation words — helps find parents, siblings, spouses
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\b", text):
        name = m.group(1)
        ctx_start = max(0, m.start() - 80)
        ctx_end = min(len(text), m.end() + 80)
        ctx = text[ctx_start:ctx_end].lower()
        if any(rel in ctx for rel in ("mother", "father", "sister", "brother", "wife", "husband",
                                       "daughter", "son", "aunt", "uncle", "cousin")):
            candidates.add(name)

    # Always include the character named in the book title (e.g. "Dracula", "Emma", "Heidi")
    # Search the FULL text (not just the slice) so Gothic/epistolary novels where the
    # title character appears mostly in the second half still get detected.
    title_name = None
    raw_title = (book_title or "").strip()
    # Handle single word titles AND "The X of Y" → try each capitalised word
    title_words = [w for w in raw_title.split() if len(w) >= 3 and w[0].isupper()
                   and w.lower() not in ("the", "and", "of", "in", "a", "an")]
    for tw in title_words:
        if re.search(rf"\b{re.escape(tw)}\b", text):
            candidates.add(tw)
            if len(tw) >= 4:   # prefer the longer/more distinctive name
                title_name = tw

    out = []
    for c in candidates:
        nn = normalize_name(c)
        if not nn:
            continue
        if nn.lower() in SINGLE_JUNK:
            continue
        out.append(nn)

    # Score on a longer slice so late-appearing characters (e.g. Dracula) are not filtered out
    slice_text = text[:200000]
    scored = []
    for n in out:
        cnt = len(re.findall(rf"\b{re.escape(n)}\b", slice_text))
        # Title-name characters always survive even with low frequency
        if title_name and normalize_name(n) == normalize_name(title_name):
            cnt = max(cnt, 999)
        if cnt >= 2:
            scored.append((n, cnt))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [n for n, _ in scored[:160]]


# -------------------- AITunnel call --------------------
def call_aitunnel(messages, max_tokens=2200, temperature=0.2, json_mode=False):
    if not AITUNNEL_API_KEY:
        raise RuntimeError("AITUNNEL_API_KEY not set in .env")
    url = f"{AITUNNEL_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {AITUNNEL_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": AITUNNEL_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def _strip_newlines_inside_json_strings(s: str) -> str:
    """Replace raw newlines inside JSON string values with space (fixes 'Expecting \",\" delimiter')."""
    out = []
    i = 0
    in_string = False
    escape_next = False
    while i < len(s):
        c = s[i]
        if escape_next:
            out.append(c)
            escape_next = False
            i += 1
            continue
        if c == "\\" and in_string:
            out.append(c)
            escape_next = True
            i += 1
            continue
        if c == '"':
            in_string = not in_string
            out.append(c)
            i += 1
            continue
        if in_string and c in ("\n", "\r"):
            out.append(" ")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _safe_json_from_model(text: str):
    """Parse JSON from model; if broken, sanitize newlines and try json_repair."""
    for raw in (text, None):
        if raw is None:
            start = text.find("{")
            if start == -1:
                break
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            raw = text[start:end]
        candidate = _strip_newlines_inside_json_strings(raw)
        try:
            return json.loads(candidate)
        except Exception:
            pass
        try:
            import json_repair
            return json_repair.loads(candidate)
        except ImportError:
            pass
        except Exception:
            pass
    raise RuntimeError("Model did not return valid JSON")


# -------------------- PREPARE STEP A: main characters --------------------
def prepare_main_characters(book_title: str, full_text: str, raw_candidates, main_limit=12):
    """
    STEP A: Ask GPT for character names + aliases ONLY.
    Short prompt, short response, no JSON truncation.
    Quotes are extracted by code in separate steps.
    """
    clusters = cluster_candidates(raw_candidates)
    clean = clean_gutenberg_text(full_text)

    # Small slice — enough to recognise characters, not pay for huge input
    if len(clean) <= 80000:
        text_slice = clean
    else:
        a = clean[:50000]
        mid_start = max(0, len(clean) // 2 - 15000)
        b = clean[mid_start: mid_start + 30000]
        text_slice = a + "\n\n[MIDDLE]\n\n" + b

    system = "You are a literature analyst. Return ONLY valid JSON. No markdown, no extra text."

    user_obj = {
        "book_title": book_title,
        "clusters": clusters,
        "main_limit": main_limit,
        "text_excerpt": text_slice,
    }

    prompt = (
        "Given: book title, candidate name clusters from the text, and a text excerpt.\n"
        "Task: select up to main_limit characters. USE THE FULL LIMIT when the novel has many important figures.\n"
        "Rules (apply to ANY novel, not just known titles):\n"
        "1. Merge clusters that refer to the same person. Use ONLY names that appear in the provided clusters.\n"
        "2. For every main character, include the people who shape their story:\n"
        "   — Family: parents, siblings, spouses, children (if in clusters and recurring).\n"
        "   — Romance: the character's love interest, spouse, or fiancé(e); if someone is rejected but stays important (e.g. rejected suitor who marries another), include them too.\n"
        "   — Recurring secondary: close friends, mentors, key antagonists, servants or colleagues who appear often.\n"
        "3. Do not drop spouses or romantic partners to make room for minor names. Prefer relationship breadth: e.g. all siblings + their partners over extra walk-on characters.\n"
        "4. If the title names a person (e.g. 'Dracula', 'Emma'), that character must be included.\n"
        "Return STRICT JSON (no markdown):\n"
        "{\"main_characters\": [{\"canonical_name\": \"str\", \"aliases\": [\"str\"]}]}\n"
    )

    content = call_aitunnel(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt + "\n\nINPUT:\n" + json.dumps(user_obj, ensure_ascii=False)},
        ],
        max_tokens=800,
        temperature=0.1,
    )

    obj = _safe_json_from_model(content)
    for ch in obj.get("main_characters", []):
        ch.setdefault("evidence_quotes", [])
        ch.setdefault("appearance_quotes", [])
    return obj


# -------------------- STEP A-b: evidence quotes extracted by code (no GPT) --------------------
def extract_evidence_quotes_from_text(full_text: str, characters: list, max_per_char: int = 4) -> dict:
    """
    Find sentences that clearly mention each character by name/alias.
    100% Python, no GPT, no cost. Quotes always contain the character's name.
    Returns dict: canonical_name -> list[{quote, location}]
    """
    clean = clean_gutenberg_text(full_text)
    total = len(clean)
    sentences = _sentencize(clean)

    result = {}
    for ch in characters:
        name = (ch.get("canonical_name") or "").strip()
        aliases = list(ch.get("aliases") or [])
        if name and name not in aliases:
            aliases = [name] + aliases
        aliases = sorted(set(a.strip() for a in aliases if a.strip()), key=lambda x: -len(x))

        patterns = []
        for a in aliases[:8]:
            p = re.escape(a)
            try:
                patterns.append(re.compile(rf"\b{p}\b", re.IGNORECASE))
            except re.error:
                pass

        # Collect all matching sentences first, then pick spread across the book
        all_matches = []
        seen = set()
        for sent, offset in sentences:
            if not any(p.search(sent) for p in patterns):
                continue
            snippet = re.sub(r"\s+", " ", sent).strip()
            if len(snippet) < 30:
                continue
            # skip chapter headers, diary headings, project-gutenberg artefacts
            sl = snippet.lower()
            if re.match(r"^(chapter|letter|diary|journal|note|appendix|part|book|section)\b", sl):
                continue
            if re.match(r"^(project gutenberg|end of|produced by)", sl):
                continue
            if len(snippet) > 220:
                snippet = snippet[:220].rsplit(" ", 1)[0] + "\u2026"
            key = snippet.lower()
            if key in seen:
                continue
            seen.add(key)
            all_matches.append({"quote": snippet, "location": _book_location(offset, total), "offset": offset})

        # pick up to max_per_char evenly spread across the book
        found = []
        if all_matches:
            step = max(1, len(all_matches) // max_per_char)
            indices = list(range(0, len(all_matches), step))[:max_per_char]
            for i in indices:
                q = all_matches[i]
                found.append({"quote": q["quote"], "location": q["location"]})
        result[name] = found
    return result


# -------------------- PREPARE STEP B: appearance candidates from full text --------------------
APPEARANCE_BODY = [
    "face", "features", "complexion", "countenance", "eyes", "hair", "locks", "brow", "cheek",
    "cheeks", "lips", "mouth", "nose", "chin", "shoulders", "figure", "form", "body",
    "skin", "eyelashes", "eyebrows", "forehead", "jaw", "neck", "waist", "height", "stature"
]
APPEARANCE_ADJ = [
    "handsome", "pretty", "beautiful", "lovely", "plain", "ugly",
    "tall", "short", "slender", "slim", "stout", "thin", "lean", "fat",
    "old", "young", "aged", "middle-aged", "striking", "elegant", "graceful",
    "fine", "delicate", "expressive", "lively", "bright", "dark", "piercing"
]
APPEARANCE_CLOTHES = [
    "dress", "gown", "bonnet", "hat", "cap", "coat", "cloak", "jacket", "waistcoat",
    "boots", "shoes", "gloves", "ribbon", "lace", "uniform", "suit", "trousers", "skirt"
]
APPEARANCE_COLORS = [
    "black", "white", "red", "blue", "green", "brown", "grey", "gray",
    "yellow", "golden", "fair", "dark", "pale", "auburn", "raven", "silvery", "blonde"
]
APPEARANCE_KEYWORDS = APPEARANCE_BODY + APPEARANCE_ADJ + APPEARANCE_CLOTHES + APPEARANCE_COLORS

# Features that indicate a CANONICAL (stable, portrait-worthy) description — not a situational moment
CANONICAL_BODY_FEATURES = [
    "eyes", "hair", "locks", "face", "features", "complexion", "countenance", "figure",
    "form", "stature", "height", "brow", "cheek", "cheeks", "lips", "forehead",
    "skin", "waist", "neck", "jaw"
]

# Patterns that signal a SITUATIONAL description (dirt, mess, etc.) — lower priority
SITUATIONAL_PATTERNS = [
    re.compile(r"\b(mud|muddy|dirty|soiled|torn|untidy|blowzy|dishevelled|disheveled|bedraggled|tangled)\b", re.IGNORECASE),
    re.compile(r"\b(petticoat|petticoats)\b.*\b(mud|dirty|soiled)\b", re.IGNORECASE),
    # Discouraged "momentary" states for portrait descriptions
    re.compile(r"\b(tired|fatigued|sleep|asleep|want sleep|kept in the dark|frets her)\b", re.IGNORECASE),
    re.compile(r"\b(crying|cried|tears|sigh|sighed)\b", re.IGNORECASE),
    re.compile(r"\b(shadow of a smile)\b", re.IGNORECASE),
]


def is_visual_appearance_quote(snippet: str) -> bool:
    """
    Heuristic check: keep only quotes that really describe appearance.
    Uses the same keyword categories as build_appearance_candidates.
    """
    if not snippet:
        return False

    sn_l = snippet.lower()

    # reject almost pure dialogue
    # Austen frequently describes appearance inside quoted speech.
    # Keep a higher threshold to avoid dropping valid portrait-worthy lines.
    quote_chars = sum(1 for c in snippet if c in ('"', "'"))
    if quote_chars > len(snippet) * 0.55:
        return False

    def has_any(words):
        for w in words:
            w = (w or "").strip().lower()
            if not w:
                continue
            pat = rf"\b{re.escape(w)}\b"
            if re.search(pat, sn_l):
                return True
        return False

    has_body = has_any(APPEARANCE_BODY)
    has_adj = has_any(APPEARANCE_ADJ)
    has_clothes = has_any(APPEARANCE_CLOTHES)
    has_color = has_any(APPEARANCE_COLORS)

    # If we have multiple distinct "core" portrait features,
    # accept even when we don't have adjectives/colors.
    # Example: "Her lips are curved and her face beams..." (face+lips only).
    core_keys = ["eyes", "face", "hair", "complexion", "countenance", "lips", "cheek", "brow", "cheeks"]
    core_hits = 0
    for kw in core_keys:
        if re.search(rf"\b{re.escape(kw)}\b", sn_l):
            core_hits += 1
    if core_hits >= 2:
        return True

    score = 0
    if has_body:
        score += 2
    if has_adj:
        score += 1
    if has_clothes:
        score += 2
    if has_color:
        score += 2

    qualifies = (
        (has_body and (has_adj or has_clothes or has_color))
        or (has_clothes and has_color)
        or (has_clothes and has_body)
        or score >= 5
    )

    return qualifies


def quote_describes_another_person(quote: str) -> bool:
    """
    Heuristic: narrator describing someone else's appearance.
    E.g. 'I remember her as slim...', 'she had black hair'.
    Such quotes must not count as THIS character's own appearance.
    """
    if not quote or len(quote) < 20:
        return False
    q = quote.strip()
    # Use IGNORECASE so lowercase 'i' and uppercase 'I' both match
    flags = re.IGNORECASE
    if re.search(r"\bI\s+remember\s+(her|him)\b", q, flags):
        return True
    if re.search(r"\bI\s+(recall|recollect|saw|noticed|thought)\s+(her|him|that\s+she|that\s+he)\b", q, flags):
        return True
    if re.search(r"\b(she|he)\s+had\s+(black|dark|fair|long|short|golden|white|grey|gray|red)\s+(hair|eyes|locks|brows)\b", q, flags):
        return True
    if re.match(r"^(she|he)\s+(was|had|looked|appeared|seemed)\s+", q, flags):
        return True
    return False


def _has_any(sn_l: str, words) -> bool:
    """Check word-boundary presence for a list of keywords."""
    for w in words:
        w = (w or "").strip().lower()
        if not w:
            continue
        if re.search(rf"\b{re.escape(w)}\b", sn_l):
            return True
    return False


def _appearance_groups(quote_text: str) -> dict:
    """
    Categorize an appearance quote for "portrait balance":
    - core: face/eyes/hair (portrait-worthy)
    - body: figure/height/complexion
    - clothes: dress/gown/coat/etc.
    - color: basic colors that influence palette
    """
    sn_l = (quote_text or "").lower()
    core = _has_any(sn_l, ["eyes", "face", "countenance", "complexion", "hair", "locks", "brow", "cheek", "cheeks", "forehead"])
    body = _has_any(sn_l, ["figure", "form", "stature", "height", "neck", "waist", "jaw", "lips", "skin", "complexion", "countenance"])
    clothes = _has_any(sn_l, ["dress", "gown", "coat", "cloak", "jacket", "bonnet", "hat", "uniform", "skirt", "trousers", "boots", "gloves"])
    color = _has_any(sn_l, APPEARANCE_COLORS)
    return {"core": bool(core), "body": bool(body), "clothes": bool(clothes), "color": bool(color)}


def select_appearance_quotes_from_candidates(candidates: list, max_quotes: int = 6) -> list:
    """
    Deterministic quote selection with group coverage.
    This keeps both portrait features (face/eyes/hair) and supporting details (figure/height/clothes/color).
    """
    if not isinstance(candidates, list):
        return []

    selected = []
    flags = {"core": False, "body": False, "clothes": False, "color": False}

    # Candidates are expected to be pre-sorted by canonical_score, same_sentence, etc.
    for c in candidates:
        if not isinstance(c, dict):
            continue
        qt = (c.get("quote") or "").strip()
        if not qt:
            continue
        if not is_visual_appearance_quote(qt):
            continue
        if quote_describes_another_person(qt):
            continue

        g = _appearance_groups(qt)
        helps_missing = (
            (not flags["core"] and g["core"]) or
            (not flags["body"] and g["body"]) or
            (not flags["clothes"] and g["clothes"]) or
            (not flags["color"] and g["color"])
        )

        # Even if we cannot find some groups (e.g. clothes),
        # still allow picking more core/body quotes to keep the portrait useful.
        core_body_already = (flags["core"] and g["core"]) or (flags["body"] and g["body"])
        can_add = helps_missing or core_body_already or all(flags.values())

        if len(selected) < max_quotes and can_add:
            selected.append({
                "quote": qt,
                "location": (c.get("location") or "unknown").strip(),
            })
            for k in flags.keys():
                if g.get(k):
                    flags[k] = True
            if len(selected) >= max_quotes:
                break

    # If we couldn't fill everything, still return what we have.
    return selected[:max_quotes]


def _sentencize(text: str):
    # простая сегментация: нормально для англ. романов
    # (не идеальна, но дешевая и работает)
    parts = re.split(r"(?<=[\.\?\!])\s+(?=[A-Z\"'])", text)
    out = []
    pos = 0
    for p in parts:
        p2 = p.strip()
        if not p2:
            pos += len(p)
            continue
        out.append((p2, pos))
        pos += len(p) + 1
    return out

def _book_location(offset: int, total: int):
    if total <= 0:
        return "unknown"
    r = offset / total
    if r < 0.33:
        return "early"
    if r < 0.66:
        return "middle"
    return "late"

def build_appearance_candidates(full_text: str, characters, max_per_char=28):
    clean = clean_gutenberg_text(full_text)
    total = len(clean)
    sentences = _sentencize(clean)

    # Precompile keyword regexes (use word boundaries to avoid false positives
    # like 'old' in 'would' or 'red' in 'tired')
    def _compile_kw(words):
        outp = []
        for w in words:
            w = (w or "").strip().lower()
            if not w:
                continue
            outp.append(re.compile(rf"\b{re.escape(w)}\b"))
        return outp

    kw_body = _compile_kw(APPEARANCE_BODY)
    kw_adj = _compile_kw(APPEARANCE_ADJ)
    kw_clothes = _compile_kw(APPEARANCE_CLOTHES)
    kw_colors = _compile_kw(APPEARANCE_COLORS)

    result = {}  # canonical_name -> list[{quote, location}]
    for ch in characters:
        name = (ch.get("canonical_name") or "").strip()
        aliases = ch.get("aliases") or []
        aliases = [a for a in aliases if isinstance(a, str) and a.strip()]
        # include canonical itself
        if name and name not in aliases:
            aliases.insert(0, name)

        aliases = [a.strip() for a in aliases]
        aliases = sorted(set(aliases), key=lambda x: (-len(x), x))

        # compile alias patterns with word boundaries to avoid false hits (e.g., "May" in "maybe")
        alias_patterns = []
        for a in aliases[:6]:
            aa = a.lower().strip()
            if not aa:
                continue
            alias_patterns.append(re.compile(rf"\b{re.escape(aa)}\b"))

        found = []
        seen_quotes = set()

        # scan sentences, look for alias mention, then pick window (prev + this + next)
        for i, (sent, offset) in enumerate(sentences):
            lower = sent.lower()
            hit_alias = None
            for p in alias_patterns:
                if p.search(lower):
                    hit_alias = True
                    break
            if not hit_alias:
                continue

            # build window
            window = []
            for j in (i-1, i, i+1):
                if 0 <= j < len(sentences):
                    window.append(sentences[j][0].strip())
            snippet = " ".join(window)
            sn_l = snippet.lower()

            # compute a simple visual score so we keep only really "appearance-heavy" snippets
            score = 0
            has_body   = any(p.search(sn_l) for p in kw_body)
            has_adj    = any(p.search(sn_l) for p in kw_adj)
            has_clothes = any(p.search(sn_l) for p in kw_clothes)
            has_color  = any(p.search(sn_l) for p in kw_colors)

            if has_body:    score += 2
            if has_adj:     score += 1
            if has_clothes: score += 2
            if has_color:   score += 2

            # require at least body/clothes AND one more signal, OR clothes+color together
            qualifies = (
                (has_body and (has_adj or has_clothes or has_color)) or
                (has_clothes and has_color) or
                (has_clothes and has_body) or
                score >= 5
            )
            if not qualifies:
                continue

            # reject snippets that look like pure dialogue (>30% inside quotes)
            quote_chars = sum(1 for c in snippet if c in ('"', '"', '"', "'"))
            if quote_chars > len(snippet) * 0.30:
                continue

            # Prefer: name and visual description in the SAME sentence (less ambiguity)
            sent_lower = sent.lower()
            same_sentence = (
                any(p.search(sent_lower) for p in kw_body) or
                any(p.search(sent_lower) for p in kw_adj) or
                any(p.search(sent_lower) for p in kw_clothes) or
                any(p.search(sent_lower) for p in kw_colors)
            )

            # length limit
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if len(snippet) > 220:
                snippet = snippet[:220].rsplit(" ", 1)[0] + "…"

            if snippet.lower() in seen_quotes:
                continue
            seen_quotes.add(snippet.lower())

            # Score how "canonical" (stable/portrait-worthy) vs situational this snippet is
            sn_l_full = snippet.lower()
            canonical_body_hits = sum(
                1 for kw in CANONICAL_BODY_FEATURES
                if re.search(rf"\b{re.escape(kw)}\b", sn_l_full)
            )
            is_situational = any(p.search(snippet) for p in SITUATIONAL_PATTERNS)
            canonical_score = canonical_body_hits - (3 if is_situational else 0)

            found.append({
                "quote": snippet,
                "location": _book_location(offset, total),
                "same_sentence": same_sentence,
                "canonical_score": canonical_score,
            })

            if len(found) >= max_per_char:
                break

        # Sort: canonical stable features first, then same-sentence hits, then rest
        found.sort(key=lambda x: (
            -x.get("canonical_score", 0),
            not x.get("same_sentence", False),
        ))
        result[name] = found

    return result


# -------------------- PREPARE STEP C: GPT chooses best appearance quotes from candidates --------------------
def choose_appearance_quotes_with_gpt(book_title: str, characters, appearance_candidates_map):
    """
    STEP C: GPT selects best appearance quotes by returning INDICES only.
    No quote text in the response → zero JSON corruption risk.
    Python reconstructs actual quotes from indices.
    """
    system = "You are a literature analyst. Return ONLY valid JSON. No markdown."

    payload = {
        "book_title": book_title,
        "characters": []
    }
    for ch in characters:
        name = (ch.get("canonical_name") or "").strip()
        candidates = appearance_candidates_map.get(name, [])
        payload["characters"].append({
            "canonical_name": name,
            "candidates": [
                {"idx": i, "preview": c["quote"][:120] if c.get("quote") else ""}
                for i, c in enumerate(candidates)
            ]
        })

    prompt = (
        "GOAL: select up to 4 candidates that best describe CANONICAL (timeless) physical appearance.\n"
        "Priority 1 — STABLE physical features: eye colour/shape, hair colour/texture, face/complexion,\n"
        "  figure/height/build, characteristic physical adjectives (handsome, plain, dark, fair, slender…).\n"
        "Priority 2 — TYPICAL clothing that defines the character's usual look (period dress, uniform, etc.).\n"
        "Priority 3 — Other visual details that help a portrait artist draw the character.\n"
        "REJECT these always:\n"
        "  - Situational dirt/mess ('muddy petticoat', 'untidy after a walk') — these describe a moment, not the character.\n"
        "  - Pure dialogue with no stable visual detail.\n"
        "  - Pure emotion/action/personality (no body description).\n"
        "  - Describes ANOTHER person's looks ('I remember her as slim...').\n"
        "  - Coincidental appearance words ('old friend', 'fair price', 'dark mood').\n"
        "If multiple candidates describe the SAME feature (e.g. two quotes both about 'fine eyes'),\n"
        "  pick the one with more detail; skip the other.\n"
        "Return ONLY indices of accepted candidates.\n"
        "Return STRICT JSON (no markdown):\n"
        "{\"appearance\": [{\"canonical_name\": \"str\", \"selected_indices\": [0, 2, 3]}]}\n"
        "Use [] for selected_indices if none qualify.\n"
    )

    content = call_aitunnel(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt + "\n\nINPUT:\n" + json.dumps(payload, ensure_ascii=False)},
        ],
        max_tokens=600,
        temperature=0.1,
    )

    raw = _safe_json_from_model(content)

    # Reconstruct actual quotes from indices
    result = {"appearance": []}
    for item in raw.get("appearance", []):
        name = (item.get("canonical_name") or "").strip()
        indices = item.get("selected_indices") or []
        candidates = appearance_candidates_map.get(name, [])
        aq = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                c = candidates[idx]
                aq.append({"quote": c["quote"], "location": c.get("location", "unknown")})
        result["appearance"].append({"canonical_name": name, "appearance_quotes": aq})
    return result


# -------------------- prompt builder for image generation (no extra GPT calls) --------------------
def build_auto_description_from_character(book: dict, character: dict, max_quotes: int = 3) -> str:
    """
    Create a compact English prompt for image generation using existing appearance_quotes.
    This is rule-based and does not call any external LLM to keep requests cheap.
    """
    if not character:
        return ""

    name = (character.get("character_name") or "").strip()
    appearance_quotes = character.get("appearance_quotes") or []
    evidence_quotes = character.get("evidence_quotes") or []

    # basic book context
    title = (book or {}).get("title") or ""
    author = (book or {}).get("author") or ""

    header_parts = []
    if name:
        header_parts.append(f"Portrait of {name}")
    if title:
        if author:
            header_parts.append(f"from the novel \"{title}\" by {author}")
        else:
            header_parts.append(f"from the novel \"{title}\"")
    header = ", ".join(header_parts) if header_parts else "Portrait of a literary character"

    # Score quotes so we prefer the most "portrait-like" details.
    # (Avoid choosing only height/tallness or chapter headings.)
    def score_appearance(txt: str) -> int:
        if not txt:
            return 0
        lower = txt.lower()
        if any(x in lower for x in ["chapter", "heading to chapter", "tailpiece"]):
            return -1000

        score = 0
        # Face / eyes / complexion
        for kw in ["eyes", "eye", "brow", "cheek", "complexion", "lips", "face", "countenance", "handsome", "beautiful", "expression"]:
            if kw in lower:
                score += 10
        # Hair
        for kw in ["hair", "ringlet", "curly", "locks"]:
            if kw in lower:
                score += 9
        # Clothing
        for kw in ["gown", "petticoat", "dress", "coat", "clothing", "clothe"]:
            if kw in lower:
                score += 7
        # Figure / height
        for kw in ["figure", "height", "tall", "slender", "stature"]:
            if kw in lower:
                score += 6
        # Colors
        for kw in ["red", "blue", "gray", "grey", "green", "black", "brown", "white"]:
            if kw in lower:
                score += 5
        return score

    def score_evidence(txt: str) -> int:
        if not txt:
            return 0
        lower = txt.lower()
        if any(x in lower for x in ["chapter", "heading to chapter", "tailpiece"]):
            return -1000
        score = 0
        for kw in ["said", "went", "walk", "danced", "entered", "obliged", "mr", "miss", "bennet", "darcy", "she", "he", "they"]:
            if kw in lower:
                score += 3
        # prefer more content (slightly)
        score += min(len(txt) // 80, 6)
        return score

    appearance_texts = []
    for q in appearance_quotes:
        txt = (q.get("quote") or "").strip() if isinstance(q, dict) else str(q).strip()
        if txt:
            appearance_texts.append(txt)

    evidence_texts = []
    for q in evidence_quotes:
        txt = (q.get("quote") or "").strip() if isinstance(q, dict) else str(q).strip()
        if txt:
            evidence_texts.append(txt)

    if appearance_texts:
        appearance_texts.sort(key=score_appearance, reverse=True)
        selected_quotes = appearance_texts[:max_quotes]
    else:
        selected_quotes = []

    if not selected_quotes and evidence_texts:
        evidence_texts.sort(key=score_evidence, reverse=True)
        selected_quotes = evidence_texts[:max_quotes]

    # compact quotes block
    quotes_part = ""
    if selected_quotes:
        # Make sure the total length is reasonable
        merged = " ".join(f"\"{q}\"" for q in selected_quotes)
        if len(merged) > 480:
            merged = merged[:480].rsplit(" ", 1)[0] + "…"
        quotes_part = f" Use these lines as a guide to appearance and clothing: {merged}."

    # soft global style hint (can be overridden on the client side if needed)
    style_hint = " Illustration, detailed character design, focus on face, body and clothing, neutral background."

    return header + "." + quotes_part + style_hint


# -------------------- routes --------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "visulit"})


@app.route("/api/usage", methods=["GET"])
def api_usage():
    user_id = get_user_id(request)
    usage = load_json(USAGE_FILE, {})
    t = today_key()
    used = int(usage.get(t, {}).get(user_id, 0))
    remaining = max(0, DAILY_FREE_LIMIT - used)

    resp = make_response(jsonify({
        "success": True,
        "used_today": used,
        "remaining_today": remaining,
        "daily_limit": DAILY_FREE_LIMIT
    }))

    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", user_id, max_age=365*24*60*60)

    return resp


@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Return last generated characters/images for current user (mock or real),
    newest first.
    """
    user_id = get_user_id(request)
    items = load_json(HISTORY_FILE, [])
    if not isinstance(items, list):
        items = []

    user_items = [r for r in items if r.get("user_id") == user_id]
    user_items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    # do not leak user_id back to client
    sanitized = []
    for r in user_items:
        rr = dict(r)
        rr.pop("user_id", None)
        sanitized.append(rr)

    return jsonify({"success": True, "history": sanitized})


@app.route("/api/books", methods=["GET"])
def api_books():
    query = (request.args.get("query") or "").strip().lower()
    limit = int(request.args.get("limit") or 150)
    limit = max(1, min(limit, 400))
    mode = (request.args.get("mode") or "curated").strip().lower()

    all_books = load_json(BOOKS_FILE, [])

    if mode == "curated":
        curated = load_json(CURATED_FILE, [])
        idx = {b.get("book_id"): b for b in all_books if b.get("book_id")}

        result = []
        for item in curated:
            bid = item.get("book_id")
            full = idx.get(bid, {})
            merged = {
                "book_id": bid,
                "title": item.get("title") or full.get("title"),
                "author": item.get("author") or full.get("author"),
                "year": full.get("year"),
                "source": full.get("source") or item.get("source") or "curated",
                "text_url": full.get("text_url"),
                "popularity_score": item.get("popularity_score", full.get("popularity_score", 0)),
            }
            if not merged.get("text_url"):
                merged["missing_text_url"] = True
            result.append(merged)

        result.sort(key=lambda b: (b.get("popularity_score", 0), (b.get("title") or "")), reverse=True)
    else:
        result = all_books
        if not query:
            result = sorted(result, key=lambda b: (b.get("title") or "").lower())

    if query:
        result = [b for b in result if query in (b.get("title") or "").lower() or query in (b.get("author") or "").lower()]

    result = result[:limit]
    return jsonify({"success": True, "books": result, "count": len(result)})


@app.route("/api/characters", methods=["GET"])
def api_characters():
    book_id = request.args.get("book_id")
    if not book_id:
        return jsonify({"success": False, "error": "book_id required"}), 400

    all_chars = load_json(CHARACTERS_FILE, [])
    book_chars = [c for c in all_chars if c.get("book_id") == book_id]

    def sort_key(c):
        src = c.get("source") or ""
        role = c.get("role") or ""
        name = (c.get("character_name") or "").lower()
        src_rank = 0 if src == "gpt_prepare" else (1 if src == "user_added" else (2 if src == "verified" else 3))
        role_rank = 0 if role == "main" else 1
        return (src_rank, role_rank, name)

    book_chars.sort(key=sort_key)
    return jsonify({"success": True, "characters": book_chars, "count": len(book_chars)})


@app.route("/api/prepare_book", methods=["POST"])
def api_prepare_book():
    started = time.time()

    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    overwrite = bool(data.get("overwrite", False))
    main_limit = int(data.get("main_limit", 12))

    if not book_id:
        return jsonify({"success": False, "error": "book_id required"}), 400

    all_books = load_json(BOOKS_FILE, [])
    book = next((b for b in all_books if b.get("book_id") == book_id), None)
    if not book:
        return jsonify({"success": False, "error": "Book not found"}), 404

    # cache
    all_chars = load_json(CHARACTERS_FILE, [])
    existing = [c for c in all_chars if c.get("book_id") == book_id and c.get("source") == "gpt_prepare"]
    if existing and not overwrite:
        existing = sorted(existing, key=lambda c: (c.get("character_name") or "").lower())
        return jsonify({
            "success": True,
            "cached": True,
            "count": len(existing),
            "eta_seconds": 0,
            "characters": existing
        })

    text_url = book.get("text_url")
    if not text_url:
        return jsonify({"success": False, "error": "No text_url for this book"}), 400

    # download
    try:
        r = requests.get(text_url, timeout=60)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to download text: {str(e)}"}), 500

    # candidates
    raw = extract_candidates_from_text(text, book.get("title", ""))

    # STEP A: main chars by GPT
    try:
        preparedA = prepare_main_characters(book.get("title", ""), text, raw, main_limit=main_limit)
    except Exception as e:
        return jsonify({"success": False, "error": f"GPT prepare failed: {str(e)}"}), 500

    main_chars = preparedA.get("main_characters", [])
    if not isinstance(main_chars, list):
        return jsonify({"success": False, "error": "Bad GPT response (main_characters)"}), 500

    # STEP A-b: evidence quotes from code (guaranteed to contain character name)
    evidence_map = extract_evidence_quotes_from_text(text, main_chars, max_per_char=4)
    for mc in main_chars:
        cname = (mc.get("canonical_name") or "").strip()
        mc["evidence_quotes"] = evidence_map.get(cname, [])

    # STEP B: appearance candidates from FULL text
    appearance_candidates_map = build_appearance_candidates(text, main_chars, max_per_char=28)

    # STEP C (no-GPT): select best appearance quotes ONLY from candidates.
    # We skip GPT selection here because it can over-reject valid "portrait-worthy"
    # lines even when strong candidates exist.
    chosen_map = {}
    for mc in main_chars:
        name_key = (mc.get("canonical_name") or "").strip()
        canonical = normalize_name(name_key)
        candidates = appearance_candidates_map.get(name_key, []) if name_key else []
        chosen_map[canonical] = select_appearance_quotes_from_candidates(candidates, max_quotes=6) if canonical else []

    # overwrite old prepared
    if overwrite:
        all_chars = [c for c in all_chars if not (c.get("book_id") == book_id and c.get("source") == "gpt_prepare")]
    else:
        # if not overwrite, still remove old gpt_prepare to avoid duplicates on rerun
        all_chars = [c for c in all_chars if not (c.get("book_id") == book_id and c.get("source") == "gpt_prepare")]

    ts = datetime.now(timezone.utc).isoformat()
    saved = []

    for mc in main_chars:
        canonical = normalize_name((mc.get("canonical_name") or "").strip())
        if not canonical:
            continue

        aliases = mc.get("aliases") or []
        aliases_norm = []
        if isinstance(aliases, list):
            for a in aliases:
                na = normalize_name(str(a))
                if na:
                    aliases_norm.append(na)

        if canonical not in aliases_norm:
            aliases_norm.insert(0, canonical)

        # evidence quotes already extracted by code — always contain the character's name
        evq = mc.get("evidence_quotes") or []
        clean_ev = []
        if isinstance(evq, list):
            for q in evq:
                if not isinstance(q, dict):
                    continue
                qt = (q.get("quote") or "").strip()
                if qt:
                    clean_ev.append({
                        "quote": qt,
                        "location": (q.get("location") or "unknown").strip()
                    })

        # appearance quotes: from step C if present; else keep from step A (sanitized)
        apq = chosen_map.get(canonical)
        if apq is None or not apq:
            # fallback: use appearance_quotes from step A, but still pass through the same visual filter
            apq = []
            raw_ap = mc.get("appearance_quotes") or []
            if isinstance(raw_ap, list):
                for q in raw_ap:
                    if not isinstance(q, dict):
                        continue
                    quote_text = (q.get("quote") or "").strip()
                    if not quote_text:
                        continue
                    if not is_visual_appearance_quote(quote_text):
                        continue
                    if quote_describes_another_person(quote_text):
                        continue
                    apq.append({
                        "quote": quote_text,
                        "location": (q.get("location") or "unknown").strip()
                    })

        cid = hashlib.md5(f"{book_id}:{canonical}".encode("utf-8")).hexdigest()[:10]
        rec = {
            "character_id": f"{book_id}-canon-{cid}",
            "book_id": book_id,
            "character_name": canonical,
            "aliases": aliases_norm,
            "role": "main",
            "evidence_quotes": clean_ev,
            "appearance_quotes": apq,
            "verified": False,
            "source": "gpt_prepare",
            "created_at": ts
        }
        all_chars.append(rec)
        saved.append(rec)

    save_json(CHARACTERS_FILE, all_chars)

    saved = sorted(saved, key=lambda c: (c.get("character_name") or "").lower())

    elapsed = time.time() - started
    eta = int(max(10, min(90, round(elapsed))))  # best effort, UI will show it nicely next time

    return jsonify({
        "success": True,
        "cached": False,
        "count": len(saved),
        "eta_seconds": eta,
        "characters": saved
    })


@app.route("/api/reselect_appearance_quotes", methods=["POST"])
def api_reselect_appearance_quotes():
    """
    Re-run ONLY the deterministic appearance-quote selection step (no GPT).
    Helps fix portrait quality without paying for full prepare_book again.
    """
    data = request.get_json(silent=True) or {}
    book_id = (data.get("book_id") or "").strip()
    max_per_char = int(data.get("max_per_char") or 28)
    max_quotes = int(data.get("max_quotes") or 6)

    if not book_id:
        return jsonify({"success": False, "error": "book_id required"}), 400

    all_books = load_json(BOOKS_FILE, [])
    book = next((b for b in all_books if b.get("book_id") == book_id), None)
    if not book:
        return jsonify({"success": False, "error": "Book not found"}), 404

    text_url = book.get("text_url")
    if not text_url:
        return jsonify({"success": False, "error": "No text_url for this book"}), 400

    try:
        r = requests.get(text_url, timeout=60)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to download text: {str(e)}"}), 500

    all_chars = load_json(CHARACTERS_FILE, [])
    target_recs = [
        c for c in all_chars
        if c.get("book_id") == book_id and c.get("role") == "main" and c.get("source") == "gpt_prepare"
    ]
    if not target_recs:
        return jsonify({"success": False, "error": "No gpt_prepare main characters found for this book"}), 404

    builder_chars = []
    for c in target_recs:
        builder_chars.append({
            "canonical_name": c.get("character_name") or "",
            "aliases": c.get("aliases") or [],
        })

    appearance_candidates_map = build_appearance_candidates(text, builder_chars, max_per_char=max_per_char)

    chosen_map = {}
    for mc in builder_chars:
        name_key = (mc.get("canonical_name") or "").strip()
        canonical = normalize_name(name_key)
        candidates = appearance_candidates_map.get(name_key, []) if name_key else []
        chosen_map[canonical] = select_appearance_quotes_from_candidates(candidates, max_quotes=max_quotes) if canonical else []

    updated = 0
    for rec in all_chars:
        if rec.get("book_id") != book_id:
            continue
        if rec.get("role") != "main" or rec.get("source") != "gpt_prepare":
            continue
        canonical = normalize_name(rec.get("character_name") or "")
        rec["appearance_quotes"] = chosen_map.get(canonical, [])
        updated += 1

    save_json(CHARACTERS_FILE, all_chars)
    return jsonify({"success": True, "updated": updated})


@app.route("/api/add_character", methods=["POST"])
def api_add_character():
    """
    Add one character to a book that was already prepared. User provides the name;
    we fetch evidence + appearance quotes and append to cache. No overwrite of existing.
    """
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    character_name = (data.get("character_name") or "").strip()

    if not book_id or not character_name:
        return jsonify({"success": False, "error": "book_id and character_name required"}), 400

    all_books = load_json(BOOKS_FILE, [])
    book = next((b for b in all_books if b.get("book_id") == book_id), None)
    if not book:
        return jsonify({"success": False, "error": "Book not found"}), 404

    text_url = book.get("text_url")
    if not text_url:
        return jsonify({"success": False, "error": "No text_url for this book"}), 400

    try:
        r = requests.get(text_url, timeout=60)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to download text: {str(e)}"}), 500

    # Aliases: name + last name if multi-word (e.g. "John Brooke" -> ["John Brooke", "Brooke"])
    aliases = [character_name]
    if " " in character_name:
        aliases.append(character_name.split()[-1])

    single_char = [{"canonical_name": character_name, "aliases": aliases}]

    evidence_map = extract_evidence_quotes_from_text(text, single_char, max_per_char=4)
    for mc in single_char:
        cname = (mc.get("canonical_name") or "").strip()
        mc["evidence_quotes"] = evidence_map.get(cname, [])

    appearance_candidates_map = build_appearance_candidates(text, single_char, max_per_char=28)

    # STEP C (no-GPT) for user-added character too: select from candidates deterministically.
    chosen_map = {}
    name_key = (single_char[0].get("canonical_name") or "").strip()
    canonical = normalize_name(name_key)
    candidates = appearance_candidates_map.get(name_key, []) if name_key else []
    chosen_map[canonical] = select_appearance_quotes_from_candidates(candidates, max_quotes=6) if canonical else []

    mc = single_char[0]
    canonical = normalize_name((mc.get("canonical_name") or "").strip())
    if not canonical:
        return jsonify({"success": False, "error": "Invalid character name"}), 400

    all_chars = load_json(CHARACTERS_FILE, [])
    existing = [c for c in all_chars if c.get("book_id") == book_id and normalize_name((c.get("character_name") or "")) == canonical]
    if existing:
        return jsonify({"success": False, "error": "This character is already in the list"}), 400

    aliases_norm = [normalize_name(a) for a in (mc.get("aliases") or []) if normalize_name(a)]
    if canonical not in aliases_norm:
        aliases_norm.insert(0, canonical)

    clean_ev = []
    for q in mc.get("evidence_quotes") or []:
        if isinstance(q, dict) and (q.get("quote") or "").strip():
            clean_ev.append({"quote": (q["quote"] or "").strip(), "location": (q.get("location") or "unknown").strip()})

    apq = chosen_map.get(canonical) or []

    ts = datetime.now(timezone.utc).isoformat()
    cid = hashlib.md5(f"{book_id}:{canonical}:{ts}".encode("utf-8")).hexdigest()[:10]
    rec = {
        "character_id": f"{book_id}-add-{cid}",
        "book_id": book_id,
        "character_name": canonical,
        "aliases": aliases_norm,
        "role": "main",
        "evidence_quotes": clean_ev,
        "appearance_quotes": apq,
        "verified": False,
        "source": "user_added",
        "created_at": ts,
    }

    all_chars.append(rec)
    save_json(CHARACTERS_FILE, all_chars)

    return jsonify({"success": True, "character": rec})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}

    character_name = (data.get("character_name") or "").strip()
    description = (data.get("description") or "").strip()
    character_id = (data.get("character_id") or "").strip()
    auto_description = bool(data.get("auto_description", False))

    # Optional: build description automatically from stored character + quotes
    if (auto_description or not description) and character_id:
        all_chars = load_json(CHARACTERS_FILE, [])
        ch = next((c for c in all_chars if c.get("character_id") == character_id), None)
        if ch:
            book = find_book_by_id(ch.get("book_id"))
            auto_desc = build_auto_description_from_character(book, ch)
            if auto_desc:
                description = auto_desc
                if not character_name:
                    character_name = (ch.get("character_name") or "").strip()

    if not character_name:
        return jsonify({"success": False, "error": "character_name required"}), 400
    if not description:
        return jsonify({"success": False, "error": "description required"}), 400

    user_id = get_user_id(request)

    # Image cache (cost saving):
    # If we already generated the exact same image "prompt" (description) for this user,
    # return it without another API call and without incrementing usage.
    prompt_hash = hashlib.md5(description.encode("utf-8")).hexdigest()
    normalized_char_id = character_id or None
    try:
        history_items = load_json(HISTORY_FILE, [])
        if isinstance(history_items, list):
            # search from newest to oldest for the latest matching record
            for rec in reversed(history_items):
                if not isinstance(rec, dict):
                    continue
                if rec.get("user_id") != user_id:
                    continue
                rec_char_id = rec.get("character_id") or None
                if rec_char_id != normalized_char_id:
                    continue
                # Prefer cached prompt_hash if present, else compute from description
                rec_ph = rec.get("prompt_hash")
                if rec_ph and rec_ph == prompt_hash:
                    image_url = rec.get("image_url")
                    if image_url:
                        remaining = get_remaining_today(user_id)
                        return jsonify({
                            "success": True,
                            "image_url": image_url,
                            "character_name": rec.get("character_name") or character_name,
                            "remaining_free_count": remaining,
                            "cached": True
                        })
                rec_desc = (rec.get("description") or "").strip()
                if rec_desc and hashlib.md5(rec_desc.encode("utf-8")).hexdigest() == prompt_hash:
                    image_url = rec.get("image_url")
                    if image_url:
                        remaining = get_remaining_today(user_id)
                        return jsonify({
                            "success": True,
                            "image_url": image_url,
                            "character_name": rec.get("character_name") or character_name,
                            "remaining_free_count": remaining,
                            "cached": True
                        })
    except Exception:
        # Cache failure should not break generation flow.
        pass

    allowed, remaining = check_and_update_usage(user_id)
    if not allowed:
        return jsonify({
            "success": False,
            "error": "Daily generation limit reached",
            "limit_reached": True,
            "daily_limit": DAILY_FREE_LIMIT
        }), 403

    # Real image generation (OpenAI-compatible /images/generations on the same provider base_url).
    # For NeuroAPI "Nano Banana" use model: "gemini-3-pro-image-preview".
    image_model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview").strip()
    image_size = os.getenv("IMAGE_SIZE", "1024x1536").strip()

    if not AITUNNEL_API_KEY or not AITUNNEL_BASE_URL:
        return jsonify({"success": False, "error": "Image generation not configured (API key/base url missing)"}), 500

    img_url = f"{AITUNNEL_BASE_URL.rstrip('/')}/images/generations"
    headers = {"Authorization": f"Bearer {AITUNNEL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": image_model, "prompt": description, "n": 1, "size": image_size}

    try:
        img_resp = requests.post(img_url, headers=headers, json=payload, timeout=240)
        img_resp.raise_for_status()
        img_data = img_resp.json()
    except Exception as e:
        return jsonify({"success": False, "error": f"Image generation failed: {type(e).__name__}: {str(e)}"}), 500

    # OpenAI-compatible response:
    # - { "data": [ { "url": "https://..." } ] }
    # - or { "data": [ { "b64_json": "..." } ] }
    image_url = None
    arr = (img_data.get("data") if isinstance(img_data, dict) else None) or []
    if isinstance(arr, list) and arr and isinstance(arr[0], dict):
        item = arr[0]
        if item.get("url"):
            image_url = str(item["url"])
        elif item.get("b64_json"):
            # Return as data URI so frontend can render directly.
            mime = item.get("mime_type") or item.get("content_type") or "image/png"
            image_url = f"data:{mime};base64,{item['b64_json']}"
    # last-resort fields
    if not image_url and isinstance(img_data, dict):
        image_url = img_data.get("image_url") or img_data.get("url")

    if not image_url:
        return jsonify({"success": False, "error": f"Image generation returned no image url (response keys: {list(img_data.keys()) if isinstance(img_data, dict) else type(img_data).__name__})"}), 500

    # save to per-user history (even for mock stage)
    source_type = "book" if character_id else "custom"
    history_record = {
        "id": str(uuid.uuid4()),
        "source_type": source_type,
        "character_id": character_id or None,
        "character_name": character_name,
        "description": description,
        "prompt_hash": prompt_hash,
        "image_url": image_url,
    }
    try:
        append_history_record(user_id, history_record)
    except Exception:
        # history failure should not break main response
        pass

    resp = make_response(jsonify({
        "success": True,
        "image_url": image_url,
        "character_name": character_name,
        "remaining_free_count": remaining
    }))

    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", user_id, max_age=365*24*60*60)

    return resp


if __name__ == "__main__":
    # на ноуте: http://127.0.0.1:5000
    # на телефоне в Wi-Fi: http://192.168.0.16:5000 (твой IP будет свой)
    app.run(debug=False, host="0.0.0.0", port=5000)