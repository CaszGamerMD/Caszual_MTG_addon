"""Whole-Oracle modal permanent destruction, with choices fixed on casting."""
import re


def parse(text, types):
    if types != ['Sorcery']:
        return ()
    lines=text.strip().splitlines()
    if not lines or lines[0] != 'Choose two —' or not 3 <= len(lines) <= 5:
        return ()
    result=[]
    for line in lines[1:]:
        if line=='• Destroy all artifacts.':
            mode=('artifact',0)
        elif line=='• Destroy all enchantments.':
            mode=('enchantment',0)
        else:
            m=re.fullmatch(r'• Destroy all creatures with mana value ([0-9]+) or (less|greater)\.',line)
            if not m:
                return ()
            mode=('creature_mana_le' if m[2]=='less' else 'creature_mana_ge',int(m[1]))
        if mode in result:
            return ()
        result.append(mode)
    return tuple(result)
