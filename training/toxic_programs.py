"""Whole-text numeric toxic keyword for creatures.

Toxic adds poison counters on a positive combat-damage event to a player;
it does not replace life damage or assign poison per damage point.
"""
import re


def parse(text: str, types) -> int:
    if 'Creature' not in types:return 0
    match=re.fullmatch(r'Toxic ([1-9][0-9]{0,2})',text)
    return int(match[1]) if match else 0
