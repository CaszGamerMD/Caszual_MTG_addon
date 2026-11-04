"""Small, closed equipment clauses assembled from executable rule blocks.

Equipment triggers refer to the equipped creature at triggering time; they
remain independent of the equipment's own stat/keyword grants and equip cost.
"""
import re

from attachments import parse as parse_attachment
from oracle_abilities import parse_token_creation


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


_HIT_CONJUNCTION=re.compile(r', then (?=proliferate$)| and (?=that player (?:mills |discards )|you (?:untap all lands |may return up to one target creature card |draw ))')


def _hit_atom(clause):
    token=re.fullmatch(r'you (create .+)',clause)
    if token:
        spec=parse_token_creation(token[1][0].upper()+token[1][1:]+'.')
        return ('create_tokens',spec.amount,spec) if spec else None
    mill=re.fullmatch(r'that player mills (a|one|two|three|four|five|six|seven|eight|nine|ten|[1-9][0-9]*) cards?',clause)
    if mill:
        words={'a':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,
               'seven':7,'eight':8,'nine':9,'ten':10}
        return ('mill_damaged_player',words[mill[1]] if mill[1] in words else int(mill[1]),None)
    discard=re.fullmatch(r'that player discards (a|one|two|three|four|[1-9][0-9]*) cards?',clause)
    if discard:
        words={'a':1,'one':1,'two':2,'three':3,'four':4}
        return ('discard_damaged_player',words[discard[1]] if discard[1] in words else int(discard[1]),None)
    if clause=='you untap all lands you control':
        return ('untap_controlled_lands',0,None)
    life=re.fullmatch(r'you gain ([1-9][0-9]*) life',clause)
    if life:return ('gain_controller_life',int(life[1]),None)
    if clause=='you may return up to one target creature card from your graveyard to your hand':
        return ('return_optional_graveyard_creature',1,None)
    hit=re.fullmatch(r'this Equipment deals ([1-9][0-9]*) damage to any target',clause)
    if hit:return ('damage_equipment_target',int(hit[1]),None)
    draw=re.fullmatch(r'you draw (a|one|two|three|four|[1-9][0-9]*) cards?',clause)
    if draw:
        words={'a':1,'one':1,'two':2,'three':3,'four':4}
        return ('draw_cards',words[draw[1]] if draw[1] in words else int(draw[1]),None)
    counter=re.fullmatch(
        r'put (a|one|two|three|four|[1-9][0-9]*) \\+1/\\+1 counters? on a creature you control',clause)
    if counter:
        words={'a':1,'one':1,'two':2,'three':3,'four':4}
        amount=words[counter[1]] if counter[1] in words else int(counter[1])
        return ('counter_controlled_creature',amount,None)
    if clause=='proliferate':
        return ('proliferate',0,None)
    return None


def equipped_combat_steps(text,types,subtypes):
    """One combat-hit ability is a sequence of *fully* parsed atomic actions.

    Separators are only recognized at the start of an independent instruction,
    never in token colors, creature subtypes, or protection grants.
    """
    if 'Artifact' not in types or 'Equipment' not in subtypes:return None
    steps=None;remaining=[]
    for line in text.splitlines():
        hit=re.fullmatch(r'Whenever equipped creature deals combat damage to a player, (.+)\.',line.strip())
        if hit:
            if steps is not None:return None
            chunks=_HIT_CONJUNCTION.split(hit[1])
            if len(chunks)>8:return None
            actions=tuple(_hit_atom(chunk) for chunk in chunks)
            if not all(actions):return None
            steps=actions
        else:remaining.append(line)
    if not steps:return None
    attachment=parse_attachment('\n'.join(remaining),types,subtypes)
    return (attachment,steps) if attachment else None
