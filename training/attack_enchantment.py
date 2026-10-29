"""Strict complete-text grammar for attack-token and self-sacrifice team enchantments."""
import re
from oracle_abilities import parse_token_creation

def parse(text,types):
    if 'Enchantment' not in types:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)!=2:return None
    attack=re.fullmatch(r'Whenever a nontoken creature you control attacks, (create .+)',lines[0])
    sacrifice=re.fullmatch(
        r'Sacrifice this enchantment: Creatures you control get \+([0-9]+)/\+([0-9]+) until end of turn\.',
        lines[1])
    if not attack or not sacrifice:return None
    spec=parse_token_creation(attack[1][0].upper()+attack[1][1:])
    if not spec or not spec.tapped or not spec.attacking:return None
    return spec,(int(sacrifice[1]),int(sacrifice[2]))
