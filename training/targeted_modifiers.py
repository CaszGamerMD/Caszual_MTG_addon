"""Strict whole-text targeted temporary stat/keyword spell grammar."""
import re
from oracle_abilities import KEYWORDS


def parse(text, types):
    if not set(types).intersection({'Instant','Sorcery'}):return None
    choice=re.fullmatch(
        r'Target creature gets ([+-][0-9]+)/([+-][0-9]+) and gains your choice of ([a-z]+) or ([a-z]+) until end of turn\.',
        text)
    if choice:
        keywords=(choice[3],choice[4])
        if keywords[0]==keywords[1] or not set(keywords)<=KEYWORDS-{'flash'}:return None
        return (int(choice[1]),int(choice[2]),keywords,'')
    conditional_draw=re.fullmatch(
        r'Target creature gets ([+-][0-9]+)/([+-][0-9]+) until end of turn\\. If you control an? ([A-Z][a-z]+), draw a card\\.',
        text)
    if conditional_draw:
        return (int(conditional_draw[1]),int(conditional_draw[2]),(),conditional_draw[3])
    return None
