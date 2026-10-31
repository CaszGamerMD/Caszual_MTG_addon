"""Strict Oracle grammar for tap-to-gain-life abilities with live subtype counts.

This describes the source's activated ability without evaluating or caching the
number of matching creatures. The count is calculated as the ability resolves.
"""
import re


def parse_counted(text, types):
    if 'Creature' not in types:
        return None
    match=re.fullmatch(
        r'\{T\}: You gain ([1-9][0-9]*) life for each '
        r'([A-Z][a-z]+|creature) (you control|on the battlefield)\.',text)
    if not match:
        return None
    amount=int(match[1])
    subtype='Creature' if match[2]=='creature' else match[2]
    scope='controller' if match[3]=='you control' else 'all'
    return (amount,subtype,scope)
