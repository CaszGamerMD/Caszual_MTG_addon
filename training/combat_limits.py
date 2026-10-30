"""Whole Oracle grammar for attacking and blocking cardinality restrictions."""
import re

def parse(text,name,types):
    if 'Creature' not in types:return None
    if name:
        for alias in sorted({name,name.split(',')[0]},key=len,reverse=True):
            text=text.replace('Whenever '+alias+' attacks,','Whenever this creature attacks,')
            text=text.replace('As long as '+alias+' is tapped,','As long as this creature is tapped,')
    lines=text.splitlines()
    if len(lines)!=3:return None
    keywords=frozenset(part.strip().lower() for part in lines[0].split(', '))
    if not keywords or not keywords<=frozenset({'first strike','flying','vigilance','haste'}):return None
    trigger=re.fullmatch(r"Whenever this creature attacks, each opponent can't block with more than (one|two|three|[1-9][0-9]*) creatures? this combat\.",lines[1])
    static=re.fullmatch(r'As long as this creature is tapped, no more than (one|two|three|[1-9][0-9]*) creatures? can attack you each combat\.',lines[2])
    if not trigger or not static:return None
    numbers={'one':1,'two':2,'three':3}
    return keywords,(numbers.get(trigger[1]) or int(trigger[1]),numbers.get(static[1]) or int(static[1]))
