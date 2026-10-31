"""Whole-Oracle grammar for Raid enters-with-counter replacement effects.

Raid is decided from actual attacks declared earlier in the same turn, not
whether attackers are still in combat. Entering with counters is a replacement
effect and must not use the trigger stack.
"""
import re


def parse(text, types):
    if 'Creature' not in types:
        return None
    lines=text.splitlines()
    found=[]
    remainder=[]
    pattern=(r'Raid — This creature enters with (a|one|two|three|[1-9][0-9]*) '
             r'\+1/\+1 counters? on it if you attacked this turn\.')
    for line in lines:
        match=re.fullmatch(pattern,line)
        if match:
            found.append(match[1])
        else:
            remainder.append(line)
    if len(found)!=1:
        return None
    word=found[0]
    count={'a':1,'one':1,'two':2,'three':3}.get(word)
    return (count if count is not None else int(word),'\n'.join(remainder))
