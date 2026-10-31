"""Fail-closed, name-independent Oracle modal target compiler.

This module only describes options; it does not cast or execute a spell.
The caller must verify chosen targets, mana payment and stack legality.
"""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Mode:
    operation: str
    target_kind: str
    amount: int = 0

@dataclass(frozen=True)
class ModalProgram:
    choose: int
    modes: tuple[Mode, ...]

    def bind(self, selected):
        if not isinstance(selected, (tuple, list)) or len(selected) != self.choose:
            raise ValueError("Incorrect number of selected modes")
        if any(type(index) is not int or index < 0 or index >= len(self.modes)
               for index in selected) or len(set(selected)) != len(selected):
            raise ValueError("Invalid or duplicate mode selection")
        return tuple(self.modes[index] for index in selected)

_RULES = (
    (re.compile(r"Destroy target (artifact|enchantment)\.", re.I), "destroy"),
    (re.compile(r"Exile target (artifact|enchantment)\.", re.I), "exile"),
    (re.compile(r"Deal ([1-9][0-9]*) damage to target creature\.", re.I), "damage"),
    (re.compile(r"Exile target card from a graveyard\.", re.I), "exile_graveyard"),
    (re.compile(r"(.+?) deals ([1-9][0-9]*) damage to target creature\."), "source_damage"),
)

def parse(text, types, card_name=""):
    """Accept only complete, explicitly supported choose-one/two modal spells."""
    if not isinstance(text, str) or not set(types).intersection(("Instant", "Sorcery")):
        return None
    if set(types).intersection(("Creature", "Enchantment", "Artifact", "Land")):
        return None
    lines = [line.strip() for line in text.strip().splitlines()]
    if not lines or lines[0] not in ("Choose one —", "Choose two —"):
        return None
    choose = 1 if lines[0] == "Choose one —" else 2
    if not 2 <= len(lines) <= 9:
        return None
    modes = []
    for line in lines[1:]:
        if not line.startswith("• "):
            return None
        clause = line[2:]
        mode = None
        for pattern, operation in _RULES:
            match = pattern.fullmatch(clause)
            if match:
                if operation in ("damage", "source_damage"):
                    if operation=="source_damage" and card_name and match.group(1)!=card_name:
                        return None
                    amount = int(match.group(2) if operation=="source_damage" else match.group(1))
                    if amount > 1000:
                        return None
                    mode = Mode("damage", "creature", amount)
                elif operation == "exile_graveyard":
                    mode = Mode("exile", "graveyard")
                else:
                    mode = Mode(operation, match.group(1).lower())
                break
        if mode is None or mode in modes:
            return None
        modes.append(mode)
    if len(modes) < choose:
        return None
    return ModalProgram(choose, tuple(modes))
