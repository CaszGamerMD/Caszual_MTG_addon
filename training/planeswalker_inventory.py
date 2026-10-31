"""Offline inventory of saved-deck planeswalkers and compiler blockers."""
from pathlib import Path
import json
from planeswalker_loyalty import inspect_card

ROOT=Path(__file__).resolve().parent

def report(decks):
    found=[]
    for deck in decks:
        for card in deck.get('commanders',[])+deck.get('mainboard',[]):
            if 'Planeswalker' not in card.get('types',[]):
                continue
            found.append(dict(deck=deck['name'],
                quantity=card.get('quantity',1),
                **inspect_card(card)))
    return dict(kind='planeswalker-capability-inventory',
                learningEligible=False,
                count=sum(x['quantity'] for x in found),
                fullyCompiled=sum(x['executionReady'] for x in found),
                entries=found)

def main():
    decks=[json.loads(file.read_text(encoding='utf-8'))
           for file in sorted((ROOT/'decks').glob('*.json'))]
    if not decks:raise RuntimeError('Saved deck inventory not found')
    result=report(decks)
    out=ROOT/'reports'/'planeswalker-capabilities.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
