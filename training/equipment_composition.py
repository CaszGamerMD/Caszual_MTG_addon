"""Small, closed equipment clauses assembled from executable rule blocks.

Equipment triggers refer to the equipped creature at triggering time; they
remain independent of the equipment's own stat/keyword grants and equip cost.
"""
import re

from attachments import parse as parse_attachment


def equipped_attack_counters(text, types, subtypes):
    if 'Artifact' not in types or 'Equipment' not in subtypes:
        return None
    amount=None
    rest=[]
    for line in text.splitlines():
        attack=re.fullmatch(
            r'Whenever equipped creature attacks, put (a|one|two|three|four|[1-9][0-9]*) '
            r'\+1/\+1 counters? on it\.',line.strip())
        if attack:
            if amount is not None:return None
            amount={'a':1,'one':1,'two':2,'three':3,'four':4}.get(attack[1])
            if amount is None:amount=int(attack[1])
        else:
            rest.append(line)
    if amount is None:return None
    remainder='\n'.join(rest)
    attachment=parse_attachment(remainder,types,subtypes)
    if attachment is None:
        # No granted abilities is also a valid Equipment.  Do not relax the
        # complete-text attachment parser for an arbitrary leftover clause.
        cost=re.fullmatch(r'Equip ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',remainder)
        if cost is None:return None
        attachment=('equipment',cost[1],frozenset(),0,0)
    return attachment,amount


def token_equip_cost(text, types, subtypes):
    """A restricted equip activation composes with the normal equip and grants.

    The alternate cost is legal only when the selected recipient is a creature
    token; it is not a blanket reduction to the normal equip activation.
    """
    if 'Artifact' not in types or 'Equipment' not in subtypes:
        return None
    special=None
    rest=[]
    for line in text.splitlines():
        match=re.fullmatch(r'Equip creature token ((?:\{(?:[0-9]{1,2}|[WUBRGC])\})+)',line.strip())
        if match:
            if special is not None:return None
            special=match[1]
        else:
            rest.append(line)
    if special is None:return None
    attachment=parse_attachment('\n'.join(rest),types,subtypes)
    return (attachment,special) if attachment else None


def equipped_combat_life(text, types, subtypes):
    """Damage-to-player triggers compose with a complete equipment program.

    The life-loss instruction is queued when positive combat damage happens;
    the target player's *current* life total is read on trigger resolution.
    """
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    life=None
    remaining=[]
    for line in text.splitlines():
        match=re.fullmatch(
            r'Whenever equipped creature deals combat damage to a player, '
            r'that player loses (half their life, rounded up|[1-9][0-9]* life)\.',line.strip())
        if match:
            if life is not None:return None
            life=('half',0) if match[1]=='half their life, rounded up' else (
                'fixed',int(match[1].split()[0]))
        else:remaining.append(line)
    if life is None:return None
    attachment=parse_attachment('\n'.join(remaining),types,subtypes)
    return (attachment,life) if attachment else None
