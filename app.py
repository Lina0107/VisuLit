# app.py
from flask import Flask, request, jsonify, make_response, render_template, send_file
from flask_cors import CORS
import json
import os
import hashlib
import base64
from datetime import datetime, timezone
import requests
import uuid
import re
import time
import unicodedata

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
PORTRAITS_DIR = os.path.join(DATA_DIR, "portraits")

DAILY_FREE_LIMIT = 5

AITUNNEL_API_KEY = os.getenv("AITUNNEL_API_KEY", "").strip()
AITUNNEL_BASE_URL = os.getenv("AITUNNEL_BASE_URL", "https://api.aitunnel.ru/v1").strip()
AITUNNEL_MODEL = os.getenv("AITUNNEL_MODEL", "gpt-4.1-mini").strip()

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PORTRAITS_DIR, exist_ok=True)


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


def charge_generation_or_limit_response(user_id):
    """
    Deduct one daily generation before serving cache or calling the image API.
    Cached/canonical hits count toward the limit too.
    Returns (remaining, None) or (None, flask_response_tuple).
    """
    allowed, remaining = check_and_update_usage(user_id)
    if not allowed:
        return None, (
            jsonify({
                "success": False,
                "error": "Daily generation limit reached",
                "limit_reached": True,
                "daily_limit": DAILY_FREE_LIMIT,
            }),
            403,
        )
    return remaining, None


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

    # Use full cleaned text for higher quality character selection.
    # This is more expensive, but avoids missing characters that are
    # described outside the old head+middle slice.
    text_slice = clean

    system = "You are a literature analyst. Return ONLY valid JSON. No markdown, no extra text."

    user_obj = {
        "book_title": book_title,
        "clusters": clusters,
        "main_limit": main_limit,
        "text_excerpt": text_slice,
    }

    prompt = (
        "Given: book title, candidate name clusters from the text, and the full cleaned text.\n"
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

    # Be tolerant to occasional malformed model output:
    # - top-level list instead of {"main_characters":[...]}
    # - list items that are not dicts
    if isinstance(obj, list):
        obj = {"main_characters": obj}
    if not isinstance(obj, dict):
        raise RuntimeError("Bad GPT response format: expected object or list")

    raw_chars = obj.get("main_characters", [])
    if isinstance(raw_chars, dict):
        raw_chars = [raw_chars]
    if not isinstance(raw_chars, list):
        raw_chars = []

    normalized = []
    for ch in raw_chars:
        if not isinstance(ch, dict):
            continue
        canonical = str(ch.get("canonical_name") or "").strip()
        aliases = ch.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        if not isinstance(aliases, list):
            aliases = []
        aliases = [str(a).strip() for a in aliases if str(a).strip()]
        if canonical and canonical not in aliases:
            aliases.insert(0, canonical)
        if not canonical:
            continue
        normalized.append({
            "canonical_name": canonical,
            "aliases": aliases,
            "evidence_quotes": [],
            "appearance_quotes": [],
        })

    obj["main_characters"] = normalized[: max(1, int(main_limit))]
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
    "face", "features", "complexion", "countenance", "eyes", "hair", "locks", "curl", "curls", "brow", "cheek",
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
    "eyes", "hair", "locks", "curl", "curls", "face", "features", "complexion", "countenance", "figure",
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

# Horror/action fragments that belong to a scene, not a calm literary portrait.
PORTRAIT_ACTION_PATTERNS = [
    re.compile(r"\b(blood|bloody|gore|smeared|smear|trickl\w*|stream of blood)\b", re.IGNORECASE),
    re.compile(r"\b(my|your|his|her)\s+blood\s+(was|were|had|ran|run)\b", re.IGNORECASE),
    re.compile(r"\b(champing|rage|fury|terror|scream|shriek|mad with)\b", re.IGNORECASE),
    re.compile(r"\b(grasped|grasp|seized|struck|attacked|bit(?:ing)?|throttle)\b", re.IGNORECASE),
]

# Dramatic beats that name the character but are still not calm portrait material.
PORTRAIT_SCENE_BEAT_PATTERNS = [
    re.compile(r"\bred light of triumph in his eyes\b", re.IGNORECASE),
    re.compile(r"\bkissing his hand to me\b", re.IGNORECASE),
]

_FEMALE_TITLE_RE = re.compile(
    r"\b(miss|mrs|ms|madam|lady|queen|princess|duchess|countess|girl|woman|wife|mother|daughter|sister|aunt)\b",
    re.IGNORECASE,
)
_MALE_TITLE_RE = re.compile(
    r"\b(mr|lord|sir|count|king|prince|duke|baron|dr|doctor|husband|father|son|brother|uncle)\b",
    re.IGNORECASE,
)


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


def _character_gender_hint(character_name: str, aliases: list | None) -> str | None:
    """Rough gender hint from titles/names — used only to reject obvious pronoun mismatches."""
    blob = " ".join([character_name or ""] + [str(a) for a in (aliases or []) if a])
    has_f = bool(_FEMALE_TITLE_RE.search(blob))
    has_m = bool(_MALE_TITLE_RE.search(blob))
    if has_f and not has_m:
        return "f"
    if has_m and not has_f:
        return "m"
    return None


def _quote_mentions_character(quote: str, character_name: str, aliases: list | None) -> bool:
    if not quote:
        return False
    seen = set()
    for raw in [character_name] + list(aliases or []):
        name = (raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        if len(name) >= 6 or " " in name:
            if re.search(rf"\b{re.escape(name)}\b", quote, re.IGNORECASE):
                return True
        elif len(name) >= 4:
            if re.search(rf"\bthe\s+{re.escape(name)}\b", quote, re.IGNORECASE):
                return True
    return False


# Signature Dracula/vampire physical description (observer POV) — not the narrator's own face.
_VAMPIRE_FACE_MARKERS = [
    re.compile(r"\bwaxen face\b", re.IGNORECASE),
    re.compile(r"\bheavy moustache\b", re.IGNORECASE),
    re.compile(r"\bpeculiarly arched nostrils\b", re.IGNORECASE),
    re.compile(r"\blofty domed forehead\b", re.IGNORECASE),
    re.compile(r"\bsharp white teeth\b", re.IGNORECASE),
    re.compile(r"\bparted red lips\b", re.IGNORECASE),
    re.compile(r"\bteeth so white\b", re.IGNORECASE),
    re.compile(r"\beyes that seem to be burning\b", re.IGNORECASE),
    re.compile(r"\ball in black\b", re.IGNORECASE),
    re.compile(r"\bhollow burning eyes\b", re.IGNORECASE),
    re.compile(r"\bhigh aquiline nose\b", re.IGNORECASE),
]


def _character_is_count_or_vampire(character_name: str, aliases: list | None = None) -> bool:
    blob = " ".join([character_name or ""] + [str(a) for a in (aliases or []) if a]).lower()
    return "dracula" in blob or re.search(r"\bcount\b", blob)


def quote_references_other_cast_member(
    quote: str,
    character_name: str,
    aliases: list | None,
    cast_members: list | None,
) -> bool:
    """Quote names another book character — e.g. Count's face stored on Jonathan Harker."""
    if not quote or not cast_members:
        return False
    q = quote.strip()
    self_norm = normalize_name(character_name)
    mentions_self = _quote_mentions_character(q, character_name, aliases)

    for other in cast_members:
        oname = (other.get("character_name") or other.get("canonical_name") or other.get("name") or "").strip()
        if not oname or normalize_name(oname) == self_norm:
            continue
        other_aliases = other.get("aliases") or []

        # Require a distinctive full name (>= 8 chars) to avoid sibling surname collisions.
        for nm in [oname] + [a for a in other_aliases if isinstance(a, str)]:
            nm = nm.strip()
            if len(nm) < 8 or " " not in nm:
                continue
            if re.search(rf"\b{re.escape(nm)}\b", q, re.IGNORECASE):
                if not mentions_self:
                    return True

        other_blob = (oname + " " + " ".join(str(a) for a in other_aliases)).lower()
        if "dracula" in other_blob or re.search(r"\bcount\b", other_blob):
            if re.search(r"\bthe Count'?s?\b", q, re.IGNORECASE) and not mentions_self:
                return True
            if re.search(r"\bCount Dracula'?s?\b", q, re.IGNORECASE) and not _character_is_count_or_vampire(character_name, aliases):
                return True
            if re.search(r"\bCount'?s\s+(evil\s+)?face\b", q, re.IGNORECASE) and not _character_is_count_or_vampire(character_name, aliases):
                return True

        if "hyde" in other_blob:
            if re.search(r"\bMr\.?\s*Hyde'?s?\b", q, re.IGNORECASE) and not _quote_mentions_character(q, character_name, aliases):
                return True

    return False


def quote_is_misattributed_villain_portrait(
    quote: str,
    character_name: str = "",
    aliases: list | None = None,
) -> bool:
    """Dracula-style face description attached to a non-vampire cast member (e.g. Harker's journal)."""
    if not quote or _character_is_count_or_vampire(character_name, aliases):
        return False
    if _quote_mentions_character(quote, character_name, aliases):
        return False
    hits = sum(1 for p in _VAMPIRE_FACE_MARKERS if p.search(quote))
    if hits >= 2:
        return True
    if hits >= 1 and re.search(r"\bwaxen face\b", quote, re.IGNORECASE):
        return True
    return False


def quote_describes_another_person(quote: str, character_name: str = "", aliases: list | None = None) -> bool:
    """
    Heuristic: narrator describing someone else's appearance.
    E.g. 'I remember her as slim...', 'Her face was ghastly...' (victim in a Dracula scene).
    Such quotes must not count as THIS character's own appearance.
    """
    if not quote or len(quote) < 20:
        return False
    q = quote.strip()
    flags = re.IGNORECASE
    mentions = _quote_mentions_character(q, character_name, aliases)
    # Pronoun-led descriptions are only suspicious when the quote never names
    # the character. With the name present ("Elizabeth … she had dark eyes")
    # the pronoun almost always refers to that same character.
    if re.search(r"\bI\s+remember\s+(her|him)\b", q, flags) and not mentions:
        return True
    if re.search(r"\bI\s+(recall|recollect|saw|noticed|thought)\s+(her|him|that\s+she|that\s+he)\b", q, flags) and not mentions:
        return True
    if re.search(r"\b(she|he)\s+had\s+(black|dark|fair|long|short|golden|white|grey|gray|red)\s+(hair|eyes|locks|brows)\b", q, flags) and not mentions:
        return True
    if re.match(r"^(she|he)\s+(was|had|looked|appeared|seemed)\s+", q, flags) and not mentions:
        return True
    if re.search(r"\b(last night|to-day|today)\s+he\s+(was|is)\b", q, flags) and not mentions:
        return True
    if re.search(r"\bto-day\s+he\s+is\s+(a\s+)?(drawn|haggard)\b", q, flags) and not mentions:
        return True
    if re.match(r"^the\s+(waxen\s+)?(face|mouth)\b", q, flags) and not mentions:
        return True
    if re.match(r"^a\s+tall\s+(man|woman)\b", q, flags) and not mentions:
        return True
    if re.match(r"^(her|his)\s+(face|lips|cheeks|throat|neck|hair|eyes|countenance|chin|brow|forehead)\b", q, flags):
        if not mentions:
            return True
    if re.match(r"^the\s+(fair\s+)?(woman|man|lady|girl|boy)\b", q, flags) and not mentions:
        return True
    if re.search(r"\bby her side stood\b", q, flags) and not mentions:
        return True
    if re.search(r"\b(slender neck of the fair woman|fair woman and with)\b", q, flags):
        return True

    gh = _character_gender_hint(character_name, aliases)
    if gh == "m" and re.match(r"^her\s+", q, flags) and not mentions:
        return True
    if gh == "f" and re.match(r"^his\s+", q, flags) and not mentions:
        return True
    return False


def quote_is_scene_beat_not_portrait(quote: str) -> bool:
    if not quote:
        return False
    return any(p.search(quote) for p in PORTRAIT_SCENE_BEAT_PATTERNS)


def quote_is_action_or_horror_scene(quote: str, character_name: str = "", aliases: list | None = None) -> bool:
    """Blood, violence, or horror staging — not a stable portrait line unless it names this character."""
    if not quote:
        return False
    if quote_is_scene_beat_not_portrait(quote):
        return True
    if not any(p.search(quote) for p in PORTRAIT_ACTION_PATTERNS):
        return False
    return not _quote_mentions_character(quote, character_name, aliases)


def is_portrait_worthy_quote(
    quote: str,
    character_name: str = "",
    aliases: list | None = None,
    cast_members: list | None = None,
) -> bool:
    """Full gate for appearance quotes used in portraits and stored on characters."""
    if not is_visual_appearance_quote(quote):
        return False
    if quote_references_other_cast_member(quote, character_name, aliases, cast_members):
        return False
    if quote_is_misattributed_villain_portrait(quote, character_name, aliases):
        return False
    if quote_describes_another_person(quote, character_name, aliases):
        return False
    if quote_is_action_or_horror_scene(quote, character_name, aliases):
        return False
    if any(p.search(quote) for p in SITUATIONAL_PATTERNS):
        return False
    return True


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


def select_appearance_quotes_from_candidates(
    candidates: list,
    max_quotes: int = 6,
    *,
    character_name: str = "",
    aliases: list | None = None,
    cast_members: list | None = None,
) -> list:
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
        if not is_portrait_worthy_quote(qt, character_name, aliases, cast_members):
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


# Same figure often appears under alternate spellings / diminutives across chapters or translations.
# If GPT keeps one form, appearance lines using another form are missed — merge common English variants.
# Keep groups conservative (omit ambiguous shorts like "Beth" vs Elizabeth family).
LITERARY_NAME_VARIANT_GROUPS = (
    frozenset({"Natasha", "Nataly", "Natalia", "Natalie", "Natásha"}),
    frozenset({"Elizabeth", "Eliza", "Lizzy", "Lizzie", "Elisabeth"}),
    frozenset({"Catherine", "Cathy", "Kate", "Katherine", "Katharine", "Kitty"}),
    frozenset({"Margaret", "Meg", "Maggie", "Peggy"}),
    frozenset({"Frederick", "Fred", "Freddy"}),
    frozenset({"Theodore", "Theo", "Ted"}),
    frozenset({"William", "Will", "Willie", "Bill", "Billy"}),
    frozenset({"Robert", "Bob", "Rob", "Bobby"}),
    frozenset({"James", "Jim", "Jimmy", "Jamie"}),
    frozenset({"John", "Jack", "Johnny"}),
    frozenset({"Edward", "Ed", "Ned", "Teddy"}),
    frozenset({"Alexander", "Alex", "Alec", "Sandy"}),
    frozenset({"Henrietta", "Hetty", "Etta"}),
    frozenset({"Frances", "Fanny"}),
    frozenset({"Christiana", "Chris", "Christie"}),
    frozenset({"Joseph", "Joe", "Joey"}),
    frozenset({"Richard", "Dick", "Rick"}),
    frozenset({"Charles", "Charlie", "Chuck"}),
    frozenset({"Thomas", "Tom", "Tommy"}),
    frozenset({"Michael", "Mike", "Mick"}),
    frozenset({"Samuel", "Sam", "Sammy"}),
    frozenset({"David", "Dave", "Davy"}),
    frozenset({"Harry", "Harold", "Hal"}),
    frozenset({"Anne", "Annie", "Nancy"}),
    frozenset({"Mary", "Molly", "Polly", "Mae"}),
    frozenset({"Sarah", "Sally", "Sadie"}),
    frozenset({"Eleanor", "Ellen", "Nell", "Nellie"}),
    frozenset({"Theresa", "Tess", "Tessa"}),
    frozenset({"Victoria", "Vicky", "Toria"}),
)


def enrich_cross_spell_aliases(main_chars: list) -> None:
    """
    For each main character, if canonical name or any alias contains a token from a variant group,
    append all spellings in that group so appearance/evidence scanners match alternate forms.
    Applies to every book (not title-specific).
    """
    if not main_chars:
        return
    for ch in main_chars:
        if not isinstance(ch, dict):
            continue
        canon = (ch.get("canonical_name") or "").strip()
        aliases = [str(a).strip() for a in (ch.get("aliases") or []) if isinstance(a, str) and str(a).strip()]
        blob = _normalize_for_match(f"{canon} {' '.join(aliases)}")
        words = set(blob.split())
        have = {normalize_name(x) for x in [canon] + aliases if x}
        merged = list(aliases)
        for group in LITERARY_NAME_VARIANT_GROUPS:
            norms = {_normalize_for_match(g) for g in group}
            norms.discard("")
            if not words & norms:
                continue
            for g in group:
                gn = normalize_name(g)
                if gn and gn not in have:
                    merged.append(g)
                    have.add(gn)
        ch["aliases"] = merged


def _normalize_for_match(s: str) -> str:
    """
    Lowercase + strip diacritics + collapse punctuation/spaces.
    Helps match aliases like "Natásha" against "Natasha".
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

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

    cast_members = [
        {
            "character_name": (c.get("canonical_name") or "").strip(),
            "aliases": c.get("aliases") or [],
        }
        for c in characters
        if (c.get("canonical_name") or "").strip()
    ]

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
            aa = _normalize_for_match(a)
            if not aa:
                continue
            alias_patterns.append(re.compile(rf"\b{re.escape(aa)}\b"))

        found = []
        seen_quotes = set()

        # Scan sentences: character may be named in an adjacent line while appearance uses only "she/her".
        # So we anchor on any of (i-1, i, i+1) containing an alias, then take the 3-sentence window around i.
        for i, (sent, offset) in enumerate(sentences):
            hit_alias = False
            for j in (i - 1, i, i + 1):
                if not (0 <= j < len(sentences)):
                    continue
                sj = _normalize_for_match(sentences[j][0])
                for p in alias_patterns:
                    if p.search(sj):
                        hit_alias = True
                        break
                if hit_alias:
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

            # Tolstoy/Austen often put valid appearance details inside dialogue.
            # Keep only very quote-heavy fragments out.
            quote_chars = sum(1 for c in snippet if c in ('"', '"', '"', "'"))
            if quote_chars > len(snippet) * 0.60:
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
            if not is_portrait_worthy_quote(snippet, name, aliases, cast_members):
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
        "  - Describes ANOTHER person's looks ('I remember her as slim...', 'Her face was ghastly...').\n"
        "  - Horror/action staging: blood on lips/throat, victims, rage, biting, grasping — not a calm portrait.\n"
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

    char_aliases = {
        (ch.get("canonical_name") or "").strip(): ch.get("aliases") or []
        for ch in characters
        if (ch.get("canonical_name") or "").strip()
    }

    # Reconstruct actual quotes from indices
    result = {"appearance": []}
    for item in raw.get("appearance", []):
        name = (item.get("canonical_name") or "").strip()
        indices = item.get("selected_indices") or []
        candidates = appearance_candidates_map.get(name, [])
        aliases = char_aliases.get(name, [])
        aq = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                c = candidates[idx]
                txt = (c.get("quote") or "").strip()
                if txt and is_portrait_worthy_quote(txt, name, aliases):
                    aq.append({"quote": txt, "location": c.get("location", "unknown")})
        result["appearance"].append({"canonical_name": name, "appearance_quotes": aq})
    return result


_GPT_VALIDATE_APPEARANCE_PROMPT = (
    "You audit appearance quotes for an AI PORTRAIT tool (calm literary head-and-shoulders image).\n"
    "For EACH quote below, decide if it describes THE NAMED CHARACTER's own stable physical appearance "
    "(face, hair, eyes, age, build, typical clothing) — not a scene, victim, or metaphor.\n\n"
    "REJECT if:\n"
    "- Describes ANOTHER person's body/face (e.g. 'Her face was ghastly…' for Count Dracula)\n"
    "- A diary narrator's description of someone else (e.g. Count Dracula's aquiline face on Jonathan Harker)\n"
    "- Quote names another cast member ('the Count's face', 'Count Dracula') for the wrong character\n"
    "- Horror/action staging: blood on lips/throat, biting, grasping a neck, terror, gore\n"
    "- Figurative language only ('my blood ran cold', 'blood congealed with horror')\n"
    "- Plot/dialogue with no portrait-worthy visual detail of THIS character\n"
    "- Only bystanders or crowd; character named nearby but not described\n\n"
    "ACCEPT if:\n"
    "- Stable features of THIS character: eyes, hair, complexion, scar, build, usual dress\n"
    "- 'Like the Count' when the character IS the Count; direct 'his face', 'her eyes' when clearly this character\n\n"
    "Return STRICT JSON only:\n"
    '{"characters":[{"canonical_name":"str","keep_indices":[0,2]}]}\n'
    "keep_indices refer to the quotes array for that character (0-based). Use [] if none are safe.\n"
)


def validate_appearance_quotes_batch_with_gpt(
    book_title: str,
    characters_with_quotes: list,
    cast_members: list | None = None,
) -> dict:
    """
    GPT pass 2 — auditor for one or many characters in a single call.
    characters_with_quotes: [{canonical_name, aliases, quotes:[{quote, location}]}]
    Returns: {normalized_canonical_name: [filtered quote dicts]}
    """
    if not characters_with_quotes or not AITUNNEL_API_KEY:
        return {}

    payload_chars = []
    quote_pools = {}  # norm_name -> list of original quote dicts (heuristic-prefiltered)

    cast = cast_members or [
        {
            "character_name": (ch.get("canonical_name") or ch.get("character_name") or "").strip(),
            "aliases": ch.get("aliases") or [],
        }
        for ch in characters_with_quotes
    ]

    for ch in characters_with_quotes:
        name = (ch.get("canonical_name") or ch.get("character_name") or "").strip()
        if not name:
            continue
        aliases = ch.get("aliases") or []
        pool = []
        for q in ch.get("quotes") or ch.get("appearance_quotes") or []:
            if not isinstance(q, dict):
                continue
            txt = (q.get("quote") or "").strip()
            if not txt or not is_portrait_worthy_quote(txt, name, aliases, cast):
                continue
            pool.append({"quote": txt, "location": (q.get("location") or "unknown").strip()})
        if not pool:
            continue
        norm = normalize_name(name)
        quote_pools[norm] = pool
        other_cast = [
            (c.get("character_name") or c.get("canonical_name") or "").strip()
            for c in cast
            if normalize_name(c.get("character_name") or c.get("canonical_name") or "") != norm
        ]
        payload_chars.append({
            "canonical_name": name,
            "aliases": aliases[:8],
            "other_cast_in_book": other_cast[:12],
            "quotes": [{"idx": i, "text": q["quote"][:220]} for i, q in enumerate(pool)],
        })

    if not payload_chars:
        return {}

    content = call_aitunnel(
        [
            {"role": "system", "content": "You are a careful literature analyst. Return ONLY valid JSON."},
            {
                "role": "user",
                "content": _GPT_VALIDATE_APPEARANCE_PROMPT
                + f'\nBook: "{book_title}"\n\nINPUT:\n'
                + json.dumps({"characters": payload_chars}, ensure_ascii=False),
            },
        ],
        max_tokens=min(1800, 200 * len(payload_chars) + 400),
        temperature=0.05,
        json_mode=True,
    )
    raw = _safe_json_from_model(content)
    out = {}
    for item in raw.get("characters", []):
        name = (item.get("canonical_name") or "").strip()
        if not name:
            continue
        norm = normalize_name(name)
        pool = quote_pools.get(norm, [])
        keep = []
        for idx in item.get("keep_indices") or []:
            if isinstance(idx, int) and 0 <= idx < len(pool):
                keep.append(pool[idx])
        out[norm] = keep
    return out


def _normalize_for_verbatim(s: str) -> str:
    """Loose normalization to verify a GPT-returned quote really exists in the text."""
    s = (s or "").lower()
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_appearance_quotes_with_gpt_fulltext(
    book_title: str,
    full_text: str,
    characters: list,
    *,
    max_quotes_per_char: int = 4,
    chunk_chars: int = 80000,
    max_calls: int = 60,
):
    """
    Deep pass: GPT reads the whole book in chunks and copies out verbatim
    appearance passages, resolving pronouns from context ("she/her" lines the
    name-anchored heuristic can never attribute). Every returned quote is
    verified to actually exist in the chunk before being accepted.
    Returns {normalized_name: [{quote, location}]}.
    """
    if not characters or not AITUNNEL_API_KEY:
        return {}

    clean = clean_gutenberg_text(full_text)
    total = len(clean)
    if not clean:
        return {}

    char_payload = []
    norm_by_listed = {}
    for ch in characters:
        name = (ch.get("canonical_name") or ch.get("character_name") or "").strip()
        if not name:
            continue
        aliases = [a for a in (ch.get("aliases") or []) if isinstance(a, str) and a.strip()]
        char_payload.append({"name": name, "aliases": aliases[:6]})
        norm_by_listed[normalize_name(name)] = name
    if not char_payload:
        return {}

    prompt_head = (
        f'You are given a verbatim excerpt from the novel "{book_title}" and a character list.\n'
        "TASK: copy out passages that describe the PHYSICAL appearance of the listed characters:\n"
        "stable features (eyes, hair, face, complexion, figure, height, build) or typical clothing.\n"
        "RULES:\n"
        "- Use surrounding context to resolve pronouns (she/her/he/his). Include a passage ONLY if you are\n"
        "  confident it describes the listed character, even when the passage itself uses only a pronoun.\n"
        "- Copy text EXACTLY as written in the excerpt (verbatim substring, 1-2 sentences, max 220 characters).\n"
        "- EXCLUDE: emotions, actions, blood/violence/horror staging, another person's looks, dialogue with\n"
        "  no visual detail, hypothetical or ironic remarks.\n"
        "- CRITICAL: diary narrators (e.g. Jonathan Harker) often DESCRIBE other characters (Count Dracula).\n"
        "  Assign only passages that describe the LISTED character's own body/face — not someone they observe.\n"
        f"- Max {max_quotes_per_char} passages per character. Omit characters with nothing.\n"
        'Return STRICT JSON: {"found": [{"name": "str", "quotes": ["str", ...]}]}\n'
    )

    results = {}
    calls = 0
    group_size = 18
    step = max(chunk_chars - 1500, 10000)

    for start in range(0, len(clean), step):
        chunk = clean[start:start + chunk_chars]
        if len(chunk) < 500:
            break
        norm_chunk = _normalize_for_verbatim(chunk)

        for gi in range(0, len(char_payload), group_size):
            group = char_payload[gi:gi + group_size]
            if calls >= max_calls:
                return results
            calls += 1
            try:
                content = call_aitunnel(
                    [
                        {"role": "system", "content": "You are a careful literature analyst. Return ONLY valid JSON."},
                        {
                            "role": "user",
                            "content": prompt_head
                            + "\nCHARACTERS:\n" + json.dumps(group, ensure_ascii=False)
                            + "\n\nEXCERPT:\n" + chunk,
                        },
                    ],
                    max_tokens=1400,
                    temperature=0.05,
                    json_mode=True,
                )
                raw = _safe_json_from_model(content)
            except Exception:
                app.logger.exception("deep quote extraction call failed (%s, chunk@%d)", book_title, start)
                continue

            for item in raw.get("found", []):
                norm = normalize_name((item.get("name") or "").strip())
                if norm not in norm_by_listed:
                    continue
                bucket = results.setdefault(norm, [])
                for qt in item.get("quotes") or []:
                    qt = re.sub(r"\s+", " ", str(qt or "")).strip()
                    if not qt or len(qt) < 25:
                        continue
                    if len(qt) > 240:
                        qt = qt[:240].rsplit(" ", 1)[0] + "…"
                    norm_q = _normalize_for_verbatim(qt)
                    pos = norm_chunk.find(norm_q)
                    if pos < 0:
                        continue  # hallucinated / paraphrased — reject
                    key = norm_q
                    if any(_normalize_for_verbatim(b["quote"]) == key for b in bucket):
                        continue
                    char_name = norm_by_listed[norm]
                    char_aliases = next(
                        (c.get("aliases") or [] for c in char_payload if normalize_name(c.get("name") or "") == norm),
                        [],
                    )
                    if not is_portrait_worthy_quote(qt, char_name, char_aliases, char_payload):
                        continue
                    if quote_is_action_or_horror_scene(qt, char_name, char_aliases):
                        continue
                    approx_offset = start + int(pos / max(len(norm_chunk), 1) * len(chunk))
                    bucket.append({
                        "quote": qt,
                        "location": _book_location(approx_offset, total),
                    })

    for norm in results:
        results[norm] = results[norm][:max_quotes_per_char * 2]
    return results


def _merge_appearance_quote_lists(*sources, character_name: str = "", aliases=None, cast_members=None, max_items: int = 12) -> list:
    """Dedupe quote dicts preserving order. Containment counts as duplicate
    (the same passage often appears truncated at different lengths)."""
    merged = []
    seen_norms = []
    for src in sources:
        if not src:
            continue
        for q in src:
            if not isinstance(q, dict):
                continue
            txt = (q.get("quote") or "").strip()
            if not txt:
                continue
            key = _normalize_for_verbatim(txt).rstrip(". ")
            if not key:
                continue
            if any(key in s or s in key for s in seen_norms):
                continue
            if not is_portrait_worthy_quote(txt, character_name, aliases, cast_members):
                continue
            seen_norms.append(key)
            merged.append({
                "quote": txt,
                "location": (q.get("location") or "unknown").strip(),
            })
            if len(merged) >= max_items:
                return merged
    return merged


def resolve_appearance_quotes_for_character(
    book_title: str,
    mc: dict,
    candidates: list,
    *,
    max_quotes: int = 6,
    use_gpt: bool = True,
    cast_members: list | None = None,
) -> list:
    """
    Full pipeline: heuristic shortlist → GPT selection → heuristic merge → GPT audit.
  Falls back to heuristics if GPT is unavailable or fails.
    """
    name = (mc.get("canonical_name") or mc.get("character_name") or "").strip()
    aliases = mc.get("aliases") or []
    if not name:
        return []

    heuristic = select_appearance_quotes_from_candidates(
        candidates,
        max_quotes=max(max_quotes, 8),
        character_name=name,
        aliases=aliases,
        cast_members=cast_members,
    )

    if not use_gpt or not AITUNNEL_API_KEY:
        return heuristic[:max_quotes]

    gpt_selected = []
    try:
        gpt_pack = choose_appearance_quotes_with_gpt(book_title, [mc], {name: candidates})
        for item in gpt_pack.get("appearance", []):
            if normalize_name(item.get("canonical_name") or "") == normalize_name(name):
                gpt_selected = item.get("appearance_quotes") or []
                break
    except Exception:
        app.logger.exception("GPT appearance selection failed for %s", name)

    merged = _merge_appearance_quote_lists(
        gpt_selected,
        heuristic,
        character_name=name,
        aliases=aliases,
        cast_members=cast_members,
        max_items=max(max_quotes, 10),
    )
    if not merged:
        return []

    try:
        validated = validate_appearance_quotes_batch_with_gpt(
            book_title,
            [{"canonical_name": name, "aliases": aliases, "quotes": merged}],
            cast_members=cast_members,
        )
        final = validated.get(normalize_name(name), [])
        if final:
            return final[:max_quotes]
    except Exception:
        app.logger.exception("GPT appearance validation failed for %s", name)

    return merged[:max_quotes]


def audit_appearance_quotes_heuristic(all_chars: list | None = None) -> dict:
    """Scan all stored characters for weak/missing/suspect appearance quotes (no GPT cost)."""
    chars = all_chars if all_chars is not None else load_json(CHARACTERS_FILE, [])
    if not isinstance(chars, list):
        chars = []

    issues = []
    zero_quotes = 0
    suspect_kw = re.compile(
        r"\b(blood|bloody|Her face was|I remember her|my blood was|champing|mad with terror)\b",
        re.IGNORECASE,
    )

    cast_by_book = {}
    for rec in chars:
        if not isinstance(rec, dict):
            continue
        bid = rec.get("book_id") or ""
        cast_by_book.setdefault(bid, []).append({
            "character_name": rec.get("character_name") or "",
            "aliases": rec.get("aliases") or [],
        })

    for rec in chars:
        if not isinstance(rec, dict):
            continue
        name = (rec.get("character_name") or "").strip()
        book_id = rec.get("book_id") or ""
        aliases = rec.get("aliases") or []
        apq = rec.get("appearance_quotes") or []
        cast = cast_by_book.get(book_id) or []

        if not apq:
            zero_quotes += 1
            issues.append({
                "character_name": name,
                "book_id": book_id,
                "issue": "no_appearance_quotes",
            })
            continue

        for q in apq:
            txt = (q.get("quote") or "").strip()
            if not txt:
                continue
            if not is_portrait_worthy_quote(txt, name, aliases, cast):
                issues.append({
                    "character_name": name,
                    "book_id": book_id,
                    "issue": "fails_heuristic_filter",
                    "quote_preview": txt[:140],
                })
            elif suspect_kw.search(txt):
                issues.append({
                    "character_name": name,
                    "book_id": book_id,
                    "issue": "suspect_keywords",
                    "quote_preview": txt[:140],
                })

    by_book = {}
    for it in issues:
        bid = it.get("book_id") or "unknown"
        by_book[bid] = by_book.get(bid, 0) + 1

    return {
        "total_characters": len(chars),
        "zero_appearance_quotes": zero_quotes,
        "issue_count": len(issues),
        "issues_by_book": by_book,
        "issues": issues[:500],
    }


# -------------------- prompt builder for image generation (no extra GPT calls) --------------------
# Appended to every book-character image prompt. Models often default to film actors for famous roles.
_ANTI_CELEBRITY_BLOCK = (
    " STRICT RULES: Depict an original anonymous person who does not resemble any real celebrity, "
    "actor, model, or public figure. Do NOT copy any film, TV, stage, or book-cover adaptation, "
    "movie poster, or actor who played this character. No named-person likeness. "
    "Follow ONLY the quoted novel text below for face, hair, age, and clothing — not pop-culture memory."
)

_ANTI_HALLUCINATION_BLOCK = (
    " PORTRAIT SAFETY: Calm literary portrait — not an action scene or horror still. "
    "Do NOT add blood, gore, wounds, fangs, supernatural makeup, or victim imagery "
    "unless the quoted lines above explicitly describe THIS character's own stable features that way. "
    "Ignore horror-movie, vampire, and adaptation stereotypes not supported by the quotes."
)

# Words that are titles/particles, not identifying name tokens.
_NAME_TOKEN_STOPWORDS = {
    "the", "van", "von", "de", "la", "le", "mr", "mrs", "miss", "ms", "dr",
    "doctor", "sir", "lady", "lord", "count", "countess", "captain", "professor",
    "madame", "monsieur", "saint", "st",
}


def _strip_identity_tokens(text: str, name: str, aliases: list | None = None) -> str:
    """
    Replace the character's name / aliases with a neutral token.
    Famous names ("Dracula", "Sherlock Holmes") pull image models toward
    film-adaptation actor faces no matter what the prompt forbids, so the
    image prompt must never reveal WHO the person is.
    """
    if not text:
        return text
    tokens = set()
    for source in [name] + list(aliases or []):
        for part in re.split(r"[\s,.;:'\"]+", str(source or "").strip()):
            part = part.strip("-’'\"")
            if len(part) >= 3 and part.lower() not in _NAME_TOKEN_STOPWORDS:
                tokens.add(part)
    out = text
    for tok in sorted(tokens, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(tok)}\b", "this person", out, flags=re.IGNORECASE)
    # Collapse doubled tokens after replacement ("this person this person").
    out = re.sub(r"\b(this person)(\s+this person)+\b", r"\1", out, flags=re.IGNORECASE)
    return out


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

    # IMPORTANT: never put the character name or the novel title in the image
    # prompt. "Portrait of Dracula from the novel Dracula" makes the model
    # recall film adaptations and paint a known actor's face, overriding any
    # anti-celebrity instruction. The face must come from the quotes alone.
    header = (
        "Photorealistic head-and-shoulders portrait of an original fictional person. "
        "Their identity is unknown and must not be guessed; build the face strictly "
        "from the quoted description below"
    )

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

    char_aliases = character.get("aliases") or []

    appearance_texts = []
    for q in appearance_quotes:
        txt = (q.get("quote") or "").strip() if isinstance(q, dict) else str(q).strip()
        if txt and is_portrait_worthy_quote(txt, name, char_aliases):
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

    # compact quotes block (names stripped so the model cannot identify the role)
    quotes_part = ""
    if selected_quotes:
        anonymized = [_strip_identity_tokens(q, name, char_aliases) for q in selected_quotes]
        merged = " ".join(f"\"{q}\"" for q in anonymized)
        if len(merged) > 480:
            merged = merged[:480].rsplit(" ", 1)[0] + "…"
        quotes_part = (
            f" PRIMARY SOURCE — appearance and clothing MUST follow these lines from a classic novel only: {merged}."
        )

    if not quotes_part:
        quotes_part = (
            " No strong appearance quotes were found; invent a neutral period-appropriate look "
            "without referencing any real person or adaptation."
        )

    # soft global style hint (can be overridden on the client side if needed)
    style_hint = (
        " Photorealistic portrait of an original human being."
        " Soft natural lighting, sharp focus on face and eyes."
        " Detailed skin texture, realistic hair."
        " Clothing and era: follow the quoted lines; if unclear, use a generic"
        " 19th-century European period look."
        " Neutral painterly background, no cartoonish or illustrated look."
    )

    return header + "." + quotes_part + style_hint + _ANTI_CELEBRITY_BLOCK + _ANTI_HALLUCINATION_BLOCK


# -------------------- scene variant (same identity, new pose / emotion / setting) --------------------
MAX_REFERENCE_IMAGE_BYTES = 4 * 1024 * 1024
_SCENE_NEG_WORDS = re.compile(
    r"\b(tear|tears|cry|cries|crying|sob|sobs|sobbing|grief|sorrow|despair|"
    r"wretched|weep|weeping|distress|moan|lament)\b",
    re.I,
)


def _sanitize_scene_field(s: str, max_len: int = 280) -> str:
    if not s or not isinstance(s, str):
        return ""
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + "…"
    return s


def _decode_reference_image_base64(raw: str):
    """Returns raw bytes or None."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.startswith("data:"):
        if ";base64," not in s:
            return None
        s = s.split(";base64,", 1)[1].strip()
    try:
        out = base64.standard_b64decode(s)
        if len(out) > MAX_REFERENCE_IMAGE_BYTES:
            return None
        return out
    except Exception:
        return None


def _fetch_reference_image_from_url(url: str):
    """Download portrait bytes server-side (avoids browser CORS on provider URLs)."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        out = r.content
        if not out or len(out) > MAX_REFERENCE_IMAGE_BYTES:
            return None
        return out
    except Exception:
        return None


def _resolve_reference_image_bytes(data: dict):
    """Base64 from client first, then server-side fetch from reference_image_url."""
    ref_raw = (data.get("reference_image_base64") or "").strip()
    ref_bytes = _decode_reference_image_base64(ref_raw)
    if ref_bytes:
        return ref_bytes
    ref_url = (data.get("reference_image_url") or "").strip()
    return _fetch_reference_image_from_url(ref_url)


def _character_sort_key(c: dict):
    src = c.get("source") or ""
    role = c.get("role") or ""
    name = (c.get("character_name") or "").lower()
    src_rank = 0 if src == "gpt_prepare" else (1 if src == "user_added" else (2 if src == "verified" else 3))
    role_rank = 0 if role == "main" else 1
    return (src_rank, role_rank, name)


def _characters_for_book(book_id: str) -> list:
    all_chars = load_json(CHARACTERS_FILE, [])
    book_chars = [c for c in all_chars if c.get("book_id") == book_id]
    book_chars.sort(key=_character_sort_key)
    return book_chars


def filter_stored_appearance_quotes(character: dict, cast_members: list | None = None) -> list:
    """Drop portrait-unsafe lines already saved on a character record."""
    name = (character.get("character_name") or "").strip()
    aliases = character.get("aliases") or []
    out = []
    for q in character.get("appearance_quotes") or []:
        if not isinstance(q, dict):
            continue
        txt = (q.get("quote") or "").strip()
        if not txt:
            continue
        if not is_portrait_worthy_quote(txt, name, aliases, cast_members):
            continue
        out.append({
            "quote": txt,
            "location": (q.get("location") or "unknown").strip(),
        })
    return out


def _pick_neutral_appearance_snippet(character: dict, max_len: int = 140) -> str:
    """Prefer short appearance lines without strong distress wording (reduces 'always crying' bias)."""
    if not character:
        return ""
    name = (character.get("character_name") or "").strip()
    aliases = character.get("aliases") or []
    for q in character.get("appearance_quotes") or []:
        txt = (q.get("quote") or "").strip() if isinstance(q, dict) else str(q).strip()
        if not txt or _SCENE_NEG_WORDS.search(txt):
            continue
        if not is_portrait_worthy_quote(txt, name, aliases):
            continue
        if len(txt) > max_len:
            txt = txt[:max_len].rsplit(" ", 1)[0] + "…"
        return txt
    return ""


def build_scene_variant_prompt(
    character_name: str,
    book: dict | None,
    scene_variant: dict,
    *,
    reference_image_present: bool,
    literary_base: str,
    base_prompt_custom: str | None,
) -> str:
    """
    Same literary character, new pose/emotion/setting.
    Book characters: literary_base (full quote-first prompt) is always primary; no celebrity likeness.
  For custom portraits, base_prompt_custom carries the prior full text prompt.
    """
    emotion = _sanitize_scene_field(scene_variant.get("emotion") or "")
    pose = _sanitize_scene_field(scene_variant.get("pose") or "")
    setting = _sanitize_scene_field(scene_variant.get("setting") or "")
    notes = _sanitize_scene_field(scene_variant.get("notes") or "", 400)

    # Never name the novel or character here — famous titles/names pull the
    # model toward film-adaptation actor faces (see build_auto_description).
    ctx = "Set in a period-appropriate world consistent with the description below. "

    if reference_image_present:
        identity_lock = (
            "CRITICAL — IDENTITY: Keep a consistent original fictional face (not a celebrity). "
            "Preserve general age, era, hair color, and bone structure only if they match the novel text below. "
            "Change expression, pose, framing, lighting, and background as directed. "
            "Never imitate a real actor or film still."
        )
    else:
        identity_lock = (
            "CRITICAL — IDENTITY: Same original fictional character across images. "
            "Face and wardrobe must match the novel text below, not any adaptation. "
            "Vary only expression, pose, setting, and lighting as directed."
        )

    changes = []
    if emotion:
        changes.append(f"Facial expression / emotion: {emotion}")
    if pose:
        changes.append(f"Pose and body language: {pose}")
    if setting:
        changes.append(f"Environment / location: {setting}")
    if notes:
        changes.append(f"Additional direction: {notes}")
    if not changes:
        changes.append(
            "Subtle variation only: calm neutral expression, slight change in head tilt and shoulders, refined lighting."
        )
    changes_txt = "\n".join(f"- {c}" for c in changes)

    literary_part = ""
    if literary_base:
        literary_part = f"\nNOVEL-GROUNDED BASE (highest priority):\n{literary_base}\n"

    custom_part = ""
    if base_prompt_custom:
        bp = base_prompt_custom.strip()
        if len(bp) > 900:
            bp = bp[:900].rsplit(" ", 1)[0] + "…"
        custom_part = (
            " Prior portrait prompt for this same character (keep their look consistent): "
            + bp
        )

    style_hint = (
        " Photorealistic cinematic portrait, detailed skin texture, realistic hair, natural soft light, "
        "sharp focus on eyes, period-appropriate wardrobe when relevant. No cartoon or illustration style."
    )

    header = f"Portrait of the same original fictional person as before. {ctx}".strip()
    return (
        f"{header}\n{identity_lock}\n"
        f"Vary the scene as follows:\n{changes_txt}"
        f"{literary_part}{custom_part}{style_hint}{_ANTI_CELEBRITY_BLOCK}{_ANTI_HALLUCINATION_BLOCK}"
    )


def _extract_image_url_from_provider_json(img_data) -> str | None:
    image_url = None
    arr = (img_data.get("data") if isinstance(img_data, dict) else None) or []
    if isinstance(arr, list) and arr and isinstance(arr[0], dict):
        item = arr[0]
        if item.get("url"):
            image_url = str(item["url"])
        elif item.get("b64_json"):
            mime = item.get("mime_type") or item.get("content_type") or "image/png"
            image_url = f"data:{mime};base64,{item['b64_json']}"
    if not image_url and isinstance(img_data, dict):
        image_url = img_data.get("image_url") or img_data.get("url")
    return image_url


def _portrait_filename(character_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", (character_id or "").strip())
    return (safe or "portrait") + ".jpg"


def _portrait_public_path(character_id: str) -> str:
    return f"/api/portraits/{_portrait_filename(character_id)}"


def _get_canonical_portrait_url(character_id: str) -> str | None:
    """Shared portrait for a book character — same image for all visitors."""
    if not character_id:
        return None
    all_chars = load_json(CHARACTERS_FILE, [])
    ch = next((c for c in all_chars if c.get("character_id") == character_id), None)
    if not ch:
        return None
    url = (ch.get("canonical_portrait_url") or "").strip()
    if not url:
        return None
    if url.startswith("/api/portraits/"):
        disk_path = os.path.join(PORTRAITS_DIR, os.path.basename(url))
        if os.path.isfile(disk_path):
            return url
        return None
    return url


def _set_canonical_portrait(character_id: str, image_url: str, prompt_hash: str) -> str:
    """Save portrait bytes on disk and store stable URL on the character record."""
    if not character_id or not image_url:
        return image_url
    # Once a shared canonical exists, never overwrite (Regenerate / personal variants must not change it).
    existing = _get_canonical_portrait_url(character_id)
    if existing:
        return existing
    filename = _portrait_filename(character_id)
    disk_path = os.path.join(PORTRAITS_DIR, filename)
    try:
        if image_url.startswith("data:") and ";base64," in image_url:
            raw = base64.standard_b64decode(image_url.split(";base64,", 1)[1])
        elif image_url.startswith(("http://", "https://")):
            r = requests.get(image_url, timeout=90)
            r.raise_for_status()
            raw = r.content
        elif image_url.startswith("/api/portraits/"):
            return image_url
        else:
            return image_url
        if not raw or len(raw) > 8 * 1024 * 1024:
            return image_url
        with open(disk_path, "wb") as f:
            f.write(raw)
    except Exception:
        app.logger.exception("canonical portrait persist failed for character_id=%s", character_id)
        return image_url

    public_url = _portrait_public_path(character_id)
    all_chars = load_json(CHARACTERS_FILE, [])
    for rec in all_chars:
        if rec.get("character_id") == character_id:
            rec["canonical_portrait_url"] = public_url
            rec["canonical_portrait_prompt_hash"] = prompt_hash
            rec["canonical_portrait_at"] = datetime.now(timezone.utc).isoformat()
            break
    save_json(CHARACTERS_FILE, all_chars)
    return public_url


def _clear_canonical_portrait(character_id: str) -> bool:
    """Remove shared portrait for a book character so the next Generate creates a new one."""
    if not character_id:
        return False
    all_chars = load_json(CHARACTERS_FILE, [])
    found = False
    for rec in all_chars:
        if rec.get("character_id") != character_id:
            continue
        found = True
        url = (rec.get("canonical_portrait_url") or "").strip()
        if url.startswith("/api/portraits/"):
            disk_path = os.path.join(PORTRAITS_DIR, os.path.basename(url))
            try:
                if os.path.isfile(disk_path):
                    os.remove(disk_path)
            except OSError:
                app.logger.exception("failed to delete canonical portrait file for %s", character_id)
        rec.pop("canonical_portrait_url", None)
        rec.pop("canonical_portrait_prompt_hash", None)
        rec.pop("canonical_portrait_at", None)
        break
    if not found:
        return False
    save_json(CHARACTERS_FILE, all_chars)
    return True


def _call_image_provider(prompt: str, reference_bytes=None) -> str:
    image_model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview").strip()
    image_size = os.getenv("IMAGE_SIZE", "1024x1536").strip()
    if not AITUNNEL_API_KEY or not AITUNNEL_BASE_URL:
        raise RuntimeError("Image generation not configured (API key/base url missing)")
    img_endpoint = f"{AITUNNEL_BASE_URL.rstrip('/')}/images/generations"
    headers = {"Authorization": f"Bearer {AITUNNEL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": image_model, "prompt": prompt, "n": 1, "size": image_size}
    ref_field = os.getenv("IMAGE_REFERENCE_BASE64_FIELD", "").strip()
    if reference_bytes and ref_field:
        payload[ref_field] = base64.standard_b64encode(reference_bytes).decode("ascii")
    img_resp = requests.post(img_endpoint, headers=headers, json=payload, timeout=240)
    img_resp.raise_for_status()
    img_data = img_resp.json()
    image_url = _extract_image_url_from_provider_json(img_data)
    if not image_url:
        raise RuntimeError(
            f"Image generation returned no image url (keys: {list(img_data.keys()) if isinstance(img_data, dict) else type(img_data).__name__})"
        )
    return image_url


# -------------------- routes --------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/portraits/<path:filename>", methods=["GET"])
def api_serve_portrait(filename):
    if not re.fullmatch(r"[\w.-]+\.jpg", filename or ""):
        return ("", 404)
    disk_path = os.path.join(PORTRAITS_DIR, filename)
    if not os.path.isfile(disk_path):
        return ("", 404)
    resp = make_response(send_file(disk_path, mimetype="image/jpeg"))
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


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


def _book_matches_query(query_lower: str, book: dict) -> bool:
    """Substring on title/author, or all significant tokens present (e.g. 'war peace' → War and Peace)."""
    if not query_lower:
        return True
    t = (book.get("title") or "").lower()
    a = (book.get("author") or "").lower()
    combined = f"{t} {a}"
    if query_lower in t or query_lower in a:
        return True
    parts = [p for p in query_lower.split() if len(p) >= 2]
    if len(parts) >= 2:
        return all(p in combined for p in parts)
    return False


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
        filtered = [b for b in result if _book_matches_query(query, b)]
        if not filtered and mode == "curated":
            extra = []
            seen = set()
            for full in all_books:
                bid = full.get("book_id")
                if not bid or bid in seen or not full.get("text_url"):
                    continue
                if not _book_matches_query(query, full):
                    continue
                seen.add(bid)
                extra.append({
                    "book_id": bid,
                    "title": full.get("title"),
                    "author": full.get("author"),
                    "year": full.get("year"),
                    "source": full.get("source") or "gutenberg",
                    "text_url": full.get("text_url"),
                    "popularity_score": int(full.get("download_count") or 0),
                })
            extra.sort(key=lambda b: (b.get("popularity_score", 0), (b.get("title") or "")), reverse=True)
            result = extra[:limit]
        else:
            result = filtered[:limit]
    else:
        result = result[:limit]

    return jsonify({"success": True, "books": result, "count": len(result)})


@app.route("/api/characters", methods=["GET"])
def api_characters():
    book_id = request.args.get("book_id")
    if not book_id:
        return jsonify({"success": False, "error": "book_id required"}), 400

    book_chars = _characters_for_book(book_id)
    resp = make_response(jsonify({"success": True, "characters": book_chars, "count": len(book_chars)}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


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

    # cache — return ALL prepared characters (gpt_prepare + user_added), not gpt_prepare only
    all_chars = load_json(CHARACTERS_FILE, [])
    existing_prepared = [c for c in all_chars if c.get("book_id") == book_id and c.get("source") == "gpt_prepare"]
    if existing_prepared and not overwrite:
        book_chars = _characters_for_book(book_id)
        return jsonify({
            "success": True,
            "cached": True,
            "count": len(book_chars),
            "eta_seconds": 0,
            "characters": book_chars
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
        app.logger.exception("prepare_book: failed to download text for book_id=%s", book_id)
        return jsonify({"success": False, "error": f"Failed to download text: {str(e)}"}), 500

    # candidates
    raw = extract_candidates_from_text(text, book.get("title", ""))

    # STEP A: main chars by GPT
    try:
        preparedA = prepare_main_characters(book.get("title", ""), text, raw, main_limit=main_limit)
    except Exception as e:
        app.logger.exception("prepare_book: GPT prepare failed for book_id=%s", book_id)
        return jsonify({"success": False, "error": f"GPT prepare failed: {str(e)}"}), 500

    main_chars = preparedA.get("main_characters", [])
    if not isinstance(main_chars, list):
        return jsonify({"success": False, "error": "Bad GPT response (main_characters)"}), 500

    enrich_cross_spell_aliases(main_chars)

    # STEP A-b: evidence quotes from code (guaranteed to contain character name)
    evidence_map = extract_evidence_quotes_from_text(text, main_chars, max_per_char=4)
    for mc in main_chars:
        cname = (mc.get("canonical_name") or "").strip()
        mc["evidence_quotes"] = evidence_map.get(cname, [])

    # STEP B: appearance candidates from FULL text
    appearance_candidates_map = build_appearance_candidates(text, main_chars, max_per_char=28)

    # STEP C: heuristic shortlist + GPT selection + GPT audit (double AI check when API key set).
    use_gpt = bool(data.get("use_gpt", True))
    book_title = book.get("title") or ""
    chosen_map = {}
    for mc in main_chars:
        name_key = (mc.get("canonical_name") or "").strip()
        canonical = normalize_name(name_key)
        candidates = appearance_candidates_map.get(name_key, []) if name_key else []
        chosen_map[canonical] = resolve_appearance_quotes_for_character(
            book_title,
            mc,
            candidates,
            max_quotes=6,
            use_gpt=use_gpt,
        ) if canonical else []

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
                    if not is_portrait_worthy_quote(quote_text, canonical, aliases_norm):
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
        "use_gpt": use_gpt,
        "characters": saved
    })


@app.route("/api/audit_appearance_quotes", methods=["GET"])
def api_audit_appearance_quotes():
    """Heuristic audit of all stored appearance quotes (no GPT cost)."""
    book_id = (request.args.get("book_id") or "").strip()
    all_chars = load_json(CHARACTERS_FILE, [])
    if book_id:
        all_chars = [c for c in all_chars if c.get("book_id") == book_id]
    report = audit_appearance_quotes_heuristic(all_chars)
    return jsonify({"success": True, **report})


@app.route("/api/sanitize_appearance_quotes", methods=["POST"])
def api_sanitize_appearance_quotes():
    """
    Re-filter appearance_quotes already stored in characters.json (no book re-download).
    Heuristic pass always; optional GPT audit pass when use_gpt=true and API key is set.
    """
    data = request.get_json(silent=True) or {}
    book_id = (data.get("book_id") or "").strip()
    use_gpt = bool(data.get("use_gpt", False))

    all_books = load_json(BOOKS_FILE, [])
    books_by_id = {b.get("book_id"): b for b in all_books if b.get("book_id")}

    all_chars = load_json(CHARACTERS_FILE, [])
    characters_updated = 0
    quotes_removed = 0
    gpt_validated = 0

    targets = [c for c in all_chars if not book_id or c.get("book_id") == book_id]
    by_book = {}
    for rec in targets:
        bid = rec.get("book_id") or ""
        by_book.setdefault(bid, []).append(rec)

    for bid, recs in by_book.items():
        book = books_by_id.get(bid) or {}
        book_title = book.get("title") or bid or "Unknown book"
        cast = [
            {"character_name": r.get("character_name") or "", "aliases": r.get("aliases") or []}
            for r in recs
        ]
        gpt_batch = None
        if use_gpt and AITUNNEL_API_KEY:
            try:
                gpt_batch = validate_appearance_quotes_batch_with_gpt(
                    book_title,
                    [
                        {
                            "canonical_name": r.get("character_name") or "",
                            "aliases": r.get("aliases") or [],
                            "quotes": filter_stored_appearance_quotes(r, cast),
                        }
                        for r in recs
                    ],
                    cast_members=cast,
                )
            except Exception:
                app.logger.exception("GPT sanitize batch failed for book_id=%s", bid)

        for rec in recs:
            before = len(rec.get("appearance_quotes") or [])
            filtered = filter_stored_appearance_quotes(rec, cast)
            norm = normalize_name(rec.get("character_name") or "")
            if gpt_batch is not None and norm in gpt_batch:
                filtered = gpt_batch[norm]
                gpt_validated += 1
            old_texts = {
                (q.get("quote") or "").strip()
                for q in (rec.get("appearance_quotes") or [])
                if isinstance(q, dict)
            }
            new_texts = {
                (q.get("quote") or "").strip()
                for q in filtered
                if isinstance(q, dict) and (q.get("quote") or "").strip()
            }
            if new_texts != old_texts:
                rec["appearance_quotes"] = filtered
                characters_updated += 1
                quotes_removed += max(0, before - len(filtered))

    if characters_updated:
        save_json(CHARACTERS_FILE, all_chars)

    return jsonify({
        "success": True,
        "characters_updated": characters_updated,
        "quotes_removed": quotes_removed,
        "gpt_validated_characters": gpt_validated,
        "book_id": book_id or None,
    })


@app.route("/api/reselect_appearance_quotes", methods=["POST"])
def api_reselect_appearance_quotes():
    """
    Re-run appearance-quote selection from book text.
    Default: heuristic + GPT selection + GPT audit (use_gpt=false for heuristics only).
    """
    data = request.get_json(silent=True) or {}
    book_id = (data.get("book_id") or "").strip()
    max_per_char = int(data.get("max_per_char") or 28)
    max_quotes = int(data.get("max_quotes") or 6)
    use_gpt = bool(data.get("use_gpt", True))

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

    cast_members = [
        {"character_name": mc.get("canonical_name") or "", "aliases": mc.get("aliases") or []}
        for mc in builder_chars
    ]

    book_title = book.get("title") or ""
    chosen_map = {}
    for mc in builder_chars:
        name_key = (mc.get("canonical_name") or "").strip()
        canonical = normalize_name(name_key)
        candidates = appearance_candidates_map.get(name_key, []) if name_key else []
        chosen_map[canonical] = resolve_appearance_quotes_for_character(
            book_title,
            mc,
            candidates,
            max_quotes=max_quotes,
            use_gpt=use_gpt,
            cast_members=cast_members,
        ) if canonical else []

    # Deep pass: many classic descriptions use only pronouns ("her dark eyes"),
    # which the name-anchored candidate search can never attribute. GPT reads
    # the full text in chunks and copies verbatim passages for thin characters.
    deep = bool(data.get("deep", True)) and use_gpt and bool(AITUNNEL_API_KEY)
    if deep:
        needy = [
            mc for mc in builder_chars
            if len(chosen_map.get(normalize_name((mc.get("canonical_name") or "").strip()), [])) < 2
        ]
        if needy:
            try:
                deep_map = extract_appearance_quotes_with_gpt_fulltext(
                    book_title, text, needy, max_quotes_per_char=max_quotes,
                )
            except Exception:
                app.logger.exception("deep quote extraction failed for %s", book_id)
                deep_map = {}
            for mc in needy:
                name_key = (mc.get("canonical_name") or "").strip()
                canonical = normalize_name(name_key)
                aliases = mc.get("aliases") or []
                extra = deep_map.get(canonical) or []
                if not extra:
                    continue
                existing = chosen_map.get(canonical, [])
                combined = list(existing)
                for q in extra:
                    txt = (q.get("quote") or "").strip()
                    if not txt or not is_portrait_worthy_quote(txt, name_key, aliases, cast_members):
                        continue
                    key = _normalize_for_verbatim(txt)
                    if not key:
                        continue
                    if any(
                        key in _normalize_for_verbatim(b.get("quote", ""))
                        or _normalize_for_verbatim(b.get("quote", "")) in key
                        for b in combined
                    ):
                        continue
                    combined.append(q)
                chosen_map[canonical] = combined[:max_quotes]

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
    return jsonify({"success": True, "updated": updated, "use_gpt": use_gpt})


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
    chosen_map[canonical] = resolve_appearance_quotes_for_character(
        book.get("title") or "",
        single_char[0],
        candidates,
        max_quotes=6,
        use_gpt=bool(AITUNNEL_API_KEY),
    ) if canonical else []

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


def _api_generate_scene_variant(data: dict):
    """New pose / emotion / setting while trying to keep the same face (prompt + optional reference image bytes)."""
    scene_variant = data.get("scene_variant") or {}
    if not isinstance(scene_variant, dict) or not scene_variant:
        return jsonify({"success": False, "error": "scene_variant object required"}), 400

    emotion = _sanitize_scene_field(scene_variant.get("emotion") or "")
    pose = _sanitize_scene_field(scene_variant.get("pose") or "")
    setting = _sanitize_scene_field(scene_variant.get("setting") or "")
    notes = _sanitize_scene_field(scene_variant.get("notes") or "", 400)
    if not any([emotion, pose, setting, notes]):
        return jsonify({
            "success": False,
            "error": "Add at least one of: emotion, pose, setting, or notes",
        }), 400

    character_id = (data.get("character_id") or "").strip()
    character_name = (data.get("character_name") or "").strip()
    base_prompt_custom = (data.get("base_prompt") or "").strip()

    ref_bytes = _resolve_reference_image_bytes(data)

    ch = None
    book = None
    if character_id:
        all_chars = load_json(CHARACTERS_FILE, [])
        ch = next((c for c in all_chars if c.get("character_id") == character_id), None)
        if not ch:
            return jsonify({"success": False, "error": "character_id not found"}), 404
        book = find_book_by_id(ch.get("book_id"))
        if not character_name:
            character_name = (ch.get("character_name") or "").strip()

    if not character_name:
        return jsonify({"success": False, "error": "character_name required"}), 400

    if not character_id and not base_prompt_custom:
        return jsonify({"success": False, "error": "base_prompt required for custom scene variant"}), 400

    literary_base = ""
    if ch:
        literary_base = build_auto_description_from_character(book, ch)

    # Quote-first book characters: do not send a reference image to the provider.
    # Reference locks in celebrity faces from prior bad generations / model bias.
    provider_ref_bytes = None if character_id else ref_bytes

    description = build_scene_variant_prompt(
        character_name,
        book,
        scene_variant,
        reference_image_present=bool(provider_ref_bytes),
        literary_base=literary_base,
        base_prompt_custom=base_prompt_custom if not character_id else None,
    )

    user_id = get_user_id(request)
    force_new = bool(data.get("force_new"))

    remaining, limit_resp = charge_generation_or_limit_response(user_id)
    if limit_resp:
        return limit_resp

    prompt_hash = hashlib.md5(
        ("scene_variant:" + description + json.dumps(scene_variant, sort_keys=True)).encode("utf-8")
    ).hexdigest()
    normalized_char_id = character_id or None

    if not force_new:
        try:
            history_items = load_json(HISTORY_FILE, [])
            if isinstance(history_items, list):
                for rec in reversed(history_items):
                    if not isinstance(rec, dict):
                        continue
                    if rec.get("user_id") != user_id:
                        continue
                    rec_char_id = rec.get("character_id") or None
                    if rec_char_id != normalized_char_id:
                        continue
                    if rec.get("prompt_hash") == prompt_hash:
                        image_url = rec.get("image_url")
                        if image_url:
                            resp = make_response(jsonify({
                                "success": True,
                                "image_url": image_url,
                                "character_name": rec.get("character_name") or character_name,
                                "remaining_free_count": remaining,
                                "cached": True,
                                "scene_variant": True,
                            }))
                            if not request.cookies.get("user_id"):
                                resp.set_cookie("user_id", user_id, max_age=365 * 24 * 60 * 60)
                            return resp
        except Exception:
            pass

    try:
        image_url = _call_image_provider(description, provider_ref_bytes)
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        app.logger.exception("scene_variant: provider failed for character_name=%s", character_name)
        return jsonify({"success": False, "error": f"Image generation failed: {type(e).__name__}: {str(e)}"}), 500

    source_type = "book" if character_id else "custom"
    history_record = {
        "id": str(uuid.uuid4()),
        "source_type": source_type,
        "character_id": character_id or None,
        "character_name": character_name,
        "description": description,
        "prompt_hash": prompt_hash,
        "image_url": image_url,
        "generation_kind": "scene_variant",
        "scene_variant": scene_variant,
    }
    try:
        append_history_record(user_id, history_record)
    except Exception:
        pass

    resp = make_response(jsonify({
        "success": True,
        "image_url": image_url,
        "character_name": character_name,
        "remaining_free_count": remaining,
        "scene_variant": True,
    }))

    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", user_id, max_age=365 * 24 * 60 * 60)

    return resp


@app.route("/api/reset_canonical_portrait", methods=["POST"])
def api_reset_canonical_portrait():
    """Clear the shared site-wide portrait for a book character (bad face stuck on canonical).

    Accepts one of:
      {"character_id": "..."}  — reset one character
      {"book_id": "..."}       — reset every character of a book
      {"all": true}            — reset every canonical portrait (e.g. after a prompt fix)
    """
    data = request.get_json(silent=True) or {}
    character_id = (data.get("character_id") or "").strip()
    book_id = (data.get("book_id") or "").strip()
    reset_all = bool(data.get("all"))

    if character_id:
        ok = _clear_canonical_portrait(character_id)
        if not ok:
            return jsonify({"success": False, "error": "Character not found or no canonical portrait"}), 404
        return jsonify({"success": True, "character_id": character_id})

    if book_id or reset_all:
        all_chars = load_json(CHARACTERS_FILE, [])
        targets = [
            c.get("character_id")
            for c in all_chars
            if c.get("canonical_portrait_url")
            and (reset_all or c.get("book_id") == book_id)
        ]
        cleared = sum(1 for cid in targets if cid and _clear_canonical_portrait(cid))
        return jsonify({"success": True, "cleared": cleared})

    return jsonify({"success": False, "error": "character_id, book_id, or all required"}), 400


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}

    scene_variant = data.get("scene_variant")
    if isinstance(scene_variant, dict) and scene_variant:
        return _api_generate_scene_variant(data)

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
    force_new = bool(data.get("force_new"))

    remaining, limit_resp = charge_generation_or_limit_response(user_id)
    if limit_resp:
        return limit_resp

    prompt_hash = hashlib.md5(description.encode("utf-8")).hexdigest()
    normalized_char_id = character_id or None

    # Global canonical portrait: one face per book character for all visitors (unless Regenerate).
    if normalized_char_id and not force_new:
        canonical_url = _get_canonical_portrait_url(normalized_char_id)
        if canonical_url:
            resp = make_response(jsonify({
                "success": True,
                "image_url": canonical_url,
                "character_name": character_name,
                "remaining_free_count": remaining,
                "cached": True,
                "canonical": True,
            }))
            if not request.cookies.get("user_id"):
                resp.set_cookie("user_id", user_id, max_age=365 * 24 * 60 * 60)
            return resp

    # Per-user history cache (same browser, same prompt).
    # Skip when force_new=true (Regenerate button).
    if not force_new:
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
                            resp = make_response(jsonify({
                                "success": True,
                                "image_url": image_url,
                                "character_name": rec.get("character_name") or character_name,
                                "remaining_free_count": remaining,
                                "cached": True,
                            }))
                            if not request.cookies.get("user_id"):
                                resp.set_cookie("user_id", user_id, max_age=365 * 24 * 60 * 60)
                            return resp
                    rec_desc = (rec.get("description") or "").strip()
                    if rec_desc and hashlib.md5(rec_desc.encode("utf-8")).hexdigest() == prompt_hash:
                        image_url = rec.get("image_url")
                        if image_url:
                            resp = make_response(jsonify({
                                "success": True,
                                "image_url": image_url,
                                "character_name": rec.get("character_name") or character_name,
                                "remaining_free_count": remaining,
                                "cached": True,
                            }))
                            if not request.cookies.get("user_id"):
                                resp.set_cookie("user_id", user_id, max_age=365 * 24 * 60 * 60)
                            return resp
        except Exception:
            # Cache failure should not break generation flow.
            pass

    try:
        image_url = _call_image_provider(description, None)
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        app.logger.exception("generate: image provider request failed for character_name=%s", character_name)
        return jsonify({"success": False, "error": f"Image generation failed: {type(e).__name__}: {str(e)}"}), 500

    # Canonical portrait: only the first successful Generate (not Regenerate) for all visitors.
    if normalized_char_id and not force_new:
        image_url = _set_canonical_portrait(normalized_char_id, image_url, prompt_hash)

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

    payload = {
        "success": True,
        "image_url": image_url,
        "character_name": character_name,
        "remaining_free_count": remaining,
    }
    if force_new:
        payload["personal_variant"] = True

    resp = make_response(jsonify(payload))

    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", user_id, max_age=365*24*60*60)

    return resp


if __name__ == "__main__":
    # на ноуте: http://127.0.0.1:5000
    # на телефоне в Wi-Fi: http://192.168.0.16:5000 (твой IP будет свой)
    app.run(debug=False, host="0.0.0.0", port=5000)