"""Entire Alliance three-mode entry trigger: one choice per mode each turn.

The trigger is independent of card name and the life amount is parameterized.
Mode selection happens on trigger resolution, when previous choices are known.
"""
import re


def parse(text,types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=4 or lines[0]!=(
            "Alliance — Whenever another creature you control enters, "
            "choose one that hasn't been chosen this turn —"):
        return None
    if lines[1]!='• Put a +1/+1 counter on this creature.':return None
    if lines[2]!='• Create a tapped Treasure token.':return None
    life=re.fullmatch(r'• You gain ([1-9][0-9]*) life\.',lines[3])
    return (1,True,int(life[1])) if life else None
