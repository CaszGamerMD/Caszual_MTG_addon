"""Complete Oracle grammar for discard-as-cost token creation.

Composes with a separate attack-group draw trigger only if BOTH lines parse.
No extra clauses are ignored, and a discard is an activation cost, not an effect.
"""
import re
from attack_group_draw import parse as parse_group_draw
from oracle_abilities import parse_token_creation

def parse(text, types):
    if not set(types) & {'Creature','Artifact','Enchantment'}:
        return None
    lines=text.splitlines()
    if len(lines)==2:
        group=parse_group_draw(lines[0],types)
        if not group:return None
        activation=lines[1]
    elif len(lines)==1:
        group=()
        activation=lines[0]
    else:return None
    match=re.fullmatch(r'((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+), Discard a card: (Create .+\.)',activation)
    if not match:return None
    spec=parse_token_creation(match[2])
    if spec is None:return None
    return group,(match[1],spec)
