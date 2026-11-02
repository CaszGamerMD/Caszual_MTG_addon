"""Whole Oracle grammar for color-specific unspent-mana retention and scaling.

Costs, snapshots and card names do not select a behavior. The dynamic stat
modifier reads only the owner's current mana pool, even within a phase.
"""
import re

COLORS={'white':'W','blue':'U','black':'B','red':'R','green':'G'}


def parse(text,name,types):
    if 'Creature' not in types:return None
    lines=text.splitlines()
    if len(lines)!=2:return None
    keep=re.fullmatch(
        r"You don't lose unspent (white|blue|black|red|green) mana as steps and phases end\.",
        lines[0])
    if not keep:return None
    # Oracle can shorten a legendary name to its comma-prefix. Require a
    # complete recognized self-reference, never a substring of an ability.
    aliases={'This creature','this creature'}
    if name:
        aliases.add(name)
        if ',' in name:aliases.add(name.split(',',1)[0])
    for alias in aliases:
        count=re.fullmatch(re.escape(alias)+
            r' gets \+([1-9][0-9]*)/\+([1-9][0-9]*) for each unspent '
            r'(white|blue|black|red|green) mana you have\.',lines[1])
        if count:
            return COLORS[keep[1]],int(count[1]),int(count[2]),COLORS[count[3]]
    return None
