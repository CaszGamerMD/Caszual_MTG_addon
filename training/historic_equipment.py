"""Closed historic-mana-value casting discount with a complete Equipment grant.

The casting reduction counts each controlled historic permanent once, including
artifacts that are also legendary. Equip targeting restrictions are compiled by
the common attachment grammar rather than inferred from the card's name.
"""
from attachments import parse as parse_attachment


def parse(text,types,subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=3 or lines[0]!=('This spell costs {X} less to cast, where X is '
        'the total mana value of historic permanents you control.'):
        return None
    attachment=parse_attachment('\n'.join(lines[1:]),types,subtypes)
    if not attachment or len(attachment)<6 or attachment[5]!='equip:legendary_creature':
        return None
    return attachment
