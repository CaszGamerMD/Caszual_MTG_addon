"""Strict whole-Oracle parsing for spells dealing subtype-counted damage.

The target is locked when cast, while the number of creatures is checked
again on resolution. Never infer an ability from a card name.
"""
import re

IRREGULAR = {
    'Elves': 'Elf', 'Faeries': 'Faerie', 'Wolves': 'Wolf',
    'Mice': 'Mouse', 'Oxen': 'Ox', 'Allies': 'Ally',
    'Zombies': 'Zombie', 'Merfolk': 'Merfolk',
}


def singular_type(plural):
    if plural in IRREGULAR:
        return IRREGULAR[plural]
    if plural == 'creatures':
        return 'Creature'
    if re.fullmatch(r'[A-Z][a-z]+s', plural) and not plural.endswith(
            ('ies', 'ves', 'ses', 'xes', 'ches', 'shes')):
        return plural[:-1]
    return None


def parse(text, name, types):
    """Return (subtype, scope, target filter) or None if any clause is unknown."""
    if not set(types).intersection({'Instant', 'Sorcery'}):
        return None
    match = re.fullmatch(
        r'(.+?) deals damage to target (player or planeswalker) equal to '
        r'the number of ([A-Z][a-z]+|creatures) (you control|on the battlefield)\.',
        text)
    if not match:
        return None
    source = match[1]
    if source not in (name, 'This spell', 'this spell'):
        return None
    subtype = singular_type(match[3])
    if not subtype:
        return None
    return (subtype, 'controller' if match[4] == 'you control' else 'all',
            match[2])
