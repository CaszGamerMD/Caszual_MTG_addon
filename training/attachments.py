"""Whole-text attachment ability grammar."""
import re
from oracle_abilities import KEYWORDS

def parse(text,types,subtypes):
    mode='equipment' if 'Artifact' in types and 'Equipment' in subtypes else 'aura' if 'Enchantment' in types and 'Aura' in subtypes else ''
    if not mode:return None
    lines=text.splitlines();cost=None;abilities=set();power=toughness=0
    if mode=='aura':
        if not lines or lines.pop(0)!='Enchant creature':return None
    prefix='Equipped' if mode=='equipment' else 'Enchanted'
    for line in lines:
        line=line.strip()
        m=re.fullmatch(r'Equip (\{[0-9]{1,2}\})',line)
        if m and mode=='equipment':cost=m[1];continue
        m=re.fullmatch(prefix+r' creature has (.+)\.',line)
        if m:
            keywords=set(re.split(r', | and ',m[1]))
            if not keywords<=KEYWORDS:return None
            abilities.update(keywords);continue
        m=re.fullmatch(prefix+r' creature gets \+([0-9]+)/\+([0-9]+)\.',line)
        if m:power+=int(m[1]);toughness+=int(m[2]);continue
        return None
    if not abilities and not power and not toughness:return None
    if mode=='equipment' and cost is None:return None
    return mode,cost,frozenset(abilities),power,toughness
