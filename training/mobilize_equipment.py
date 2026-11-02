"""Complete Equipment granting power-based mobilize plus ordinary keywords.

Mobilize is keyword rules text: on attack create X tapped-and-attacking
1/1 red Warriors, where X is the source creature's power at resolution,
then sacrifice exactly those tokens at the beginning of the next end step.
"""
import re
from attachments import _keyword_grants


def parse(text,types,subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=2:return None
    rule=re.fullmatch(r'Equipped creature has (.+) and mobilize X, where X is its power\.',lines[0])
    equip=re.fullmatch(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',lines[1])
    if not rule or not equip:return None
    keywords=_keyword_grants(rule[1])
    if not keywords:return None
    return ('equipment',equip[1],frozenset(keywords),0,0)
