"""Whole-text entry-triggered team boost bound to live creature quantities."""
from dataclasses import dataclass
import re

from counted_effect_blocks import BattlefieldCount
from creature_types import valid_creature_choice
from oracle_abilities import KEYWORDS


@dataclass(frozen=True)
class EntryGroupModifier:
    intrinsic: str
    granted: str
    count: BattlefieldCount

    def __post_init__(self):
        if (self.intrinsic not in KEYWORDS-{'flash'}
                or self.granted not in KEYWORDS-{'flash'}
                or not isinstance(self.count,BattlefieldCount)
                or self.count.card_type!='Creature'):
            raise ValueError('Unimplemented entry group modifier')


_BODY=re.compile(
    r'When this creature enters, creatures you control gain ([a-z ]+) '
    r'and get \+X/\+X until end of turn, where X is the number of '
    r'(creatures|[A-Z][a-z]+) (you control|on the battlefield)\.'
)


def _subtype(noun):
    if noun=='creatures':return ''
    if noun=='Elves':return 'Elf'
    if noun.endswith('ies') and len(noun)>4:return noun[:-3]+'y'
    if noun.endswith('s') and len(noun)>2 and not noun.endswith('ss'):
        return noun[:-1]
    return None


def parse(text,types):
    if 'Creature' not in types:return None
    lines=text.splitlines()
    if len(lines)!=2 or lines[0].lower() not in KEYWORDS-{'flash'}:
        return None
    match=_BODY.fullmatch(lines[1])
    if not match:return None
    subtype=_subtype(match[2])
    if subtype is None or subtype and not valid_creature_choice(subtype):return None
    try:return EntryGroupModifier(lines[0].lower(),match[1],BattlefieldCount(
        'controller' if match[3]=='you control' else 'any',
        card_type='Creature',subtype=subtype))
    except ValueError:return None
