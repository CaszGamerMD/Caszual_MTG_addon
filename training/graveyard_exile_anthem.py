"""Whole-program grammar for opposing creature anthem plus targeted graveyard exile."""
import re
from oracle_abilities import static_effect, parse_token_creation
from mana_pool import requirements

def parse(text,types):
    if set(types)!={'Enchantment'}:return None
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(lines)!=3:return None
    first,second=(static_effect(line) for line in lines[:2])
    if first is None or second is None or isinstance(first,tuple) or isinstance(second,tuple):
        return None
    if first.subject.relation!='controller' or second.subject.relation!='opponent':
        return None
    if not first.subject.creature or not second.subject.creature:return None
    m=re.fullmatch(r"((?:\{(?:[0-9]+|[WUBRGC])\})+): Exile target card from an opponent's graveyard\. If it was a creature card, you create (.+)\.",lines[2])
    if not m or requirements(m[1]) is None:return None
    spec=parse_token_creation('Create '+m[2]+'.')
    if spec is None:return None
    return (first,second),(m[1],spec)
