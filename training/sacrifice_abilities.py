"""Strict reusable Oracle grammar for sacrifice-as-cost activated abilities.

A complete recognized program must be executed; unrecognized extra clauses fail
closed. This parser describes the cost and effect, never card identities.
"""
import re


def parse(text, types):
    if not set(types).intersection({'Creature', 'Artifact', 'Enchantment'}):
        return None
    mana = re.fullmatch(r'Sacrifice an? ([A-Z][a-z]+): Add \{([WUBRGC])\}\.', text)
    if mana:
        return ('mana', mana[1], mana[2])
    return None
