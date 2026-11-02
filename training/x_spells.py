"""Whole-text variable sorceries, with X chosen explicitly at cast time."""
from oracle_abilities import parse_token_creation
from mana_pool import requirements
from card_events import rule_text

def parse(cost,text,types):
    text=rule_text(text)
    if types != ['Sorcery'] or '{X}' not in cost or requirements(cost,0) is None: return None
    if text.startswith('Create X '):
        token=parse_token_creation('Create a '+text[len('Create X '):])
        if token: return {'effect':'tokens','token':token}
    if text=='Draw X cards.': return {'effect':'draw'}
    if text=='You gain X life.': return {'effect':'life'}
    if text==('Reveal the top X cards of your library. You may put any number of permanent cards '
              'with mana value X or less from among them onto the battlefield. Then put all cards '
              "revealed this way that weren't put onto the battlefield into your graveyard."):
        return {'effect':'wave'}
    return None
