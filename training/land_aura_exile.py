"""Strict whole-Oracle language for land Auras with linked temporary exile."""
import re
from attachments import parse as parse_attachment

def parse(text,types,subtypes):
    if 'Enchantment' not in types or 'Aura' not in subtypes:return None
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)!=2:return None
    # Consume the entire trigger; any additional clause remains unsupported.
    if lines[1]!='When this Aura enters, exile target creature an opponent controls until this Aura leaves the battlefield.':
        return None
    # Reuse the same land-subtype, snow and controller restrictions as other
    # land Auras. A synthetic keyword is only a grammar probe, never granted.
    probe=parse_attachment(lines[0]+'\nEnchanted land has hexproof.',types,subtypes)
    if not probe or len(probe)!=6 or not probe[5].startswith('land:'):return None
    return ('aura',None,frozenset(),0,0,probe[5])
