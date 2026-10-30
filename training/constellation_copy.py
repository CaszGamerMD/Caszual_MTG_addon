"""Whole-text constellation and once-per-turn enchanted-creature copying."""
import re


def compile(text,name,types,subtypes):
    if not {'Creature','Enchantment'}<=set(types):return None
    # Oracle often refers to a legendary permanent using only its short name.
    # Normalize this grammatical self-reference, never use name-based dispatch.
    short=name.split(',')[0].strip()
    normalized=text.replace(name,'this creature')
    if short!=name:
        normalized=re.sub(r'(?<=Whenever )'+re.escape(short)+r'(?= or )',
                          'this creature',normalized)
    lines=normalized.splitlines()
    if len(lines)!=2:return None
    enter=(
        'Constellation — Whenever this creature or another enchantment you control enters, '
        'put a +1/+1 counter on target creature.'
    )
    damage=(
        "Whenever this creature or an enchanted creature you control deals combat damage "
        "to a player, you may create a token that's a copy of a nonlegendary enchantment "
        "you control. Do this only once each turn."
    )
    return lines==[enter,damage]
