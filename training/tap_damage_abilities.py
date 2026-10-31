"""Composable Oracle clauses: doesn't untap, untaps on deaths, and tap damage.

These are independent ability blocks. A creature may have any combination,
and no text may be ignored: unrecognized lines are handed to the ordinary
whole-program parser, which must itself succeed.
"""
import re


def parse(text,types):
    if 'Creature' not in types:
        return None
    skip=False;death=False;damage=0;other=[]
    for line in text.splitlines():
        if line=="This creature doesn't untap during your untap step.":
            if skip:return None
            skip=True
        elif line=='Whenever a creature dies, untap this creature.':
            if death:return None
            death=True
        elif m:=re.fullmatch(
                r'\{T\}: This creature deals ([1-9][0-9]*) damage to any target\.',
                line):
            if damage:return None
            damage=int(m[1])
        else:
            other.append(line)
    if not (skip or death or damage):
        return None
    return (skip,death,damage,'\n'.join(other))
