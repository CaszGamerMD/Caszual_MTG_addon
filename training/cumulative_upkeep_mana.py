"""Whole-Oracle cumulative-upkeep programs whose payment adds mana.

Age counters are tracked independently from +1/+1 and charge counters. The
upkeep ability uses the normal trigger stack, with its count set on resolution.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class CumulativeUpkeepMana:
    symbol: str


_REMINDER=(' (At the beginning of your upkeep, put an age counter on this '
           'permanent, then sacrifice it unless you pay its upkeep cost '
           'for each age counter on it.)')
_ADD=re.compile(r'Cumulative upkeep—Add \{([WUBRGC])\}\.')


def parse(text: str, types) -> CumulativeUpkeepMana | None:
    if not set(types).intersection({'Enchantment','Artifact','Creature'}):
        return None
    core=text.removesuffix(_REMINDER)
    match=_ADD.fullmatch(core)
    return CumulativeUpkeepMana(match[1]) if match else None
