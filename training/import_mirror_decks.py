"""Import paired public Archidekt Commander decks as reproducible rules fixtures.

Excludes Maybeboard/Sideboard and validates exact physical 100-card count.
Works on raw Archidekt oracleCard data; no deck-name-specific card behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from probe_mirror_decks import DECKS, get_deck

HERE=Path(__file__).resolve().parent
OUT=HERE/"decks"
SLUGS={14509839:"mono-red-gobs",14435337:"lupitas-elves"}
LINKS={
    14509839:"https://archidekt.com/decks/14509839/mono_red_gobs",
    14435337:"https://archidekt.com/decks/14435337/lupitas_elves",
}
COLOR_MAP={'W':'White','U':'Blue','B':'Black','R':'Red','G':'Green',
           'White':'White','Blue':'Blue','Black':'Black','Red':'Red',
           'Green':'Green','C':'Colorless','Colorless':'Colorless'}
SIDE={"Maybeboard","Sideboard","Considering"}  # Tokens is a user-defined strategy category!


def colors(values):
    return [COLOR_MAP.get(str(x),str(x)) for x in (values or ())]


def face_convert(f):
    if not isinstance(f,dict):
        raise ValueError("Unexpected face format")
    return dict(name=f.get('name',''),manaCost=f.get('manaCost') or '',
                types=f.get('types') or [],superTypes=f.get('superTypes') or [],
                subTypes=f.get('subTypes') or [], colors=colors(f.get('colors')),
                text=f.get('text') or '',power=f.get('power') or '',
                toughness=f.get('toughness') or '')


def convert_card(row:dict):
    oracle=((row.get('card') or {}).get('oracleCard') or {})
    if not oracle or not oracle.get('name'):
        raise ValueError('Missing oracle card name and metadata')
    q=row.get('quantity',1)
    if isinstance(q,bool) or int(q)!=q or q<1:
        raise ValueError("Invalid card quantity "+repr(q))
    faces=[face_convert(x) for x in (oracle.get('faces') or [])]
    result=dict(name=oracle['name'],quantity=int(q),oracleId=oracle.get('uid') or
                str(oracle.get('id','')), manaCost=oracle.get('manaCost') or '',
                types=oracle.get('types') or [],superTypes=oracle.get('superTypes') or [],
                subTypes=oracle.get('subTypes') or [],
                colors=colors(oracle.get('colors')),
                colorIdentity=colors(oracle.get('colorIdentity')),
                oracleText=oracle.get('text') or '',
                power=oracle.get('power') or '',
                toughness=oracle.get('toughness') or '',
                layout=oracle.get('layout') or 'normal',
                faces=faces, loyalty=oracle.get('loyalty'))
    return result


def convert_deck(deck_id:int,source:dict):
    if source.get('id') is not None and int(source['id'])!=deck_id:
        raise ValueError("Wrong source deck ID")
    if not source.get('cards'):
        raise ValueError('Empty deck')
    commanders,mainboard,excluded=[],[],[]
    sections=Counter()
    for row in source['cards']:
        categories=set(row.get('categories') or [])
        converted=convert_card(row)
        if categories & SIDE:
            excluded.append(converted)
            continue
        if 'Commander' in categories:
            commanders.append(converted)
            sections['commanders']+=converted['quantity']
        else:
            mainboard.append(converted)
            sections['mainboard']+=converted['quantity']
    if len(commanders)!=1 or commanders[0]['quantity']!=1:
        raise ValueError(f"Expected one commander, got {[(x['name'],x['quantity']) for x in commanders]}")
    if sections['commanders']+sections['mainboard']!=100:
        raise ValueError(f"Need exactly 100 active cards, got {dict(sections)}")
    if any(not c['name'] for c in commanders+mainboard):
        raise ValueError('Empty card name')
    if any(not c['types'] for c in commanders+mainboard):
        raise ValueError('Missing Oracle types')
    if any(not c['oracleText'] and 'Land' not in c['types']
           and not c['faces'] for c in commanders+mainboard):
        # No Oracle text is possible on vanilla creatures, so warn only.
        print("VANILLA_CARD_NO_RULES_TEXT",flush=True)
    result=dict(schemaVersion=1,sourceUrl=LINKS[deck_id],sourceDeckId=deck_id,
                name=source.get('name') or SLUGS[deck_id],
                sourceUpdatedAt=source.get('updatedAt'),
                retrievedAt=datetime.now(timezone.utc).isoformat(),
                format='commander',commanders=commanders,mainboard=mainboard)
    report=dict(id=deck_id,name=result['name'],commander=commanders[0]['name'],
                activeCards=sections['commanders']+sections['mainboard'],
                activeUnique=len(mainboard)+len(commanders),excludedMaybeboardCopies=sum(
                  x['quantity'] for x in excluded),
                lands=sum(c['quantity'] for c in mainboard if 'Land' in c['types']),
                creatureCards=sum(c['quantity'] for c in mainboard if 'Creature' in c['types']),
                cardTypes=dict(Counter(t for c in mainboard for t in c['types'] for
                                       _ in range(c['quantity']))),
                sourceUrl=LINKS[deck_id])
    return result,report


def write_files(source_data):
    OUT.mkdir(parents=True,exist_ok=True)
    result=[]
    for deck_id,_ in DECKS:
        data,report=convert_deck(deck_id,source_data[deck_id])
        path=OUT/f"{deck_id}-{SLUGS[deck_id]}.json"
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding='utf-8')
        report['path']=str(path.relative_to(HERE.parent))
        result.append(report)
        print("MIRROR_IMPORT "+json.dumps(report,ensure_ascii=False),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-probe',type=Path,
                        help='Use raw files created by probe_mirror_decks.py instead of downloading')
    args=parser.parse_args()
    inputs={}
    for deck_id,slug in DECKS:
        if args.from_probe:
            inputs[deck_id]=json.loads((args.from_probe/f"{deck_id}-{slug}-raw.json").read_text())
        else:
            inputs[deck_id]=get_deck(deck_id)
    reports=write_files(inputs)
    output=HERE/"reports/mirror-teaching-import.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(decks=reports),indent=2)+"\n",encoding='utf-8')


if __name__=='__main__':
    main()
