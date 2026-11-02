"""Whole creature Aura: goad, double enchanted combat damage, graveyard return."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class GoadDamageAura:
    return_cost: str


_SECOND=('If enchanted creature would deal combat damage to a permanent or player, '
         'it deals double that damage instead.')
_RETURN=re.compile(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+): '
                   r'Return this card from your graveyard to your hand\.')


def parse(text: str, types, subtypes) -> GoadDamageAura | None:
    if 'Enchantment' not in types or 'Aura' not in subtypes:return None
    lines=text.splitlines()
    if (len(lines)!=4 or lines[0]!='Enchant creature' or
            lines[1]!='Enchanted creature is goaded.' or lines[2]!=_SECOND):return None
    cost=_RETURN.fullmatch(lines[3])
    return GoadDamageAura(cost[1]) if cost else None
