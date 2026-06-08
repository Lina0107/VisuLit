#!/usr/bin/env python3
"""
Audit and optionally clean appearance_quotes in data/characters.json.

Usage:
  python scripts/sanitize_character_quotes.py          # audit only
  python scripts/sanitize_character_quotes.py --write  # save cleaned JSON
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    CHARACTERS_FILE,
    build_auto_description_from_character,
    filter_stored_appearance_quotes,
    find_book_by_id,
    is_portrait_worthy_quote,
    load_json,
    save_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit/clean stored appearance quotes")
    parser.add_argument("--write", action="store_true", help="Save filtered quotes to characters.json")
    args = parser.parse_args()

    chars = load_json(CHARACTERS_FILE, [])
    if not isinstance(chars, list):
        print("ERROR: characters.json is not a list")
        return 1

    removed_examples: list[str] = []
    empty_after: list[str] = []
    changed = 0
    removed_total = 0

    for rec in chars:
        if not isinstance(rec, dict):
            continue
        name = (rec.get("character_name") or "").strip()
        aliases = rec.get("aliases") or []
        before = rec.get("appearance_quotes") or []
        bad = []
        for q in before:
            if not isinstance(q, dict):
                continue
            txt = (q.get("quote") or "").strip()
            if txt and not is_portrait_worthy_quote(txt, name, aliases):
                bad.append(txt)

        filtered = filter_stored_appearance_quotes(rec)
        if bad:
            changed += 1
            removed_total += len(bad)
            for txt in bad[:2]:
                removed_examples.append(f"{name}: {txt[:110]}…")

        if args.write:
            rec["appearance_quotes"] = filtered

        if not filtered and before:
            empty_after.append(name)

    print(f"Characters with bad quotes: {changed}")
    print(f"Quotes to remove: {removed_total}")
    if empty_after:
        print(f"Would have 0 appearance quotes after clean ({len(empty_after)}): {', '.join(empty_after[:12])}")
        if len(empty_after) > 12:
            print(f"  … and {len(empty_after) - 12} more")

    if removed_examples:
        print("\nExamples removed:")
        for line in removed_examples[:20]:
            print(f"  - {line}")
        if len(removed_examples) > 20:
            print(f"  … and {len(removed_examples) - 20} more")

    # Sample prompts for main gallery characters
    print("\nSample prompts (first 220 chars):")
    gallery_names = {
        "Elizabeth Bennet", "Mr. Darcy", "Count Dracula", "Jane Eyre",
        "Rochester", "Dorian Gray", "Jo March",
    }
    for rec in chars:
        name = (rec.get("character_name") or "").strip()
        if name not in gallery_names:
            continue
        book = find_book_by_id(rec.get("book_id") or "")
        prompt = build_auto_description_from_character(book or {}, rec)
        print(f"\n[{name}] quotes={len(rec.get('appearance_quotes') or [])}")
        print(prompt[:320] + ("…" if len(prompt) > 320 else ""))

    if args.write:
        save_json(CHARACTERS_FILE, chars)
        print(f"\nWrote cleaned quotes to {CHARACTERS_FILE}")
    else:
        print("\nDry run only. Re-run with --write to update characters.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
