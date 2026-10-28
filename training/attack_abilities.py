"""Whole-program grammar for keyword/crew/saddle and self attack effects."""
import re
from oracle_abilities import KEYWORDS

def compile(text):
    keywords=set();crew=saddle=None;effects=[]
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        words={w.strip().lower() for w in line.split(',')}
        if words<=KEYWORDS: keywords.update(words);continue
        m=re.fullmatch(r'(Crew|Saddle) ([1-9][0-9]*)',line)
        if m:
            if m[1]=='Crew': crew=int(m[2])
            else: saddle=int(m[2])
            continue
        m=re.fullmatch(r'Whenever this (?:creature|Vehicle) attacks, put a \+1/\+1 counter on it\.',line)
        if m: effects.append(('counter',1,1,''));continue
        m=re.fullmatch(r'Whenever this creature attacks while saddled, it gets \+([0-9]+)/\+([0-9]+) and gains (flying|trample|lifelink|vigilance) until end of turn\.',line)
        if m: effects.append(('saddled_boost',int(m[1]),int(m[2]),m[3]));continue
        return None
    return (frozenset(keywords),crew,saddle,tuple(effects)) if effects else None
