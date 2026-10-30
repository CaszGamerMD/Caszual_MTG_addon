"""Whole-text grammar for forced creature sacrifice and its static prevention."""
import re

KEYWORDS={'flying','hexproof','reach','vigilance','trample','first strike','double strike','lifelink','deathtouch','menace','indestructible','haste','defender'}

def prevention(text,types):
    if 'Creature' not in types:return ()
    m=re.fullmatch(
        r'([A-Z][a-z]+(?:, [a-z]+)*)\n'
        r"Spells and abilities your opponents control can't cause you to sacrifice permanents\.",
        text)
    if m is None:return ()
    keywords=frozenset(x.lower() for x in m[1].split(', '))
    return keywords if keywords and keywords<=KEYWORDS else ()

def edict(text,types):
    if not set(types).intersection({'Instant','Sorcery'}):return ()
    m=re.fullmatch(
        r'(Each opponent|Each player) sacrifices (a|one|two|three|[1-9][0-9]*) creatures?\.',
        text)
    if not m:return ()
    number={'a':1,'one':1,'two':2,'three':3}.get(m[2],int(m[2]) if m[2].isdigit() else 0)
    return ('opponent' if m[1]=='Each opponent' else 'all',number)
