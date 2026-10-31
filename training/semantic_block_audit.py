"""Offline audit: which proposed Oracle operations have reusable handlers?

Reads previously saved sources and semantic proposals. Makes no API calls and
never creates executable cards, legal actions, or game-state mutations.

Usage:
  python training/semantic_block_audit.py --source scryfall-source.json \
      --proposals semantic-proposals.json --out semantic-block-audit.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from oracle_semantic_reader import fingerprint
from semantic_execution_blocks import inspect_semantic_proposal
from scryfall_random_exam import convert_scryfall


def audit(scryfall_sources: list[dict], semantic_report: dict) -> dict:
    rows=semantic_report.get('cards')
    if not isinstance(rows,list) or len(rows)!=len(scryfall_sources):
        raise ValueError('Every source card needs its original semantic report row')
    if semantic_report.get('totalCards')!=len(rows):
        raise ValueError('Semantic report size is inconsistent')
    candidates=[];rejected=[];verified=0
    for index,(source,row) in enumerate(zip(scryfall_sources,rows)):
        card=convert_scryfall(source)
        if row.get('fingerprint')!=fingerprint(card) or row.get('card')!=card['name']:
            raise ValueError('Semantic report is not bound to the source Oracle text')
        if row.get('semanticAccuracyVerified') is not False:
            raise ValueError('Only unverified semantic reports belong in this audit')
        if row.get('semanticStatus')=='rejected-unverified':
            if row.get('units') or not row.get('rejectionReason'):
                raise ValueError('Malformed rejected semantic report row')
            rejected.append(dict(card=card['name'],reason=row['rejectionReason']))
            continue
        if row.get('semanticStatus')!='model-proposal-evidence-checked':
            raise ValueError('Unrecognized semantic proposal status')
        proposal=dict(units=row['units'],summary=row['summary'],
                      uncertainties=row['uncertainties'])
        draft=inspect_semantic_proposal(card,proposal)
        verified+=1  # Evidence checked only; not semantic accuracy.
        candidates.extend(dict(card=card['name'],cardIndex=index,**item)
                          for item in draft['candidates'])
    handlers=Counter(item['candidateHandler'] or 'missing_handler' for item in candidates)
    verbs=Counter(item['verb'] for item in candidates)
    return dict(kind='untrusted-semantic-block-audit',totalCards=len(rows),
                evidenceCheckedCards=verified,rejectedCards=len(rejected),
                potentialHandlerOperations=sum(bool(c['candidateHandler']) for c in candidates),
                missingHandlerOperations=sum(not c['candidateHandler'] for c in candidates),
                handlerCounts=dict(sorted(handlers.items())),
                verbCounts=dict(sorted(verbs.items())),rejected=rejected,
                candidates=candidates,executionReady=False,learningEligible=False,
                notice='Candidate handlers are not verified semantic mappings or legal gameplay rules')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--proposals',type=Path,required=True)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    data=audit(json.loads(args.source.read_text(encoding='utf-8')),
               json.loads(args.proposals.read_text(encoding='utf-8')))
    output=json.dumps(data,indent=2,ensure_ascii=False)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(output,encoding='utf-8')
    else:
        print(output,end='')


if __name__=='__main__':main()
