"""Complete, typed damage-replacement clauses for the standalone simulator.

Replacements are continuous while their source permanent is on the
battlefield; they are evaluated on the actual damage event, not as triggers.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DamageReplacement:
    operation: str
    source_filter: str
    target_filter: str
    amount: int = 0
    intrinsic: str = ''

    def __post_init__(self):
        fixed=(self.operation,self.source_filter,self.target_filter,self.amount,self.intrinsic)
        if not (fixed in (
                ('multiply','controlled_creature','any_target',2,''),
                ('multiply','attached_combat_creature','any_target',2,''),
                ('multiply','any','any_target',2,'flash'),
                ('multiply','any','any_target',2,'')) or
                (self.operation,self.source_filter,self.target_filter,self.intrinsic) in (
                    ('floor','any','controller_player',''),
                    ('add','controlled_red_or_artifact','opponent_target',''),
                    ('add','red_spell','any_target',''))
                and 1<=self.amount<=1000):
            raise ValueError('Unsupported damage replacement program')


_FLOOR=re.compile(r'Damage that would reduce your life total to less than ([1-9][0-9]{0,2}) '
                  r'reduces it to ([1-9][0-9]{0,2}) instead\.')
_CREATURE_DOUBLE=('If a creature you control would deal damage to a permanent '
                  'or player, it deals double that damage instead.')
_RED_ARTIFACT_BONUS=re.compile(
    r'If a red or artifact source you control would deal damage '
    r'to an opponent or a permanent an opponent controls, '
    r'it deals that much damage plus ([1-9][0-9]{0,2}) instead\.')
_RED_SPELL_BONUS=re.compile(
    r'If a red spell would deal damage to a permanent or player, '
    r'it deals that much damage plus ([1-9][0-9]{0,2}) '
    r'to that permanent or player instead\.')
_GLOBAL_DOUBLE=('If a source would deal damage to a permanent or player, '
                'it deals double that damage to that permanent or player instead.')


def parse(text,types):
    floor=_FLOOR.fullmatch(text)
    if floor and 'Creature' in types and floor[1]==floor[2]:
        return DamageReplacement('floor','any','controller_player',int(floor[1]))
    if text==_CREATURE_DOUBLE and set(types).intersection({'Enchantment','Artifact','Creature'}):
        return DamageReplacement('multiply','controlled_creature','any_target',2)
    bonus=_RED_ARTIFACT_BONUS.fullmatch(text)
    if bonus and set(types).intersection({'Enchantment','Artifact','Creature'}):
        return DamageReplacement('add','controlled_red_or_artifact','opponent_target',int(bonus[1]))
    spell_bonus=_RED_SPELL_BONUS.fullmatch(text)
    if spell_bonus and set(types).intersection({'Enchantment','Artifact','Creature'}):
        return DamageReplacement('add','red_spell','any_target',int(spell_bonus[1]))
    if set(types).intersection({'Enchantment','Artifact'}):
        if text=='Flash\n'+_GLOBAL_DOUBLE:
            return DamageReplacement('multiply','any','any_target',2,'flash')
        if text==_GLOBAL_DOUBLE:
            return DamageReplacement('multiply','any','any_target',2)
    return None
