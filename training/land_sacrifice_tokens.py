"""Compose a known static ability with mana/tap/sacrifice-land token creation."""
from dataclasses import dataclass
import re

from oracle_abilities import StaticEffect, TokenSpec, static_effect, parse_token_creation


@dataclass(frozen=True)
class LandSacrificeTokens:
    cost: str
    token: TokenSpec
    artifact: bool
    enchantment: bool
    static_effects: tuple[StaticEffect, ...]


_ACTION=re.compile(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), \{T\}, '
                   r'Sacrifice a land: (Create .+\.)')


def parse(text: str, types) -> LandSacrificeTokens | None:
    if not set(types).intersection({'Enchantment','Artifact','Creature'}):return None
    lines=text.splitlines()
    if len(lines)!=2:return None
    static=static_effect(lines[0])
    if static is None:return None
    effect=_ACTION.fullmatch(lines[1])
    if not effect:return None
    creation=effect[2]
    artifact=False;enchantment=False
    for adjective,art,ench in ((' enchantment artifact',True,True),
                               (' artifact enchantment',True,True),
                               (' enchantment',False,True),(' artifact',True,False)):
        if adjective+' creature token' in creation:
            creation=creation.replace(adjective+' creature token',' creature token',1)
            artifact=art;enchantment=ench
            break
    token=parse_token_creation(creation)
    if not token:return None
    return LandSacrificeTokens(effect[1],token,artifact,enchantment,
        static if isinstance(static,tuple) else (static,))
