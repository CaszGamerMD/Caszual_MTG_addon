"""Typed two-target equipment attachment activated ability.

Source cards are arbitrary. Both targets are chosen before paying costs and
remain independently targetable objects on the stack until resolution.
"""
from dataclasses import dataclass
import re

import mana_pool


@dataclass(frozen=True)
class AttachEquipment:
    mana_cost: str
    tap_cost: bool = True

    def __post_init__(self):
        if not self.tap_cost or mana_pool.requirements(self.mana_cost) is None:
            raise ValueError('Unsupported equipment attachment cost')


_ATTACH=re.compile(
    r'(?:(\{(?:[0-9]{1,2}|[WUBRGC])\}(?:\{(?:[0-9]{1,2}|[WUBRGC])\})*), )?'
    r'\{T\}: Attach target Equipment you control to target creature you control\.'
)


def parse(text,types):
    if not set(types).intersection({'Creature','Artifact','Enchantment'}):return None
    match=_ATTACH.fullmatch(text)
    if not match:return None
    try:return AttachEquipment(match[1] or '{0}')
    except ValueError:return None
