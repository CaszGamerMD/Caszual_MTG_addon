"""Whole Oracle grammar for paid multikicker, entry counters and a live anthem.

The multikicker count is a casting choice; the counters are an entry
replacement, and other creatures receive a continuous counter-scaled bonus.
"""
import re


_COST=r'((?:\{(?:[0-9]+|[WUBRGC])\})+)'
_NUMBER={'a':1,'one':1,'two':2,'three':3,'four':4}


def parse(text,types):
    if 'Creature' not in types:return None
    lines=[line.strip() for line in text.splitlines()]
    if len(lines)!=3:return None
    kicker=re.fullmatch(r'Multikicker '+_COST,lines[0])
    enter=re.fullmatch(
        r'This creature enters with (a|one|two|three|four|[1-9][0-9]*) '
        r'\+1/\+1 counters? on it for each time it was kicked\.',lines[1])
    anthem=re.fullmatch(
        r'Other ([A-Z][a-z]+(?: [A-Z][a-z]+)*) creatures you control get '
        r'\+([1-9][0-9]*)/\+([1-9][0-9]*) for each \+1/\+1 counter '
        r'on this creature\.',lines[2])
    if not (kicker and enter and anthem):return None
    counters=_NUMBER.get(enter[1])
    if counters is None:counters=int(enter[1])
    return kicker[1],counters,anthem[1],int(anthem[2]),int(anthem[3])
