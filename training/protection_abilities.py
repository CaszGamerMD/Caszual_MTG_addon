"""Reusable complete-text grammar for mana plus self-sacrifice protection activations."""
import re
import mana_pool
from oracle_abilities import KEYWORDS

def parse(text,types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)!=2:return None
    keywords=frozenset(word.strip().lower() for word in lines[0].split(','))
    if not keywords or not keywords <= KEYWORDS-{'flash'}:return None
    m=re.fullmatch(
        r'((?:\{(?:[0-9]+|[WUBRGC])\})+), Sacrifice this creature: '
        r'Target (creature|creature or enchantment) you control gains protection from '
        r'the color of your choice until end of turn\.',lines[1])
    if not m or mana_pool.requirements(m[1]) is None:return None
    kinds=('Creature','Enchantment') if m[2]=='creature or enchantment' else ('Creature',)
    return keywords,m[1],kinds
