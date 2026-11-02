"""Complete creature-changing Aura with its independent enters-the-battlefield draw.

The grammar is deliberately independent of card name, creature type and
power/toughness values. An unsupported sentence must not be silently dropped.
"""
import re


_COLORS={
    'white':'White','blue':'Blue','black':'Black','red':'Red','green':'Green',
}


def parse(text,types,subtypes):
    if 'Enchantment' not in types or 'Aura' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=3 or lines[:2]!=['Enchant creature','When this Aura enters, draw a card.']:
        return None
    match=re.fullmatch(
        r'Enchanted creature loses all abilities and is a '
        r'(white|blue|black|red|green) ([A-Z][a-zA-Z]+) creature '
        r'with base power and toughness ([0-9]+)/([0-9]+)\.',
        lines[2])
    if not match:return None
    return (_COLORS[match[1]],match[2],int(match[3]),int(match[4]))
