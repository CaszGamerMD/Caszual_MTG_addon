"""Probe the two user-supplied Archidekt teaching decks without guessing their contents.

The Archidekt API is public but network access can be unavailable; fail visibly.
Save complete raw JSON as a GitHub Actions artifact for an auditable import.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DECKS = (
    (14509839, "mono_red_gobs"),
    (14435337, "lupitas_elves"),
)

def get_deck(deck_id: int):
    url = f"https://archidekt.com/api/decks/{deck_id}/"
    req = Request(url, headers={"User-Agent": "CaszualMTG-Learning-DeckImporter/1.0 (personal teaching deck research)", "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        if response.status != 200: raise RuntimeError(f"HTTP {response.status} for {deck_id}")
        return json.load(response)

def summary(deck_id, data):
    cards = data.get("cards", [])
    rows = []
    for entry in cards:
        oracle = ((entry.get("card") or {}).get("oracleCard") or {})
        rows.append(dict(name=oracle.get("name"),
                         categories=entry.get("categories") or [],
                         quantity=entry.get("quantity"),
                         type=oracle.get("types"),
                         oracleFields=list(oracle)[:35]))
    categories={}
    for r in rows:
        for cat in r["categories"]:
            categories[str(cat)]=categories.get(str(cat),0)+(r["quantity"] or 1)
    return dict(deckId=deck_id, deckName=data.get("name"),format=data.get("deckFormat"),
                deckKeys=sorted(data.keys()), countEntries=len(rows),
                totalCopies=sum(r["quantity"] or 1 for r in rows),
                categoryCopies=categories,
                commanderCandidates=[r["name"] for r in rows if
                                    "Commander" in r["categories"]],
                names=[(r["quantity"],r["name"],r["categories"]) for r in rows],
                oracleSample=rows[0]["oracleFields"] if rows else [])

def main():
    out=Path("training/reports/mirror-deck-probe")
    out.mkdir(parents=True,exist_ok=True)
    errors=[]
    for deck_id,label in DECKS:
        try:
            data=get_deck(deck_id)
            if not isinstance(data, dict) or not data.get("cards"):
                raise ValueError("No public deck card records found")
            (out/f"{deck_id}-{label}-raw.json").write_text(
                json.dumps(data,indent=2,ensure_ascii=False)+"\n")
            result=summary(deck_id,data)
            (out/f"{deck_id}-{label}-summary.json").write_text(json.dumps(result,indent=2)+"\n")
            print("MIRROR_DECK " + json.dumps(result,ensure_ascii=False),flush=True)
        except Exception as exc:
            errors.append(dict(deckId=deck_id,error=f"{type(exc).__name__}: {exc}"))
            print("MIRROR_IMPORT_ERROR "+json.dumps(errors[-1]),flush=True)
    if errors:
        (out/"errors.json").write_text(json.dumps(errors,indent=2)+"\n")
        raise SystemExit(1)

if __name__=="__main__":
    main()
