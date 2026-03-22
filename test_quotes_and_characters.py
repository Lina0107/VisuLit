#!/usr/bin/env python3
"""
Тест цитат и персонажей: отчёт по подготовленным книгам.
Запуск: python test_quotes_and_characters.py
(Сервер app.py может быть выключен — скрипт читает только data/.)

Опционально: python test_quotes_and_characters.py --prepare gutenberg-1342 gutenberg-1260
  — сначала вызовет POST /api/prepare_book для этих книг (сервер должен быть запущен), потом отчёт.
"""

import json
import os
import sys

DATA_DIR = "data"
BOOKS_FILE = os.path.join(DATA_DIR, "books.json")
CURATED_FILE = os.path.join(DATA_DIR, "curated_books.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default


def book_title(book_id, books, curated):
    for b in curated:
        if b.get("book_id") == book_id:
            return b.get("title") or book_id
    for b in books:
        if b.get("book_id") == book_id:
            return b.get("title") or book_id
    return book_id


def run_report():
    books = load_json(BOOKS_FILE, [])
    curated = load_json(CURATED_FILE, [])
    characters = load_json(CHARACTERS_FILE, [])

    # Группируем по book_id только gpt_prepare
    by_book = {}
    for c in characters:
        if c.get("source") != "gpt_prepare":
            continue
        bid = c.get("book_id")
        if not bid:
            continue
        by_book.setdefault(bid, []).append(c)

    if not by_book:
        print("Нет подготовленных книг (source=gpt_prepare).")
        print("Сначала в интерфейсе: выбери книгу → Overwrite → Prepare book.")
        print("Или: python test_quotes_and_characters.py --prepare gutenberg-1342 gutenberg-1260")
        return

    for bid in sorted(by_book.keys()):
        title = book_title(bid, books, curated)
        chars = by_book[bid]
        chars = sorted(chars, key=lambda x: (x.get("character_name") or "").lower())
        print()
        print("=" * 60)
        print(f"  {title}  ({bid})")
        print(f"  Персонажей: {len(chars)}")
        print("=" * 60)
        for c in chars:
            name = c.get("character_name") or "—"
            ev = c.get("evidence_quotes") or []
            ap = c.get("appearance_quotes") or []
            print(f"\n  • {name}")
            print(f"    evidence: {len(ev)}, appearance: {len(ap)}")
            if ev:
                first_ev = (ev[0].get("quote") or "")[:120]
                print(f"    evidence[0]: {first_ev}…" if len(first_ev) >= 120 else f"    evidence[0]: {first_ev}")
            if ap:
                first_ap = (ap[0].get("quote") or "")[:120]
                print(f"    appearance[0]: {first_ap}…" if len(first_ap) >= 120 else f"    appearance[0]: {first_ap}")
            elif not ap and (ev or name):
                print("    appearance[0]: (нет)")
        print()
    print("Готово. Проверь: evidence — с именем персонажа; appearance — про внешность (не 'I remember her...').")
    print("\nЧтобы переподготовить с бОльшим составом: в UI выбери '24 (wider cast)', Overwrite, Prepare book.")
    print("Затем снова: python test_quotes_and_characters.py")


def run_prepare(book_ids):
    try:
        import requests
    except ImportError:
        print("Для --prepare нужен requests. Установи: pip install requests")
        return
    base = "http://127.0.0.1:5000"
    for bid in book_ids:
        print(f"Prepare {bid}…", end=" ", flush=True)
        try:
            r = requests.post(
                f"{base}/api/prepare_book",
                json={"book_id": bid, "overwrite": True, "main_limit": 18},
                timeout=120,
            )
            data = r.json() if r.ok else {}
            if data.get("success"):
                n = data.get("count", 0)
                print(f"OK, персонажей: {n}")
            else:
                print(f"Ошибка: {data.get('error', r.text[:200])}")
        except requests.exceptions.ConnectionError:
            print("Сервер не запущен. Запусти: python app.py")
            return
        except Exception as e:
            print(f"Ошибка: {e}")
    print()
    run_report()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--prepare":
        ids = sys.argv[2:]
        if not ids:
            ids = ["gutenberg-1342", "gutenberg-1260", "gutenberg-345"]
        run_prepare(ids)
    else:
        run_report()
