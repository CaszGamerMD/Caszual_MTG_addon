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

def parse_counted(text, types):
    """Consume one subtype/creature-count mana clause; preserve all other lines."""
    if 'Creature' not in types:
        return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    pattern=r'\{T\}: Add \{([WUBRG])\} for each ([A-Z][a-z]+|creature) (you control|on the battlefield)\.'
    found=[(index,re.fullmatch(pattern,line)) for index,line in enumerate(lines)]
    found=[(index,match) for index,match in found if match]
    if len(found)!=1:
        return None
    index,match=found[0]
    kind='Creature' if match[2]=='creature' else match[2]
    scope='controller' if match[3]=='you control' else 'all'
    return 'count:'+match[1]+':'+kind+':'+scope, '\n'.join(line for i,line in enumerate(lines) if i!=index)
