"""Whole-text ETB mana trigger for entering-creature shared-type counts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SharedTypeMana:
    mana_symbol: str
    optional: bool


_ORACLE=('Whenever a creature enters, you may add an amount of {C} equal to '
         'the number of creatures you control that share a creature type with it.')


def parse(text: str, types) -> SharedTypeMana | None:
    if 'Enchantment' in types and text==_ORACLE:
        return SharedTypeMana('C',True)
    return None
