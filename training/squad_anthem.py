"""Whole-text Squad casting cost composed with a live other-tribe anthem.

Squad is a paid casting choice whose count creates a triggered ETB copy batch;
the copied creatures retain their printed static rules (not counters or buffs).
"""
import re
from oracle_abilities import compile_abilities


def parse(text,types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=2:return None
    squad=re.fullmatch(r'Squad ((?:\{(?:[0-9]+|[WUBRGC])\})+)',lines[0])
    anthem=re.fullmatch(r'Other ([A-Z][a-z]+(?: [A-Z][a-z]+)*) you control get '
                        r'\+([1-9][0-9]*)/\+([1-9][0-9]*)\.',lines[1])
    if not squad or not anthem:return None
    program=compile_abilities(lines[1])
    if not program or len(program.static_effects)!=1 or program.triggers or program.activations:return None
    effect=program.static_effects[0]
    if not effect.subject.other or effect.power!=int(anthem[2]) or effect.toughness!=int(anthem[3]):return None
    return squad[1],program.static_effects
