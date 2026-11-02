"""Equipment counted by a creature's base-one P/T and optional tribal ETB attach.

Both the stat-count rule and the tribal auto-attachment must be present; an
unrecognized trailing or interpolated Oracle instruction rejects the card.
"""
import re


_MANA=r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)'


def parse(text,types,subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=3:return None
    scale=re.fullmatch(
        r'Equipped creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) for each '
        r'creature you control with base power or toughness 1\.',lines[0])
    entry=re.fullmatch(
        r'Whenever a ((?:[A-Z][a-zA-Z]+(?:, |, or | or ))+[A-Z][a-zA-Z]+) '
        r'you control enters, you may attach this Equipment to that creature\.',lines[1])
    equip=re.fullmatch(r'Equip '+_MANA,lines[2])
    if not all((scale,entry,equip)):return None
    subtypes_list=tuple(re.split(r', or |, | or ',entry[1]))
    if len(subtypes_list)<2 or len(set(subtypes_list))!=len(subtypes_list):return None
    return (equip[1],int(scale[1]),int(scale[2]),subtypes_list)
