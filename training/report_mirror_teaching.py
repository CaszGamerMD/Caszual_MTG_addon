"""Paired teaching-deck diagnostic: plans, rules coverage, opening consistency.

No forced 50/50 win-rate objective or hidden opponent information. Never call
a rules-blocked simulated game a test of deck balance.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import re

from deck_adaptive_strategy import analyze_deck
from strategy_building_blocks import map_mechanics, compose_routes
from diagnostic_coverage import report as coverage_report
from simulator import RulesBridge

ROOT=Path(__file__).resolve().parent
PAIRS=(
  ("Goblin", ROOT/"decks/14509839-mono-red-gobs.json"),
  ("Elf", ROOT/"decks/14435337-lupitas-elves.json"),
)

def cmc(card):
    cost=card.get('manaCost') or ''
    return sum(int(t) if t.isdigit() else 0 if t.upper()=='X' else 1
               for t in re.findall(r'\{([^}]+)\}',cost))


def opening_stats(deck, sample=400, seed=14509839):
    """Same-shuffle-index baseline; no opponent library observation or cheating."""
    cards=[]
    for card in deck['mainboard']:
        cards += [card] * int(card['quantity'])
    if len(cards)!=99:
        raise ValueError('Expected 99 physical mainboard cards')
    rng=random.Random(seed)
    three_lands=0
    playable=0
    low=0
    sumlands=0
    for i in range(sample):
        hand=rng.sample(cards,7)
        lands=sum('Land' in c.get('types',()) for c in hand)
        cheap=sum('Land' not in c.get('types',()) and cmc(c)<=3 for c in hand)
        sumlands+=lands
        three_lands+=lands==3
        # Opening fitness proxy: not a guarantee of mana colors or castability.
        playable+=(2<=lands<=4 and cheap>=2)
        low+=(lands<=1)
    return dict(samples=sample,seed=seed,threeLandRate=round(three_lands/sample,3),
                lowLandRate=round(low/sample,3),playableProxyRate=round(playable/sample,3),
                avgLandsInSeven=round(sumlands/sample,2),
                proxyDefinition='2-4 lands and 2 nonlands with printed mana value <=3; not rules-validated')


def compare(decks, coverage, samples=400):
    plans={label:analyze_deck(deck) for label,deck in decks.items()}
    own={}
    for label,deck in decks.items():
        cards=[c for c in deck['mainboard'] for _ in range(int(c['quantity']))]
        blocks=map_mechanics(deck)
        counts=Counter(role for c in blocks for role in c.blocks for _ in range(c.quantity))
        own[label]=dict(sourceDeckId=deck['sourceDeckId'],title=deck['name'],
            commander=deck['commanders'][0]['name'],
            totalCards=1+len(cards),
            landCount=sum('Land' in c['types'] for c in cards),
            creatureCount=sum('Creature' in c['types'] for c in cards),
            equipmentCount=sum('Equipment' in c.get('subTypes',[]) for c in cards),
            cheapNonlands=sum('Land' not in c['types'] and cmc(c)<=3 for c in cards),
            opening=opening_stats(deck,samples),
            mechanicBlocks=dict(sorted(counts.items())),
            plan=plans[label].describe())
    by_id={d['deckId']:d for d in coverage['decks']}
    for label,data in own.items():
        card_cov=by_id[data['sourceDeckId']]
        data['rulesCoverage']=dict(playable=card_cov['playable'],
            unsupported=card_cov['unsupported'],
            commanderPlayable=card_cov['commanderPlayable'],
            unsupportedNames=card_cov['unsupportedCards'])
    return dict(schemaVersion=1,kind='mirror-teaching-deck-evaluation',
                mode='decklist-and-diagnostic-card-coverage',
                learningEligible=False, matchResultsAvailable=False,
                statement='Comparable construction does not prove fair games; full games gated by rules coverage.',
                comparison=own,
                deltas=dict(lands=own['Goblin']['landCount']-own['Elf']['landCount'],
                    cheapNonlands=own['Goblin']['cheapNonlands']-own['Elf']['cheapNonlands'],
                    playableOpeningRate=round(own['Goblin']['opening']['playableProxyRate']-
                                              own['Elf']['opening']['playableProxyRate'],3)),
                bothFullyDiagnosticPlayable=all(
                    v['rulesCoverage']['unsupported']==0 and
                    v['rulesCoverage']['commanderPlayable'] for v in own.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=400)
    p.add_argument('--out',type=Path,default=ROOT/'reports/mirror-teaching-comparison.json')
    a=p.parse_args()
    decks={name:json.loads(path.read_text()) for name,path in PAIRS}
    if a.samples<=0:raise ValueError('samples must be positive')
    with RulesBridge() as rules:
        coverage=coverage_report(rules,list(decks.values()))
    result=compare(decks,coverage,samples=a.samples)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    for name,data in result['comparison'].items():
        print('TEACHING_DECK_PROFILE '+json.dumps(dict(deck=name,
                commander=data['commander'],lands=data['landCount'],
                creatures=data['creatureCount'],equipments=data['equipmentCount'],
                cheapNonlands=data['cheapNonlands'],
                opening=data['opening'],primary=data['plan']['primary'],
                routes=data['plan']['strategyRoutes'],
                unsupported=data['rulesCoverage']['unsupported'],
                unresolved=data['rulesCoverage']['unsupportedNames']),
                ensure_ascii=False),flush=True)
    print('MIRROR_TEACHING_SUMMARY '+json.dumps(dict(
        bothFullyDiagnosticPlayable=result['bothFullyDiagnosticPlayable'],
        deltas=result['deltas'],samples=a.samples,matchResultsAvailable=False)),
        flush=True)


if __name__=='__main__':
    main()
