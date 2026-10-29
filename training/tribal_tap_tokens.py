"""Complete Oracle grammar for a tap ability creating X subtype-counted tokens."""
import re
from oracle_abilities import parse_token_creation

def parse(text,types):
    if not types.intersection({'Creature','Artifact','Enchantment'}):return None
    match=re.fullmatch(
        r'\{T\}: Create X ([0-9]+)/([1-9][0-9]*) (white|blue|black|red|green|colorless) '
        r'([A-Z][a-z]+(?: [A-Z][a-z]+)*) creature tokens, where X is the number of '
        r'([A-Z][a-z]+)s you control\.',text)
    if not match:return None
    spec=parse_token_creation('Create a '+match[1]+'/'+match[2]+' '+match[3]+' '+match[4]+' creature token.')
    return (spec,match[5]) if spec else None
