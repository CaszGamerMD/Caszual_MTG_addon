#!/usr/bin/env python3
"""Batch semantic card reading; model use is opt-in, never part of a match.

Examples:
  python training/oracle_semantic_batch.py --source training/reports/random-commander-exam-20261031/scryfall-source.json --prepare
  python training/oracle_semantic_batch.py --source .../scryfall-source.json --responses proposals.json
  python training/oracle_semantic_batch.py --source .../scryfall-source.json --invoke --model gpt-6-astra

The first command makes a complete reviewable *request* without network or
LLM cost. The second validates offline proposals; the third explicitly asks a
model to read them. No resulting proposal is executed by the game engine.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from oracle_semantic_reader import (INSTRUCTIONS, SCHEMA, model_input,
    oracle_units, report, request_model)
from scryfall_random_exam import convert_scryfall
import simulator as s


HERE=Path(__file__).resolve().parent


def load_cards(path: Path) -> list[dict]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data,list):
        return [convert_scryfall(x) if x.get('object')=='card' else x for x in data]
    if isinstance(data,dict) and 'mainboard' in data and 'commanders' in data:
        return [*data['commanders'],*data['mainboard']]
    raise ValueError('Source must contain raw cards, Scryfall cards, or a saved deck')


def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true',help='No network; save model input and schema')
    mode.add_argument('--responses',type=Path,help='Offline array of proposed model responses')
    mode.add_argument('--invoke',action='store_true',help='Explicit external model requests, billed separately')
    p.add_argument('--model',default='',help='Explicit Responses model, required with --invoke')
    p.add_argument('--limit',type=int,default=15)
    p.add_argument('--out',type=Path,default=HERE/'reports/oracle-semantic-audit')
    p.add_argument('--diagnostic',action='store_true',
                   help='Separately run the existing diagnostic importer on every card')
    args=p.parse_args()
    if not 1<=args.limit<=100:raise ValueError('Limit must be 1..100 cards')
    cards=load_cards(args.source)[:args.limit]
    if not cards:raise ValueError('No source cards')
    if args.prepare:
        s.write_json(args.out/'model-request.json',dict(
            instructions=INSTRUCTIONS,schema=SCHEMA,
            cards=[model_input(card) for card in cards],
            warning='Semantic proposals are hypotheses, not executable rules.'))
        print(f'SEMANTIC_PREPARED {len(cards)} cards and '
              f'{sum(len(oracle_units(c)) for c in cards)} Oracle lines; no model call')
        return
    if args.invoke:
        if not args.model:raise ValueError('--invoke requires an explicit --model')
        proposals=[]
        for i,card in enumerate(cards):
            proposals.append(request_model(card,model=args.model))
            print(f'SEMANTIC_MODEL_READ {i+1}/{len(cards)}',flush=True)
    else:
        proposals=json.loads(args.responses.read_text(encoding='utf-8'))
    verdicts=None
    if args.diagnostic:
        with s.RulesBridge() as rules:
            verdicts=[s.import_diagnostic_card(rules,card,0,
                      f'semantic-audit-{i}',set(card.get('colorIdentity',[]))).kind!='unsupported'
                      for i,card in enumerate(cards)]
    data=report(cards,proposals,verdicts)
    s.write_json(args.out/'semantic-proposals.json',data)
    print('SEMANTIC_AUDIT '+json.dumps(dict(cards=data['totalCards'],
          lines=data['sourceLines'],checked=data['proposalChecked'],
          accuracyVerified=False,learningEligible=False,
          capabilities=[dict(name=x['capability'],cardCount=x['cardCount'])
                        for x in data['capabilities']]),ensure_ascii=False))


if __name__=='__main__':run()
