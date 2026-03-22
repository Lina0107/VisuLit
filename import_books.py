import json
import os
import time
import requests

DATA_DIR = "data"
BOOKS_FILE = os.path.join(DATA_DIR, "books.json")

GUTENDEX_BASE = "https://gutendex.com/books"
DEFAULT_LANG = "en"

# Сколько книг тянуть (примерно). Можно 500, 1000, 3000
TARGET_COUNT = 1000

# Чтобы не долбить API слишком быстро
SLEEP_BETWEEN_REQUESTS_SEC = 0.2


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def load_existing_books():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BOOKS_FILE):
        return []
    with open(BOOKS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_books(books):
    with open(BOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)


def pick_best_text_url(formats: dict) -> str | None:
    """
    Предпочитаем plain text UTF-8 (без .zip).
    Gutendex formats keys примеры:
    - 'text/plain; charset=utf-8'
    - 'text/plain'
    - 'text/plain; charset=us-ascii'
    Также бывают html/epub и т.п.
    """
    if not formats:
        return None

    preferred_keys = [
        "text/plain; charset=utf-8",
        "text/plain; charset=us-ascii",
        "text/plain",
    ]

    # сначала идеальные варианты
    for k in preferred_keys:
        url = formats.get(k)
        if url and isinstance(url, str) and not url.lower().endswith(".zip"):
            return url

    # иначе — любой text/plain не zip
    for k, url in formats.items():
        if not isinstance(url, str):
            continue
        if k.startswith("text/plain") and not url.lower().endswith(".zip"):
            return url

    return None


def normalize_book(item: dict) -> dict:
    """
    Приводим к твоему формату books.json
    """
    authors = item.get("authors") or []
    author_name = authors[0].get("name") if authors else "Unknown"

    # Gutendex id — число. Сделаем стабильный book_id
    gid = safe_int(item.get("id"))
    title = (item.get("title") or "").strip() or f"Gutenberg #{gid}"

    # year из Gutendex напрямую нет. Оставим None.
    # Позже можно вычислять по author death_year / subject, но это не обязательно для старта.
    year = None

    formats = item.get("formats") or {}
    text_url = pick_best_text_url(formats)

    return {
        "book_id": f"gutenberg-{gid}",
        "title": title,
        "author": author_name,
        "year": year,
        "source": "gutenberg",
        "has_verified_characters": False,
        "suitability_score": 0.6,  # базово; позже сделаем AI-скоринг
        "language": DEFAULT_LANG,
        "gutenberg_id": gid,
        "download_count": safe_int(item.get("download_count")),
        "text_url": text_url,   # пригодится позже для извлечения персонажей
    }


def fetch_page(url: str) -> dict:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    existing = load_existing_books()
    by_id = {b.get("book_id"): b for b in existing if b.get("book_id")}

    added = 0
    url = f"{GUTENDEX_BASE}?languages={DEFAULT_LANG}"

    print("Starting import from Gutendex…")
    print("Existing books:", len(by_id))

    while url and len(by_id) < TARGET_COUNT:
        data = fetch_page(url)
        results = data.get("results") or []

        for item in results:
            book = normalize_book(item)
            bid = book["book_id"]
            if bid in by_id:
                continue

            # фильтр: если нет text_url, всё равно добавляем (можно убрать если хочешь)
            by_id[bid] = book
            added += 1

            if len(by_id) >= TARGET_COUNT:
                break

        url = data.get("next")  # пагинация Gutendex
        print(f"Imported: {len(by_id)} (+{added}), next={bool(url)}")

        time.sleep(SLEEP_BETWEEN_REQUESTS_SEC)

    books = list(by_id.values())
    # сортировка: самые популярные (download_count) наверх
    books.sort(key=lambda b: b.get("download_count", 0), reverse=True)

    save_books(books)
    print("DONE. Total books saved:", len(books))
    print("Saved to:", BOOKS_FILE)


if __name__ == "__main__":
    main()
