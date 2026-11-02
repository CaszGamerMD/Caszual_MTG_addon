"""Whole-Oracle combination of each-upkeep tokens and controlled tribal entry life."""
from dataclasses import dataclass
import re

from creature_types import valid_creature_choice
from oracle_abilities import TokenSpec, parse_token_creation


@dataclass(frozen=True)
class UpkeepTokenEntryLife:
    token: TokenSpec
    entry_subtype: str


_UPKEEP=re.compile(r'At the beginning of each upkeep, ([Cc]reate .+\.)')
_LIFE=re.compile(r'Whenever another ([A-Z][A-Za-z-]+) you control enters, '
                 r'you gain life equal to its toughness\.')


def parse(text: str, types) -> UpkeepTokenEntryLife | None:
    if 'Creature' not in types:return None
    lines=text.splitlines()
    if len(lines)!=2:return None
    upkeep=_UPKEEP.fullmatch(lines[0]);life=_LIFE.fullmatch(lines[1])
    if not upkeep or not life or not valid_creature_choice(life[1]):return None
    spec=parse_token_creation(upkeep[1][0].upper()+upkeep[1][1:])
    return UpkeepTokenEntryLife(spec,life[1]) if spec else None
