"""Exact-text, reusable tribal entry triggers that counter their source.

"Your team" is interpreted as just the controller in this diagnostic's
strict two-player, no-teammates sandbox. Multiplayer teams remain unsupported.
"""
from dataclasses import dataclass
import re

from creature_types import valid_creature_choice


@dataclass(frozen=True)
class TribalEntryCounter:
    subtype: str
    amount: int
    team: bool = False

    def __post_init__(self):
        if not valid_creature_choice(self.subtype) or not 1<=self.amount<=1000:
            raise ValueError('Unsupported tribal entry counter')


_ENTRY=re.compile(
    r'Whenever another ([A-Z][A-Za-z-]+) (you control|your team controls) enters, '
    r'put (a|[1-9][0-9]{0,2}) \+1/\+1 counters? on this creature\.'
)


def parse(text,types):
    if 'Creature' not in types:return None
    match=_ENTRY.fullmatch(text)
    if not match:return None
    amount=1 if match[3]=='a' else int(match[3])
    if (amount==1 and 'counter on' not in text or
            amount!=1 and 'counters on' not in text):return None
    try:return TribalEntryCounter(match[1],amount,match[2]=='your team controls')
    except ValueError:return None
