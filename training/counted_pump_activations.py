"""Reusable creature-targeted tap ability with a resolution-time count."""
from dataclasses import dataclass
import re

from counted_effect_blocks import BattlefieldCount
from creature_types import valid_creature_choice


@dataclass(frozen=True)
class CountedPump:
    count: BattlefieldCount

    def __post_init__(self):
        if not isinstance(self.count,BattlefieldCount) or self.count.card_type!='Creature':
            raise ValueError('Unsupported pump quantity source')


_PUMP=re.compile(
    r'\{T\}: Target creature gets \+X/\+X until end of turn, where X is the '
    r'number of (creatures|[A-Z][a-z]+) (on the battlefield|you control)\.'
)


def _subtype(word):
    if word=='creatures':return ''
    if word=='Elves':return 'Elf'
    if word.endswith('ies') and len(word)>4:return word[:-3]+'y'
    if word.endswith('s') and len(word)>2 and not word.endswith('ss'):
        return word[:-1]
    return None


def parse(text,types):
    if not set(types).intersection({'Creature','Artifact','Enchantment'}):return None
    match=_PUMP.fullmatch(text)
    if not match:return None
    subtype=_subtype(match[1])
    if subtype is None:return None
    if subtype and not valid_creature_choice(subtype):return None
    try:return CountedPump(BattlefieldCount(
        'any' if match[2]=='on the battlefield' else 'controller',
        card_type='Creature',subtype=subtype))
    except ValueError:return None
