"""Complete Oracle patterns for upkeep-triggered, conditional token creation."""
import re
from oracle_abilities import parse_token_creation


def parse_enchanted(text, types):
    if 'Creature' not in types:
        return ()
    m=re.fullmatch(r'At the beginning of (each|your) upkeep, if this creature is enchanted, ([Cc]reate .+\.)',text)
    if not m:
        return ()
    token=parse_token_creation(m[2][0].upper()+m[2][1:])
    if token is None:
        return ()
    return (m[1], 'enchanted', '', 1, token)


def parse_scaled(text, types):
    """An upkeep token amount based on a current creature-subtype count."""
    if 'Enchantment' not in types and 'Creature' not in types and 'Artifact' not in types:
        return ()
    m=re.fullmatch(
        r'At the beginning of (your|each) upkeep, create X ([1-9][0-9]*/[1-9][0-9]* (?:white|blue|black|red|green)(?: and (?:white|blue|black|red|green))? [A-Z][a-z]+(?: [A-Z][a-z]+)* creature tokens?(?: with [a-z, ]+)?)\, where X is half the number of ([A-Z][a-z]+) you control, rounded down\.',text)
    if not m:
        return ()
    spec=parse_token_creation('Create one '+m[2].replace('creature tokens','creature token')+'.')
    if not spec:
        return ()
    plural=m[3]
    if plural.endswith('ies'):
        counted=plural[:-3]+('ie' if plural in {'Zombies','Faeries','Pixies'} else 'y')
    elif plural.endswith('ves'):
        counted=plural[:-3]+'f'
    elif plural.endswith('s'):
        counted=plural[:-1]
    else:
        counted=plural
    if not counted:
        return ()
    return (m[1],'',counted,2,spec)
