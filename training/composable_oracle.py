"""Strict compositional Oracle building block for power-scaled mana.

Parse one independently meaningful activated mana clause and return the rest
unchanged for the existing generic trigger/static/keyword compiler. A card is
not supported unless *every* remaining line compiles in that rules kernel.

Unlike name-special cases, any creature with:
  Whenever another <subtype> ... enters, put a counter on <self>.
  {T}: Add an amount of {symbol} equal to <self>'s power.
can use the same two pieces. The parser does not consult the deck ID.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

MANA_LINE=re.compile(
    r"\{T\}: Add an amount of \{([WUBRG])\} equal to "
    r"(.+?)(?:'s|’s) power\."
)

@dataclass(frozen=True)
class PowerMana:
    symbol: str
    remaining_text: str


def parse_power_mana(text: str, name: str, types) -> PowerMana | None:
    """Recognize only a complete self-power tap instruction with no extra costs."""
    if "Creature" not in types:
        return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    matches=[(index,MANA_LINE.fullmatch(line)) for index,line in enumerate(lines)]
    matching=[(index,match) for index,match in matches if match]
    if len(matching)!=1:
        return None
    index,match=matching[0]
    subject=match[2]
    # An Oracle shortened proper-name reference is allowed only if the full
    # source card name starts with it, and the short name is a whole word.
    aliases={name, "this creature"}
    if name:
        aliases.add(name.split(",")[0])
        aliases.add(name.split()[0])
    if subject not in aliases:
        return None
    # A blank remainder is valid: mana-only creatures, but no unrelated text
    # is discarded by this helper.
    return PowerMana(match[1],'\n'.join(line for i,line in enumerate(lines) if i!=index))
