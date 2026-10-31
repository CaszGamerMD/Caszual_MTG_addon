"""Seeded offline AI skirmishes using both real Faeries planeswalkers.

This is a nonlearning partial diagnostic: two genuine planeswalker definitions
with supported sandbox creatures/lands, NOT full Commander deck games.
Fail visibly if games pause or if the agent never uses loyalty.
"""
from pathlib import Path
import json

from simulator import (
    RulesBridge,Simulator,Policy,Card,Permanent,
    demo_deck,import_diagnostic_card,write_json
)

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports'/'planeswalker-strategy-skirmishes.json'

def run_skirmishes(rules,seeds=(101,203,307)):
    deck=json.loads((ROOT/'decks'/'27521806-faeries.json').read_text(encoding='utf-8'))
    saved={c['name']:c for c in deck['mainboard'] if 'Planeswalker' in c.get('types',())}
    names=('Kaito Shizuki','Liliana, the Last Hope')
    samples=[]
    for seed in seeds:
        walkers=tuple(import_diagnostic_card(rules,saved[name],seat,f'walker-{seat}',
                            set(saved[name]['colorIdentity']))
                      for seat,name in enumerate(names))
        if any(x.kind!='planeswalker' for x in walkers):
            raise RuntimeError('Saved planeswalker card no longer compiles')
        sim=Simulator(rules,seed,decks=tuple(demo_deck(seat)+[walkers[seat]]
                           for seat in (0,1)),diagnostic=True,max_turns=12,
                           policies=(Policy(),Policy()))
        if sim.finished:raise RuntimeError('Skirmish was blocked at initialization')
        for seat,walker in enumerate(walkers):
            player=sim.players[seat]
            (player.hand if walker in player.hand else player.library).remove(walker)
            player.battlefield.append(Permanent(walker,loyalty=walker.loyalty_program.starting_loyalty))
        result=sim.run()
        activations=[dict(actor=e.get('actor'),cost=e.get('details',{}).get('cost'),
                          source=e.get('details',{}).get('source'),
                          loyalty=e.get('details',{}).get('remainingLoyalty'))
                     for e in sim.events if e['kind']=='loyalty_activation']
        decisions=[dict(seat=x['seat'],turn=x['turn'],phase=x['phase'],
                        choice=x['action']) for x in sim.decisions
                   if x['action']=='activate_loyalty']
        samples.append(dict(seed=seed,turns=result['turns'],result=result['result'],
                winner=result['winner'],questions=result['questions'],
                activationCount=len(activations),activations=activations,
                decisions=decisions,
                playedEmblems=sum(e['kind']=='emblem_created' for e in sim.events),
                tacticalChoiceKind='public-board-loyalty-v1'))
    return dict(kind='diagnostic-planeswalker-skirmishes',learningEligible=False,
                realPlaneswalkerNames=list(names),
                scope='real saved planeswalkers in synthetic supported 26-card environments',
                samples=samples)

def main():
    with RulesBridge() as rules:data=run_skirmishes(rules)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    write_json(OUT,data)
    print(json.dumps(dict(kind=data['kind'],scope=data['scope'],
         samples=[{k:v for k,v in s.items() if k in
                   ('seed','turns','result','activationCount','playedEmblems')}
                  for s in data['samples']],
         artifact=str(OUT)),ensure_ascii=False))
    if any(s['questions'] for s in data['samples']):
        raise RuntimeError('Skirmish paused; see report for unresolved question')
    if sum(s['activationCount'] for s in data['samples'])==0:
        raise RuntimeError('No real planeswalker loyalty decisions observed')

if __name__=='__main__':main()
