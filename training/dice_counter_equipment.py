"""Equipment attack counter plus combat-damage die roll and counter doubling.

The dice size and Equip mana are parameters; no extra Oracle clauses may be
silently ignored, and the die's maximum must match its stated special case.
"""
import re


def parse(text,types,subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=3 or lines[0]!='Whenever equipped creature attacks, put a +1/+1 counter on it.':
        return None
    roll=re.fullmatch(
        r'Whenever equipped creature deals combat damage, roll a d([0-9]+)\. '
        r'If the result is greater than the damage dealt or the result is ([0-9]+), '
        r'double the number of \+1/\+1 counters on that creature\.',lines[1])
    equip=re.fullmatch(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',lines[2])
    if not roll or not equip:return None
    sides,special=int(roll[1]),int(roll[2])
    if not 2<=sides<=1000 or special!=sides:return None
    return equip[1],sides
