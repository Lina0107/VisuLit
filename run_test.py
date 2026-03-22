import sys, requests, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

books = [
    ("gutenberg-37106", "Little Women"),
    ("gutenberg-84", "Frankenstein"),
    ("gutenberg-768", "Wuthering Heights"),
]

for bid, title in books:
    print(f"\n=== Testing: {title} ({bid}) ===")
    try:
        r = requests.post(
            "http://localhost:5000/api/prepare_book",
            json={"book_id": bid, "overwrite": True, "main_limit": 8},
            timeout=300
        )
        d = r.json()
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        continue

    if d.get("success"):
        chars = d.get("characters", [])
        print(f"OK — {len(chars)} characters found")
        for c in chars:
            name = c.get("character_name", "?")
            evq  = c.get("evidence_quotes", [])
            apq  = c.get("appearance_quotes", [])
            print(f"  [{name}]  evidence={len(evq)}  appearance={len(apq)}")
            if evq:
                print(f"    EVID : {evq[0]['quote'][:120]}")
            if apq:
                print(f"    APPEAR: {apq[0]['quote'][:120]}")
    else:
        print(f"FAIL: {d.get('error')}")
