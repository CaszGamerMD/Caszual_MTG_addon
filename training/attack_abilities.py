"""Whole-program grammar for keyword/crew/saddle and self attack effects."""
import re
from oracle_abilities import KEYWORDS, parse_token_creation

def compile(text):
    keywords=set();crew=saddle=None;effects=[]
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        words={w.strip().lower() for w in line.split(',')}
        if words<=KEYWORDS: keywords.update(words);continue
        # A saddled Mount's attack trigger creates noncreature Treasure tokens.
        # The complete instruction is required; saddle is checked at attack time.
        treasure=re.fullmatch(
            r'Whenever this creature attacks while saddled, create (a|one|two|three|four|[1-9][0-9]*) Treasure tokens?\.',line)
        if treasure:
            amount={'a':1,'one':1,'two':2,'three':3,'four':4}.get(treasure[1])
            effects.append(('saddled_treasures',amount if amount is not None else int(treasure[1]),0,''))
            continue
        group=re.fullmatch(r'Whenever this creature and at least (one|two|three|[1-9][0-9]*) other creatures attack, (create .+)',line)
        saddled=re.fullmatch(r'Whenever this creature attacks while saddled, (create .+)',line)
        token=re.fullmatch(r'Whenever this creature attacks, (create .+)',line)
        if group or token or saddled:
            clause=group[2] if group else token[1] if token else saddled[1]
            spec=parse_token_creation(clause[:1].upper()+clause[1:])
            if not spec:return None
            minimum=({'one':1,'two':2,'three':3}.get(group[1]) or int(group[1])) if group else 0
            effects.append(('group_tokens' if group else 'saddled_tokens' if saddled else 'attack_tokens',minimum,0,spec));continue
        target_grant=re.fullmatch(
            r'Whenever this creature attacks, target (legendary|nonlegendary) creature you control gains (.+) until end of turn\.',line)
        if target_grant:
            words=tuple(sorted(set(w.strip() for w in re.split(r', | and ',target_grant[2].replace(', and ', ', ')))))
            if not words or not set(words)<=KEYWORDS:return None
            effects.append(('attack_target_keywords',int(target_grant[1]=='legendary'),0,words))
            continue
        team_grant=re.fullmatch(
            r'Whenever this creature attacks, creatures you control gain (.+) until end of turn\.',
            line)
        if team_grant:
            words=tuple(sorted(set(w.strip() for w in re.split(r', | and ',team_grant[1]))))
            if not words or not set(words)<=KEYWORDS:return None
            effects.append(('attack_team_keywords',0,0,words))
            continue
        m=re.fullmatch(r"Whenever this creature attacks, put a \+1/\+1 counter on it, then create a number of (.+) equal to this creature's power\.",line)
        if m:
            token=parse_token_creation('Create a '+m[1]+'.')
            if token: effects.append(('counter_power_tokens',1,0,token));continue
            return None
        greatest=re.fullmatch(
            r'Whenever this creature attacks, it gets \+([X0])/\+([X0]) until end of turn, where X is the greatest power among creatures you control\.',
            line)
        if greatest:
            if 'X' not in greatest.groups():return None
            effects.append(('greatest_power_boost',int(greatest[1]=='X'),
                            int(greatest[2]=='X'),''));continue
        attacking=re.fullmatch(
            r'Whenever this creature attacks, it gets \+([0-9]+)/\+([0-9]+) until end of turn for each other attacking ([A-Z][a-z]+)\.',line)
        if attacking:
            effects.append(('attacking_subtype_boost',int(attacking[1]),int(attacking[2]),attacking[3]))
            continue
        m=re.fullmatch(r'Whenever this creature attacks, it gets \+([0-9]+)/\+([0-9]+) until end of turn for each other ([A-Z][a-z]+) you control\.',line)
        if m:effects.append(('subtype_count_boost',int(m[1]),int(m[2]),m[3]));continue
        m=re.fullmatch(r'(Crew|Saddle) ([1-9][0-9]*)',line)
        if m:
            if m[1]=='Crew': crew=int(m[2])
            else: saddle=int(m[2])
            continue
        m=re.fullmatch(r'Whenever this (?:creature|Vehicle) attacks, put a \+1/\+1 counter on it\.',line)
        if m: effects.append(('counter',1,1,''));continue
        m=re.fullmatch(r'Whenever this creature attacks while saddled, it gets \+([0-9]+)/\+([0-9]+) and gains (flying|trample|lifelink|vigilance|menace) until end of turn\.',line)
        if m: effects.append(('saddled_boost',int(m[1]),int(m[2]),m[3]));continue
        return None
    return (frozenset(keywords),crew,saddle,tuple(effects)) if effects else None
