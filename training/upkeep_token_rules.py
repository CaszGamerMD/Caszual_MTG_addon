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


