"""Characteristic-defining P/T for counted controlled colored permanents."""
import re
from card_events import SIMPLE_ABILITIES

COLORS={'white':'White','blue':'Blue','black':'Black','red':'Red','green':'Green'}

def parse_colored_permanent_pt(text,name,types):
    if 'Creature' not in types:return None
    lines=text.splitlines()
    if not lines:return None
    characteristic=lines[-1].replace(name+"'s", "This creature's") if name else lines[-1]
    match=re.fullmatch(
        r"This creature's power and toughness are each equal to the number of (white|blue|black|red|green) permanents you control\.",
        characteristic)
    if not match:return None
    traits=set()
    for line in lines[:-1]:
        for keyword in line.lower().split(', '):
            if keyword not in SIMPLE_ABILITIES:return None
            traits.add(keyword)
    return frozenset(traits),COLORS[match[1]]
