"""Whole-program subtype lord with last-known-information death exile permission."""
import re
from oracle_abilities import static_effect,Trigger,Selector,Effect

def parse(text,types):
    if 'Creature' not in types:return None
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(lines)!=2:return None
    static=static_effect(lines[0])
    if static is None or isinstance(static,tuple) or not static.subject.other or not static.subject.subtype:return None
    m=re.fullmatch(r"Whenever this creature or another ([A-Z][a-z]+) you control dies, exile the top card of your library\. If it's a ([A-Z][a-z]+) creature card, you may cast that card until the end of your next turn\.",lines[1])
    if not m:return None
    return static,Trigger('dies',Selector(creature=True,self_or_controlled_subtype=m[1]),
                          Effect('exile_top_cast_permission',1,library_filter=('subtype',m[2],'creature')))
