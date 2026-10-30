"""Whole-text Saga chapters and transformed enchantment-creature stat scaling."""
import re


def compile_saga(text,types,subtypes):
    if 'Enchantment' not in types or 'Saga' not in subtypes:return None
    # The balanced parenthetical reminder text is removed upstream; the
    # resulting two chapter lines must be consumed in their entirety.
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    if len(lines)!=2:return None
    bonus=re.fullmatch(
        r'I, II — Target creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) '
        r'until end of turn for each artifact and/or enchantment you control\.',
        lines[0])
    transform=lines[1]=='III — Exile this Saga, then return it to the battlefield transformed under your control.'
    return (int(bonus[1]),int(bonus[2])) if bonus and transform else None


def compile_transformed_creature(text,types):
    if not {'Creature','Enchantment'}<=set(types):return None
    m=re.fullmatch(
        r'This creature gets \+([1-9][0-9]*)/\+([1-9][0-9]*) '
        r'for each artifact and/or enchantment you control\.',text)
    return (int(m[1]),int(m[2])) if m else None
