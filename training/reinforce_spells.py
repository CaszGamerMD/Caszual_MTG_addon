"""Two-zone Oracle program: cast a token sorcery or reinforce from hand.

Reinforce is an activated ability of the card in hand, not a spell mode.
Its mana payment and discard happen as costs; the target receives counters
only when the stack ability resolves.
"""
import re
from oracle_abilities import parse_token_creation


def parse(text,types):
    if 'Sorcery' not in types or not types<={'Sorcery','Kindred'}:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=2:return None
    token=parse_token_creation(lines[0])
    reinforce=re.fullmatch(
        r'Reinforce ([1-9][0-9]*)[—–-]((?:\{(?:[0-9]+|[WUBRGC])\})+)',lines[1])
    if not token or not reinforce:return None
    return token,int(reinforce[1]),reinforce[2]
