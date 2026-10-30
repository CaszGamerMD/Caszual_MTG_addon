"""Report *diagnostic simulator* coverage separately from Java rules-bridge audit.

Runs against the actual five saved Commander decks and writes a JSON artifact.
"Playable" here means the sandbox importer recognizes the complete card text,
not that arbitrary Commander games are learning-eligible or fully supported.
"""
from __future__ import annotations

import json
from pathlib import Path
from simulator import RulesBridge, import_diagnostic_card

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports" / "diagnostic-coverage.json"


def report(rules, decks):
    result = []
    unresolved_names = set()
    for deck in decks:
        identity = set(deck["commanders"][0].get("colorIdentity", []))
        unresolved = []
        playable = []
        for index, card in enumerate(deck["commanders"] + deck["mainboard"]):
            diagnostic = import_diagnostic_card(
                rules, card, 0, f"audit-{index:04d}", identity
            )
            quantity = int(card["quantity"])
            record = dict(name=card["name"], quantity=quantity)
            if diagnostic.kind == "unsupported":
                unresolved.append(record)
                unresolved_names.add(card["name"])
            else:
                playable.append(record)
        playable_count = sum(c["quantity"] for c in playable)
        unsupported_count = sum(c["quantity"] for c in unresolved)
        result.append(dict(
            deckId=deck.get("sourceDeckId"), deck=deck["name"],
            cardCount=playable_count + unsupported_count,
            playable=playable_count, unsupported=unsupported_count,
            commanderPlayable=all(
                name["name"] not in {p["name"] for p in unresolved}
                for name in deck["commanders"]
            ),
            unsupportedCards=[x["name"] for x in unresolved],
            playableCards=[x["name"] for x in playable],
        ))
    return dict(
        schemaVersion=1,kind="diagnostic-coverage",learningEligible=False,
        disclaimer="Diagnostic parse coverage only; not full rules conformance.",
        decks=result,uniqueUnsupportedNames=len(unresolved_names),
        unsupportedNames=sorted(unresolved_names),
    )


def main():
    decks = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "decks").glob("*.json"))
    ]
    if not decks:
        raise RuntimeError("No saved decks found; never report empty coverage as success.")
    with RulesBridge() as rules:
        data = report(rules, decks)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Name-level blocker inventory for the two focused decks, emitted in CI
    # so each remaining rule family can be resolved without guessing.
    for item in data["decks"]:
        if item["deckId"] in (5254666, 5189995, 14509839, 14435337):
            print("FOCUSED_UNRESOLVED " + json.dumps({
                "deckId":item["deckId"],"deck":item["deck"],
                "unresolved":item["unsupportedCards"],"count":item["unsupported"]
            },ensure_ascii=False))
    print(json.dumps({
        "kind": data["kind"], "uniqueUnsupportedNames": data["uniqueUnsupportedNames"],
        "decks": [{k: deck[k] for k in ("deckId","deck","cardCount","playable","unsupported","commanderPlayable")}
                  for deck in data["decks"]],
        "artifact": str(OUT),
        "learningEligible": data["learningEligible"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
