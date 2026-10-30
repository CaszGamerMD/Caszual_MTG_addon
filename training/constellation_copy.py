"""Whole-text constellation and once-per-turn enchanted-creature copying."""
import re


def compile(text,name,types,subtypes):
    if not {'Creature','Enchantment'}<=set(types):return None
    lines=text.replace(name,'this creature').splitlines()
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
