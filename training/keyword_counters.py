"""Whole-instruction, name-independent keyword-counter entry choices."""
import re

COUNTER_KEYWORDS=frozenset({'deathtouch','lifelink','flying','first strike',
                            'double strike','menace','reach','trample','vigilance','hexproof'})

def parse_entry_choice(text,types):
    if 'Creature' not in types:return ()
    match=re.fullmatch(
        r'This creature enters with your choice of an? ([a-z]+(?: strike)?) counter or an? ([a-z]+(?: strike)?) counter on it\.',
        text)
    if not match:return ()
    choices=tuple(match.groups())
    return choices if len(set(choices))==2 and set(choices)<=COUNTER_KEYWORDS else ()
