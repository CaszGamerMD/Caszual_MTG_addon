"""Rank unresolved Oracle-language families; suggestions never grant rules support.

Use standalone against an existing questions.json, or via the gauntlet writer.
A card can require multiple families, so affected-card totals are not additive
and are not estimates of how many cards become fully playable from one change.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from card_events import rule_text
from oracle_abilities import compile_abilities, KEYWORDS
from attachments import parse as parse_attachment
from mana_pool import production

FAMILIES = (
    ('cost changes', r'cost .+ (?:less|more) to cast|cost .+ more'),
    ('replacement effects', r'\binstead\b'),
    ('counters', r'\bcounters?\b'),
    ('lifegain', r'\bgain(?:ed|s)? .{0,35}life\b'),
    ('draw and library operations', r'\bdraw|\bscry|\bsurveil|\blibrary\b'),
    ('attachments and roles', r'\benchant(?:ed)?\b|\bequip(?:ped)?\b|\bRole\b|\bliving weapon\b'),
    ('targeted removal and return', r'\bexile target|\bdestroy target|\breturn .+ battlefield'),
    ('token creation and copying', r'\bcreate\b|\bcopy\b'),
    ('mana and land rules', r'\bAdd\b|\bland\b'),
    ('combat restrictions and triggers', r'\battacks?\b|\bblocks?\b|\bcombat\b'),
    ('activated abilities', r':'),
    ('cast triggers', r'Whenever .+ casts?\b'),
)


def normalized_clause(text, name):
    text=rule_text(text)
    # Self references and numeric parameters are variables, not card identities.
    for alias in sorted({name,name.split(',')[0]},key=len,reverse=True):
        if alias:text=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)','SELF',text)
    return re.sub(r'\b[0-9]+\b','N',text).strip()


def recognized_component(clause, name):
    text=rule_text(clause)
    if compile_abilities(text,name) is not None:return True
    if {word.strip().lower() for word in text.split(',')}<=KEYWORDS:return True
    if production(text):return True
    if text=='Enchant creature':return True
    if parse_attachment('Enchant creature\n'+text,{'Enchantment'},{'Aura'}):return True
    if re.fullmatch(r'Equip \{[0-9]+\}',text):
        return parse_attachment('Equipped creature gets +1/+1.\n'+text,{'Artifact'},{'Equipment'}) is not None
    return False


def build_report(questions, focal_id=None):
    families=defaultdict(dict);patterns=defaultdict(dict);cards=[];recognized={}
    for question in questions:
        name=question['card'];text=rule_text(question.get('oracleText',''))
        tags=[name for name,pattern in FAMILIES if re.search(pattern,text,re.I)]
        if not text:tags=['multiple faces or missing Oracle text']
        elif not tags:tags=['other unsupported language']
        entry=dict(card=name,questionId=question['id'],requiredFamilyCandidates=tags,
                   focal=any(str(o['deckId'])==str(focal_id) for o in question.get('occurrences',[])),
                   encounters=len(set(question.get('encounterGames',[]))),
                   copies=sum(o.get('quantity',1) for o in question.get('occurrences',[])))
        cards.append(entry)
        for tag in tags:families[tag][question['id']]=entry
        for clause in text.splitlines():
            key=normalized_clause(clause,name)
            if key:
                patterns[key][question['id']]=entry
                recognized[key]=recognized.get(key,True) and recognized_component(clause,name)
    def rows(groups,key):
        result=[]
        for label,entries in groups.items():
            values=list(entries.values())
            result.append({key:label,'affectedCards':len(values),
                           'focalCards':sum(v['focal'] for v in values),
                           'cardGameEncounters':sum(v['encounters'] for v in values),
                           'cards':sorted(v['card'] for v in values),
                           'cardsWithOtherCandidateFamilies':sum(len(v['requiredFamilyCandidates'])>1 for v in values)})
        return sorted(result,key=lambda row:(-row['focalCards'],-row['affectedCards'],-row['cardGameEncounters'],row[key]))
    repeated=[dict(row,componentRecognizedByPythonGrammar=recognized[row['template']]) for row in rows(patterns,'template') if row['affectedCards']>1]
    repeated.sort(key=lambda row:row['componentRecognizedByPythonGrammar'])
    return dict(schemaVersion=1,
                notice='Heuristic work planning only. Families overlap; matching a family does not resolve a card. Component recognition is partial (Python grammar only); false does not prove a missing rule. Recognized components may still need composition support. Full Oracle parsing and behavioral tests remain required.',
                unresolvedCards=len(cards),families=rows(families,'family'),
                repeatedClauseTemplates=repeated,cards=cards)


def questions_from_decks(rules, decks):
    """Fresh parse coverage without playing games or consulting old reports."""
    from simulator import import_diagnostic_card, question
    questions={}
    for deck in decks:
        identity=set(deck['commanders'][0].get('colorIdentity',[]))
        for role in ('commanders','mainboard'):
            for raw in deck[role]:
                card=import_diagnostic_card(rules,raw,0,'batch-audit',identity)
                if card.kind!='unsupported':continue
                q=question(raw,'Unsupported complete Oracle program',deck['name'])
                entry=questions.setdefault(q['id'],dict(q,occurrences=[],encounterGames=[]))
                entry['occurrences'].append(dict(deckId=deck['sourceDeckId'],role=role,quantity=raw['quantity']))
    return list(questions.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('questions',type=Path,nargs='?')
    parser.add_argument('--decks',type=Path,nargs='+',help='Audit current deck imports without running a gauntlet')
    parser.add_argument('--focal-id',type=int)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if bool(args.questions)==bool(args.decks):parser.error('Choose questions.json or --decks')
    if args.decks:
        from simulator import RulesBridge
        with RulesBridge() as rules:
            questions=questions_from_decks(rules,[json.loads(p.read_text()) for p in args.decks])
    else:questions=json.loads(args.questions.read_text())['unsupportedCardQuestions']
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(build_report(questions,args.focal_id),indent=2)+'\n')

if __name__=='__main__':main()
