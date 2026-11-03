"""Strict grammar for exile-other-cards alternate costs cast from a graveyard."""
import re

_COST=r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)'
_PATTERN=re.compile(
    r'You may cast (?:this card|this creature) from your graveyard by paying '
    +_COST+
    r' and exiling (a|one|two|three|four|[1-9][0-9]*) other cards from your graveyard rather than paying its mana cost\.'
)


def parse(text,types):
    """Consume exactly one complete alternate-cast clause; preserve all else."""
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    matches=[(index,_PATTERN.fullmatch(line)) for index,line in enumerate(lines)]
    matches=[(index,match) for index,match in matches if match]
    if len(matches)!=1:return None
    index,match=matches[0]
    count={'a':1,'one':1,'two':2,'three':3,'four':4}.get(match[2])
    if count is None:count=int(match[2])
    if not 1<=count<=20:return None
    remaining='\n'.join(line for i,line in enumerate(lines) if i!=index)
    return match[1],count,remaining
