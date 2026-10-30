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


def parse_charge(text,name,types,subtypes):
    """Charge counters on Equipment itself, distinct from counters on the host."""
    if not ('Artifact' in types and 'Equipment' in subtypes):return None
    if name:text=text.replace(name,'this artifact')
    lines=text.splitlines()
    if len(lines)!=3:return None
    trigger=re.fullmatch(r'Whenever you gain life, put (a|one|two|three|[1-9][0-9]*) charge counters? on this artifact\.',lines[0])
    scale=re.fullmatch(r'Equipped creature gets \+([0-9]+)/\+([0-9]+) for each charge counter on this artifact\.',lines[1])
    equip=re.fullmatch(r'Equip '+COST,lines[2])
    if not (trigger and scale and equip) or not (int(scale[1]) or int(scale[2])):return None
    amount={'a':1,'one':1,'two':2,'three':3}.get(trigger[1])
    return (amount if amount is not None else int(trigger[1]),
            (int(scale[1]),int(scale[2])),equip[1])
