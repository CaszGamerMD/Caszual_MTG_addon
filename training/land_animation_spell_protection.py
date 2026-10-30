"""Whole-text generic uncounterable spell categories + targeted land animation."""
import re

def parse(text,types):
    if not (set(types)&{'Creature','Enchantment','Artifact'}):return ()
    m=re.fullmatch(
        r'([A-Z][a-z]+) and ([a-z]+) spells you control can[\x27’]t be countered\.\n'
        r'((?:\{(?:[0-9]+|[WUBRGC])\})+): Target land you control becomes an X/X '
        r'([A-Z][a-z]+) creature with (trample and haste|haste and trample) until end of turn, '
        r'where X is the number of (enchantments|artifacts) you control\. It[\x27’]s still a land\.',
        text)
    if not m:return ()
    categories=(m[1].lower(),m[2].lower())
    if not set(categories)<= {'creature','enchantment','artifact'} or len(set(categories))!=2:return ()
    return (categories,m[3],m[4],m[6][:-1].title())
