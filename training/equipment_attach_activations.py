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
    target_mode: str = 'creature'
    sorcery_only: bool = False

    def __post_init__(self):
        if (mana_pool.requirements(self.mana_cost) is None or
                (self.target_mode,self.tap_cost,self.sorcery_only) not in
                (('creature',True,False),('self',False,True))):
            raise ValueError('Unsupported equipment attachment cost')


_ATTACH=re.compile(
    r'(?:(\{(?:[0-9]{1,2}|[WUBRGC])\}(?:\{(?:[0-9]{1,2}|[WUBRGC])\})*), )?'
    r'\{T\}: Attach target Equipment you control to target creature you control\.'
)
_SELF_ATTACH=re.compile(
    r'(\{(?:[0-9]{1,2}|[WUBRGC])\}(?:\{(?:[0-9]{1,2}|[WUBRGC])\})*): '
    r'Attach target Equipment you control to this creature\. '
    r'Activate only as a sorcery\.'
)


def parse(text,types):
    if not set(types).intersection({'Creature','Artifact','Enchantment'}):return None
    self_match=_SELF_ATTACH.fullmatch(text)
    if self_match and 'Creature' in types:
        try:return AttachEquipment(self_match[1],False,'self',True)
        except ValueError:return None
    match=_ATTACH.fullmatch(text)
    if not match:return None
    try:return AttachEquipment(match[1] or '{0}')
    except ValueError:return None
