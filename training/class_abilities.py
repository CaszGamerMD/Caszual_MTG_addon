"""Strict class enchantment: two paid level abilities and continuous/attack rules."""
import re
from oracle_abilities import KEYWORDS


def parse(text,types,subtypes):
    if 'Enchantment' not in types or 'Class' not in subtypes:return None
    lines=text.splitlines()
    if len(lines)!=5:return None
    tax=re.fullmatch(r'Spells your opponents cast during your turn cost \{([1-9][0-9]*)\} more to cast\.',lines[0])
    level2=re.fullmatch(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+): Level 2',lines[1])
    anthem=re.fullmatch(r'Creatures you control get \+([0-9]+)/\+([0-9]+)\.',lines[2])
    level3=re.fullmatch(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+): Level 3',lines[3])
    attack=re.fullmatch(
        r'Whenever you attack, until end of turn, target attacking creature gets '
        r'\+([0-9]+)/\+([0-9]+) for each other attacking creature and gains ([a-z ]+)\.',
        lines[4])
    if not all((tax,level2,anthem,level3,attack)):return None
    if attack[3] not in KEYWORDS-{'flash'}:return None
    return (int(tax[1]),level2[1],int(anthem[1]),int(anthem[2]),
            level3[1],int(attack[1]),int(attack[2]),attack[3])
