"""Full-text counter-scaling Equipment with alternate planeswalker equip cost."""
import re

COST=r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)'

def parse(text,types,subtypes):
    if not ('Artifact' in types and 'Equipment' in subtypes):return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)!=4:return None
    bonus=re.fullmatch(r'Equipped creature gets \+([0-9]+)/\+([0-9]+) for each counter on it\.',lines[0])
    conversion=(lines[1]=="Equipped permanent isn't a planeswalker and is a creature in addition to its other types.")
    alternate=re.fullmatch(r'Equip planeswalker '+COST,lines[2])
    standard=re.fullmatch(r'Equip '+COST,lines[3])
    if not (bonus and conversion and alternate and standard):return None
    if not (int(bonus[1]) or int(bonus[2])):return None
    return (('equipment',standard[1],frozenset(),0,0),
            (int(bonus[1]),int(bonus[2])),alternate[1])
