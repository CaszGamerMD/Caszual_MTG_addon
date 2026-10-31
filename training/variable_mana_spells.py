"""Whole-Oracle mana-producing spells that scale with live creature counts.

Counts are evaluated when the spell resolves. They do not create a new mana
source; they add the resulting mana to the casting player's mana pool.
"""
import re


def parse(text, types):
    if not set(types).intersection({'Instant','Sorcery'}):
        return None
    match=re.fullmatch(
        r'Add \{([WUBRG])\} for each ([A-Z][a-z]+|creature) '
        r'(you control|on the battlefield)\.',text)
    if not match:
        return None
    subtype='Creature' if match[2]=='creature' else match[2]
    scope='controller' if match[3]=='you control' else 'all'
    return (match[1],subtype,scope)
