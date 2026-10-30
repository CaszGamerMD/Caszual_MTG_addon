"""Strict whole-Oracle creature tap-mana programs, not card-name exceptions."""
import re

def parse_fixed(text, types):
    """A creature taps for one fixed color, possibly multiple units of it."""
    if 'Creature' not in types:
        return None
    match=re.fullmatch(r'\{T\}: Add ((?:\{[WUBRG]\})+)\.', text)
    if not match:
        return None
    symbols=re.findall(r'\{([WUBRG])\}',match[1])
    if len(set(symbols))!=1:
        return None
    return 'fixed:'+symbols[0]+':'+str(len(symbols))
