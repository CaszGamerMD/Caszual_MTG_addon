"""Whole-Oracle grammar for end-step life-gain counter distributions.

This family chooses any number of distinct OTHER legal creature targets and the
distribution at trigger placement, with life gain measured for the current turn.
"""
import re

KEYWORDS=frozenset({'lifelink','vigilance','flying','reach','trample','hexproof',
                    'first strike','double strike','deathtouch','menace','haste'})

def parse(text, types):
    if 'Creature' not in types:return ()
    m=re.fullmatch(
        r'([A-Z][a-z]+(?:, [a-z]+)*)\n'
        r'At the beginning of each end step, if you gained life this turn, '
        r'distribute up to that many \+1/\+1 counters among any number of other target creatures\.',
        text)
    if not m:return ()
    words=frozenset(word.lower() for word in m[1].split(', '))
    return words if words and words<=KEYWORDS else ()
