"""Whole-text Mentor grammar, with temporary combat-token obligations."""
from dataclasses import replace
import re
from oracle_abilities import Trigger, Selector, Effect, parse_token_creation

def parse(text, types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0]!='Mentor':return None
    if len(lines)==1:return ()
    if len(lines)!=2:return None
    m=re.fullmatch(
        r'At the beginning of combat on your turn, (create (?:a|an|one|two|three|four|[1-9][0-9]*) '
        r'[0-9]+/[1-9][0-9]* (?:white|blue|black|red|green|colorless) '
        r'[A-Z][a-z]+(?: [A-Z][a-z]+)* creature tokens?)\. '
        r'That token gains haste until end of turn and attacks this combat if able\.',lines[1])
    if not m:return None
    spec=parse_token_creation(m[1][0].upper()+m[1][1:]+'.')
    if not spec or spec.amount!=1:return None
    spec=replace(spec,temporary_haste=True,must_attack_this_combat=True)
    return (Trigger('begin_combat',Selector(self_only=True),
                    Effect('create_tokens',spec.amount,token=spec)),)
