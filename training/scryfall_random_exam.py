"""Blind Scryfall card-understanding exam for the *diagnostic* Commander engine.

Pull 5 random paper Commander-legal cards per round, without choosing easy cards.
Classify full-card importer acceptance, executable compiled evidence, heuristic
mechanic guesses and gaps. Never promote partial text guesses to rules support.

Run e.g.:
    python training/scryfall_random_exam.py --count 5 --rounds 3

Scryfall API etiquette: descriptive User-Agent / Accept, 250ms pacing, no
retry storm on 429/403. Store exact source card objects for reproducibility.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import simulator as s
from compiled_rules_knowledge import compiled_knowledge
from strategy_building_blocks import parse_card_blocks

HERE=Path(__file__).resolve().parent
QUERY='legal:commander game:paper'
URL='https://api.scryfall.com/cards/random?'+urlencode({'q':QUERY})
HEADERS={
    'User-Agent':'CaszualMTG-OracleLearning/1.0 (GitHub CaszGamerMD/Caszual_MTG_addon; one-shot rules research)',
    'Accept':'application/json;q=0.9,*/*;q=0.8',
}
SYMBOL={'W':'White','U':'Blue','B':'Black','R':'Red','G':'Green','C':'Colorless'}
SUPERTYPES={'Basic','Legendary','Snow','World','Ongoing'}


def type_parts(type_line: str):
    """Scryfall type line => engine type, subtype and supertype vectors."""
    if not type_line or not isinstance(type_line,str):
        raise ValueError('Missing type line')
    parts=type_line.split(' — ',1)
    if len(parts)==1:
        parts=type_line.split(' - ',1)
    head=parts[0].split()
    if not head:
        raise ValueError('Empty type line')
    super_types=[x for x in head if x in SUPERTYPES]
    types=[x for x in head if x not in SUPERTYPES]
    subtypes=parts[1].split() if len(parts)>1 else []
    return types,super_types,subtypes


def face_to_raw(obj: dict):
    types,supers,subtypes=type_parts(obj['type_line'])
    return dict(name=obj.get('name') or '',manaCost=obj.get('mana_cost') or '',
                types=types,superTypes=supers,subTypes=subtypes,
                colors=[SYMBOL.get(x,x) for x in (obj.get('colors') or ())],
                text=obj.get('oracle_text') or '',
                power=obj.get('power') or '',toughness=obj.get('toughness') or '',
                loyalty=obj.get('loyalty'))


def convert_scryfall(card: dict):
    """Faithful raw-card conversion; never concatenate DFC faces to claim support."""
    if card.get('object')!='card' or not card.get('id') or not card.get('name'):
        raise ValueError('Malformed Scryfall card response')
    if card.get('legalities',{}).get('commander')!='legal' or 'paper' not in card.get('games',()):
        raise ValueError('Result not paper Commander legal')
    raw=face_to_raw(card)
    raw.update(oracleId=card.get('oracle_id'),quantity=1,
        colorIdentity=[SYMBOL.get(x,x) for x in card.get('color_identity',[])],
        layout=card.get('layout') or 'normal',
        faces=[face_to_raw(x) for x in (card.get('card_faces') or ())])
    raw['oracleText']=card.get('oracle_text') or ''
    if not raw['oracleText'] and len(raw['faces'])==1:
        raw['oracleText']=raw['faces'][0]['text']
    # Scryfall's type_line for transform cards is a parent combined line.
    # Their *faces* preserve complete printed rules for correct validation.
    return raw


def fetch_random():
    req=Request(URL,headers=HEADERS)
    with urlopen(req,timeout=25) as response:
        if response.status!=200:
            raise RuntimeError('Scryfall returned HTTP '+str(response.status))
        data=json.load(response)
        if not isinstance(data,dict):
            raise ValueError('Scryfall response must be one card')
        return data


def sample(count: int, rounds: int, fetch=fetch_random, sleep=time.sleep):
    """Collect only distinct original Oracle identities. Never fudge missing draws."""
    if count<1 or rounds<1 or count*rounds>100:
        raise ValueError('Exam needs 1..100 cards in positive rounds')
    draws=[]
    seen=set()
    needed=count*rounds
    # Network random endpoint can yield repeated printings; bound attempts.
    max_tries=needed*5
    for attempt in range(max_tries):
        if len(draws)>=needed:
            break
        if attempt:
            sleep(.25)
        obj=fetch()
        converted=convert_scryfall(obj)
        oracle=obj.get('oracle_id') or obj['id']
        if oracle in seen:
            continue
        seen.add(oracle)
        draws.append((obj,converted))
    if len(draws)!=needed:
        raise RuntimeError(f'Scryfall supplied only {len(draws)}/{needed} unique legal cards')
    return draws


def analyze(rules, source: dict, converted: dict, index: int):
    """Engine conclusion versus *uncertified* heuristic clues, with provenance."""
    card=s.import_diagnostic_card(rules,converted,0,'exam-'+str(index),
                                  set(converted['colorIdentity']))
    knowledge=compiled_knowledge(card)
    hypothesis=parse_card_blocks(converted)
    full=card.kind!='unsupported'
    # A card importer recognizing a type or spell does NOT verify the
    # stack/choices/outcomes in an actual played game.
    diagnostic=s.parse_event_card(converted)
    reason='' if full else diagnostic.reason or 'No whole-card diagnostic executor supports this Oracle program'
    raw_text=converted['oracleText'] or '\n//\n'.join(f['text'] for f in converted['faces'])
    return dict(
        number=index+1, card=converted['name'],scryfallId=source['id'],
        oracleId=source.get('oracle_id'),url=source.get('scryfall_uri'),
        commanderLegal=source['legalities']['commander']=='legal',
        layout=converted['layout'],typeLine=source.get('type_line'),
        oracleText=raw_text, manaCost=converted['manaCost'],
        verdict='diagnostic-compiled' if full else 'unsupported',
        # Independent signals: lexical ideas never imply executable behavior.
        executableDiagnostic=full,kind=card.kind,
        confirmed=knowledge['rules'],confirmedRoles=knowledge['roles'],
        hypotheticalRoles=list(hypothesis.blocks),
        hypotheticalNeeds=list(hypothesis.needs),
        hypotheticalProduces=list(hypothesis.produces),
        gap=reason,
        notice='Import acceptance is NOT proof of rules-correct execution or full Commander legality')


def exam(draws, rules, count):
    rows=[analyze(rules,source,raw,i) for i,(source,raw) in enumerate(draws)]
    batches=[]
    for n in range(0,len(rows),count):
        section=rows[n:n+count]
        accepted=sum(x['executableDiagnostic'] for x in section)
        batch=dict(round=n//count+1,count=len(section),diagnosticCompiled=accepted,
                   unsupported=len(section)-accepted,cards=section)
        batches.append(batch)
    totals=Counter(x['verdict'] for x in rows)
    return dict(schemaVersion=1,kind='random-commander-oracle-exam',
                queried=QUERY,createdAt=datetime.now(timezone.utc).isoformat(),
                totalCards=len(rows),batchSize=count,batches=batches,
                totals=dict(totals),learningEligible=False,
                interpretation='Diagnostic importer accepted = text recognized, NOT validated game execution; no rules training from unsupported cards')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count',type=int,default=5)
    p.add_argument('--rounds',type=int,default=1)
    p.add_argument('--out',type=Path,default=HERE/'reports/random-commander-exam')
    a=p.parse_args()
    draws=sample(a.count,a.rounds)
    a.out.mkdir(parents=True,exist_ok=True)
    s.write_json(a.out/'scryfall-source.json',[source for source,_ in draws])
    with s.RulesBridge() as rules:
        data=exam(draws,rules,a.count)
    s.write_json(a.out/'results.json',data)
    for batch in data['batches']:
        for row in batch['cards']:
            print('RANDOM_CARD_RESULT '+json.dumps(
                {key:row[key] for key in ('number','card','url','layout','verdict',
                     'confirmedRoles','hypotheticalRoles','gap')},ensure_ascii=False),flush=True)
        print('RANDOM_CARD_BATCH '+json.dumps(
            {key:batch[key] for key in ('round','count','diagnosticCompiled','unsupported')}),
            flush=True)
    print('RANDOM_CARD_SUMMARY '+json.dumps(
        dict(totalCards=data['totalCards'],totals=data['totals'],
             report=str(a.out/'results.json')),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
