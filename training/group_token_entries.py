"""Recognize batch-wide 'one or more tokens enter' +1/+1 counter triggers.

A group of simultaneous tokens causes one ability trigger, not one per token.
Ability words are stripped only when an exactly supported rule follows them.
"""
import re


def parse(text, types):
    if 'Creature' not in types:
        return None
    pattern=(r'(?:[A-Z][A-Za-z ]+ — )?Whenever one or more tokens you control '
             r'enter, put (a|one|two|three) \+1/\+1 counters? on this creature\.')
    match=re.fullmatch(pattern,text)
    if not match:
        return None
    return {'a':1,'one':1,'two':2,'three':3}[match[1]]
