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
    # Only the one-creature, single-affected-player edict has a fully
    # implemented zone change and trigger batch. Simultaneous multi-player
    # or multi-creature sacrifice instructions must remain unsupported.
    if re.fullmatch(r'Each opponent sacrifices a creature\\.',text):
        return ('opponent',1)
    return ()
