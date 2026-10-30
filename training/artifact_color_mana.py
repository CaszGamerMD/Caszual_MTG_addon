"""Whole Oracle grammar: colored spending permission, mana tap, color-count draw."""
import re
from mana_pool import production

def parse(text, types):
    if set(types)!={'Artifact'}:return None
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(lines)!=3 or lines[0]!='You may spend mana as though it were mana of any color.':return None
    mana=production(lines[1])
    if not mana:return None
    draw=re.fullmatch(r'((?:\{(?:[0-9]+|[WUBRGC])\})+), \{T\}: Draw a card for each color among permanents you control\.',lines[2])
    if not draw or not re.search(r'\{[1-9WUBRGC]',draw[1]):return None
    return dict(mana_production=mana,mana_as_any_color=True,color_draw_cost=draw[1])
