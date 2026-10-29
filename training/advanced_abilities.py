"""Whole-text grammars for station, entry-history activations and equipped attacks."""
import re
from dataclasses import replace
from oracle_abilities import compile_abilities,parse_token_creation,static_effect,KEYWORDS

def station(text,types,subtypes):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    if 'Artifact' not in types or 'Spacecraft' not in subtypes or not lines or lines[0]!='Station':return None
    levels=[]
    for line in lines[1:]:
        m=re.fullmatch(r'([1-9][0-9]*)\+ \| (.+)',line)
        if not m:return None
        effect=static_effect(m[2]);words=frozenset(x.strip().lower() for x in m[2].split(','))
        if effect:levels.append((int(m[1]),effect,()))
        elif words and words<=KEYWORDS:levels.append((int(m[1]),None,tuple(sorted(words))))
        else:return None
    if len(levels)<1 or [x[0] for x in levels]!=sorted(set(x[0] for x in levels)) or not levels[-1][2]:return None
    return tuple(levels)

def history(text):
    other=[];activation=None
    for line in text.splitlines():
        m=re.fullmatch(r'\{T\}: Create X (.+) creature tokens, where X is the number of ([A-Z][a-z]+) and/or ([A-Z][a-z]+) that entered the battlefield under your control this turn\. The tokens have "This token saddles Mounts and crews Vehicles as though its power were ([1-9][0-9]*) greater\."',line.strip())
        if not m:other.append(line);continue
        if activation:return None
        spec=parse_token_creation('Create a '+m[1]+' creature token.')
        if not spec:return None
        irregular={'Elves':'Elf','Faeries':'Faerie','Dwarves':'Dwarf','Wolves':'Wolf','Werewolves':'Werewolf','Mice':'Mouse','Allies':'Ally','Merfolk':'Merfolk','Fish':'Fish','Sheep':'Sheep'}
        def singular(word):
            if word in irregular:return irregular[word]
            if word.endswith('s') and not word.endswith(('ies','ves','ses','xes','ches','shes')):return word[:-1]
            return None
        watched=tuple(singular(word) for word in (m[2],m[3]))
        if None in watched:return None
        activation=(watched,replace(spec,contribution_bonus=int(m[4])))
    program=compile_abilities('\n'.join(other))
    return (program,activation) if activation and program else None

def equipped_attacks(text,types,subtypes):
    from attachments import parse
    other=[];effects=[]
    for line in text.splitlines():
        m=re.fullmatch(r'Whenever equipped creature attacks, (create .+)',line.strip())
        if m:
            spec=parse_token_creation(m[1][:1].upper()+m[1][1:])
            if not spec:return None
            effects.append(spec)
        else:other.append(line)
    attachment=parse('\n'.join(other),types,subtypes)
    return (attachment,tuple(effects)) if effects and attachment else None
