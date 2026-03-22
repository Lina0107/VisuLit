import json
import os
import sys
import time
from typing import Any

import requests


ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
CURATED_BOOKS = os.path.join(DATA_DIR, "curated_books.json")


def _load_json(path: str, default: Any):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main() -> int:
    api_base = os.environ.get("API_BASE", "http://127.0.0.1:5000")
    main_limit = int(os.environ.get("MAIN_LIMIT", "18"))

    books = _load_json(CURATED_BOOKS, [])
    if not books:
        print(f"ERROR: No curated books found at {CURATED_BOOKS}")
        return 2

    session = requests.Session()
    ok = 0
    fail = 0

    for idx, b in enumerate(books, start=1):
        book_id = b.get("book_id")
        title = b.get("title") or ""
        if not book_id:
            continue

        print(f"[{idx}/{len(books)}] Preparing: {title} ({book_id})")
        try:
            r = session.post(
                f"{api_base}/api/prepare_book",
                json={"book_id": book_id, "overwrite": True, "main_limit": main_limit},
                timeout=600,
            )
            data = r.json()
            if r.status_code == 200 and data.get("success"):
                ok += 1
                print(f"  OK: {data.get('count', 0)} characters (cached={data.get('cached')})")
            else:
                fail += 1
                print(f"  FAIL: HTTP {r.status_code} {data}")
        except Exception as e:
            fail += 1
            print(f"  FAIL: {type(e).__name__}: {e}")

        time.sleep(0.25)

    print(f"\nDone. OK={ok} FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

