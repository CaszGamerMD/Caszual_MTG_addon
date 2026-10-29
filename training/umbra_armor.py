"""Whole-Oracle Aura grammar for the umbra armor destruction replacement.

Umbra armor is not regeneration: it does not tap or remove the creature
from combat, and it never saves a creature from zero toughness or sacrifice.
"""
from attachments import parse as parse_attachment

def parse(text,types,subtypes):
    if 'Enchantment' not in types or 'Aura' not in subtypes:
        return None
    lines=text.splitlines()
    if len(lines)<3 or lines[-1] not in ('Umbra armor','Totem armor'):
        return None
    attachment=parse_attachment('\n'.join(lines[:-1]),types,subtypes)
    return attachment if attachment and attachment[0]=='aura' else None
