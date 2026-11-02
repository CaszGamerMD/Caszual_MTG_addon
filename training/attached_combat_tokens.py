"""Complete beginning-of-combat attached-Aura/Equipment token program.

The source name may be printed as its own name or as 'this creature'. Each
generated token is recorded for an independent delayed end-step exile.
"""
import re
from oracle_abilities import parse_token_creation


def parse(text,name,types):
    if 'Creature' not in types:return None
    match=re.fullmatch(
        r'At the beginning of combat on your turn, for each Aura and Equipment '
        r'attached to (.+?), create (a [0-9]+/[0-9]+ .+ creature token with .+)\. '
        r'Exile those tokens at the beginning of the next end step\.',text)
    if not match or match[1] not in (name,name.split(',')[0],'this creature'):return None
    spec=parse_token_creation('Create '+match[2]+'.')
    if not spec or spec.amount!=1 or spec.land or spec.enchantment:return None
    return spec
