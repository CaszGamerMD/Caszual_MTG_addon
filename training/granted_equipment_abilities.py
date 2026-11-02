"""Whole Oracle equipment grammar: granted tap damage, death untap, tribal autoattach."""
from dataclasses import dataclass
import re

from creature_types import valid_creature_choice


@dataclass(frozen=True)
class GrantedEquipment:
    activation_cost: str
    damage: int
    entry_subtype: str
    equip_cost: str


_GRANT=re.compile(
    r'Equipped creature has "((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), \{T\}: '
    r'This creature deals ([1-9][0-9]{0,2}) damage to any target" and '
    r'"Whenever a creature dies, untap this creature\."')
_ENTRY=re.compile(r'Whenever a ([A-Z][A-Za-z-]+) creature enters, '
                  r'you may attach this Equipment to it\.')
_EQUIP=re.compile(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)')


def parse(text: str, types, subtypes) -> GrantedEquipment | None:
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=text.splitlines()
    if len(lines)!=3:return None
    grant=_GRANT.fullmatch(lines[0]);entry=_ENTRY.fullmatch(lines[1]);equip=_EQUIP.fullmatch(lines[2])
    if not grant or not entry or not equip or not valid_creature_choice(entry[1]):return None
    return GrantedEquipment(grant[1],int(grant[2]),entry[1],equip[1])
