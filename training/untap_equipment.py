"""Complete Equipment grant of a mana-plus-untap-symbol temporary pump.

The activation belongs to the equipped creature's controller. Untapping is a
cost (before the ability reaches the stack), not part of resolution.
"""
import re


def parse(text,types,subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=2:return None
    activation=re.fullmatch(
        r'Equipped creature has "((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), '
        r'\{Q\}: This creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) '
        r'until end of turn\."',lines[0])
    equip=re.fullmatch(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',lines[1])
    if not activation or not equip:return None
    return ('equipment',equip[1],frozenset(),0,0),(activation[1],int(activation[2]),int(activation[3]))
