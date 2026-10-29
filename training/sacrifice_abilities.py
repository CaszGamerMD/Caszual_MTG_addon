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
    boost = re.fullmatch(r'Sacrifice an? ([A-Z][a-z]+): Target creature gets \+([0-9]+)/\+([0-9]+) until end of turn\.', text)
    if boost:
        return ('boost', boost[1], int(boost[2]), int(boost[3]))
    return None
