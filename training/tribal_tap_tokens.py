"""Complete Oracle grammar for a tap ability creating X subtype-counted tokens."""
import re
from oracle_abilities import parse_token_creation

def parse(text,types):
    if not types.intersection({'Creature','Artifact','Enchantment'}):return None
    match=re.fullmatch(
        r'\{T\}: Create X ([0-9]+)/([1-9][0-9]*) (white|blue|black|red|green|colorless) '
        r'([A-Z][a-z]+(?: [A-Z][a-z]+)*) creature tokens, where X is the number of '
        r'([A-Z][a-z]+) you control\.',text)
    if not match:return None
    plural=match[5]
    # Oracle plural forms for ordinary subtypes, including Elf/Elves and Wolf/Wolves.
    subtype=(plural[:-3]+'f' if plural.endswith('ves') else
             plural[:-1] if plural.endswith('s') else None)
    if not subtype:return None
    spec=parse_token_creation('Create a '+match[1]+'/'+match[2]+' '+match[3]+' '+match[4]+' creature token.')
    return (spec,subtype) if spec else None
