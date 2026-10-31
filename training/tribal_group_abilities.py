"""Reusable whole-line grammar for tribal entry triggers and team mana pumps.

A once-per-turn entry trigger observes all entries in one batch but triggers
only once in a turn. The activation is an independent, mana-paid stack ability.
Unrecognized lines are returned to the compositional Oracle parser, not dropped.
"""
import re
from oracle_abilities import parse_token_creation, KEYWORDS
from variable_damage_spells import singular_type


def parse(text, types):
    if 'Creature' not in types:
        return None
    entry_rule=None
    pump_rule=None
    remainder=[]
    for line in text.splitlines():
        entry=re.fullmatch(
            r'Whenever one or more (other )?([A-Z][a-z]+) you control enter, '
            r'(create .+)\. This ability triggers only once each turn\.',
            line)
        if entry:
            if entry_rule is not None:
                return None
            subtype=singular_type(entry[2])
            spec=parse_token_creation(entry[3][0].upper()+entry[3][1:]+'.')
            if not subtype or spec is None:
                return None
            entry_rule=(subtype,spec,bool(entry[1]),True)
            continue
        pump=re.fullmatch(
            r'((?:\{(?:[0-9]+|[WUBRGC])\})+): ([A-Z][a-z]+) you control '
            r'get \+([0-9]+)/\+([0-9]+) and gain ([a-z ]+) until end of turn\.',
            line)
        if pump:
            if pump_rule is not None:
                return None
            subtype=singular_type(pump[2])
            if (not subtype or pump[5] not in KEYWORDS-{'flash'}
                    or not (int(pump[3]) or int(pump[4]))):
                return None
            pump_rule=(pump[1],subtype,int(pump[3]),int(pump[4]),pump[5])
            continue
        remainder.append(line)
    if entry_rule is None and pump_rule is None:
        return None
    return (entry_rule,pump_rule,'\n'.join(remainder))
