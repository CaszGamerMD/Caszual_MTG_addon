"""Typed intervening-if uniqueness gate for nontoken creature ETB draws.

The name predicate is checked when the event triggers and when it resolves.
It reads the controller's current creatures and creature cards in graveyard,
excluding the entering creature itself from the "another creature" test.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class UniqueCreatureEntryDraw:
    amount: int

    def __post_init__(self):
        if not 1 <= self.amount <= 1000:
            raise ValueError('Unsupported unique creature draw amount')


_DRAW=re.compile(
    r"Whenever a nontoken creature you control enters, if it doesn't have "
    r'the same name as another creature you control or a creature card in '
    r'your graveyard, draw (a|[1-9][0-9]{0,2}) cards?\.'
)


def parse(text,types):
    if not set(types).intersection({'Creature','Artifact','Enchantment'}):return None
    match=_DRAW.fullmatch(text)
    if not match:return None
    amount=1 if match[1]=='a' else int(match[1])
    if (amount==1 and not text.endswith('draw a card.') and
            not text.endswith('draw 1 card.') or
            amount!=1 and not text.endswith('cards.')):return None
    try:return UniqueCreatureEntryDraw(amount)
    except ValueError:return None
