"""Compose two independent paid tribal activations without dropping either.

One activation targets another matching creature for regeneration; the other
temporarily boosts all controlled members of the tribe and grants a keyword.
"""
import re
from oracle_abilities import KEYWORDS

_COST=r'((?:\{(?:[0-9]+|[WUBRGC])\})+)'


def parse(text,types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=2:return None
    regenerate=re.fullmatch(_COST+r': Regenerate another target ([A-Z][a-z]+)\.',lines[0])
    team=re.fullmatch(_COST+r': ([A-Z][a-z]+) creatures you control get '
                      r'\+([1-9][0-9]*)/\+([1-9][0-9]*) and gain '
                      r'([a-z ]+) until end of turn\.',lines[1])
    if not (regenerate and team and regenerate[2]==team[2] and team[5] in KEYWORDS):return None
    return regenerate[1],regenerate[2],team[1],int(team[3]),int(team[4]),team[5]
