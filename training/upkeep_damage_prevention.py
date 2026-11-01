"""Whole-Oracle compiler for recurring upkeep damage plus life-gain prevention.

Self-reference may say "this enchantment" or match the supplied card name;
no card-specific name is recognized by the grammar.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class UpkeepDamagePrevention:
    damage: int


def parse(text: str, name: str, types) -> UpkeepDamagePrevention | None:
    if 'Enchantment' not in types or not name:
        return None
    pattern=(r"At the beginning of each player's upkeep, (?:this enchantment|" + re.escape(name) + r')' +
             r' deals ([1-9][0-9]{0,2}) damage to that player\.\n'
             r'If a player would gain life, that player gains no life instead\.')
    match=re.fullmatch(pattern,text)
    return UpkeepDamagePrevention(int(match.group(1))) if match else None
