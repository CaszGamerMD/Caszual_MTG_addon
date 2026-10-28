"""Whole-text variable sorceries, with X chosen explicitly at cast time."""
from oracle_abilities import parse_token_creation
from mana_pool import requirements

def parse(cost,text,types):
    if types != ['Sorcery'] or '{X}' not in cost or requirements(cost,0) is None: return None
    if text.startswith('Create X '):
        token=parse_token_creation('Create a '+text[len('Create X '):])
        if token: return {'effect':'tokens','token':token}
    if text=='Draw X cards.': return {'effect':'draw'}
    if text=='You gain X life.': return {'effect':'life'}
    return None
