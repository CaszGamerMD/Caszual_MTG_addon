"""Whole-text activated card draw with an activation-time named-permanent gate."""
from collections import Counter
from dataclasses import dataclass
import re

import mana_pool


@dataclass(frozen=True)
class ConditionalDraw:
    cost: str
    amount: int
    minimum: int
    permanent_type: str

    def __post_init__(self):
        if (mana_pool.requirements(self.cost) is None
                or not 1<=self.amount<=5 or not 2<=self.minimum<=20
                or self.permanent_type not in ('Land','Artifact','Creature','Enchantment')):
            raise ValueError('Unsupported named-permanent draw ability')

    def available(self,game,controller):
        names=Counter(state.definition.name for state in game.battlefield.values()
                      if state.controller==controller
                      and (game.creature(state) if self.permanent_type=='Creature'
                           else self.permanent_type in state.definition.types))
        return any(count>=self.minimum for count in names.values())


_DRAW=re.compile(
    r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), \{T\}: Draw '
    r'(a|one|two|three|four|five) cards?\. '
    r'Activate only if you control (two|three|four|five|[0-9]+) or more '
    r'(lands|artifacts|creatures|enchantments) with the same name\.'
)
_NUMBERS={'a':1,'one':1,'two':2,'three':3,'four':4,'five':5}
_TYPES={'lands':'Land','artifacts':'Artifact','creatures':'Creature','enchantments':'Enchantment'}


def parse(text,types):
    if not set(types).intersection({'Artifact','Creature','Enchantment'}):return None
    match=_DRAW.fullmatch(text)
    if not match:return None
    try:return ConditionalDraw(match[1],_NUMBERS[match[2]],
                               _NUMBERS.get(match[3]) or int(match[3]),_TYPES[match[4]])
    except ValueError:return None
