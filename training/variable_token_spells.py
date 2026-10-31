"""Strict Oracle grammar for creature-token spells scaled by live creature counts.

Token characteristics are parsed by the existing shared token grammar. This
module recognizes only the additional 'for each [type] [scope]' quantity rule;
the number is deliberately not frozen at casting time.
"""
import re
from oracle_abilities import parse_token_creation


def parse(text, types):
    if not set(types).intersection({'Sorcery', 'Instant'}):
        return None
    if text.count(' for each ') != 1 or not text.endswith('.'):
        return None
    creation, condition = text[:-1].split(' for each ', 1)
    scope = re.fullmatch(
        r'([A-Z][a-z]+|creature) (you control|on the battlefield)', condition)
    if not scope:
        return None
    spec = parse_token_creation(creation + '.')
    if spec is None:
        return None
    kind = 'Creature' if scope[1] == 'creature' else scope[1]
    relation = 'controller' if scope[2] == 'you control' else 'all'
    return (spec, kind, relation)
