"""Typed, persistent planeswalker emblem trigger programs.

Emblems are owned by players, not battlefield permanents. They never cease
to exist because the source planeswalker leaves. Triggers use the regular
priority stack and count matching creatures at resolution, not at trigger time.
No card names occur in the grammar.
"""
from dataclasses import dataclass, asdict
import re
from oracle_abilities import TokenSpec
from creature_types import has_subtype

_COLOR={'white':'White','blue':'Blue','black':'Black','red':'Red','green':'Green'}
_WORDS={'one':1,'two':2,'three':3,'four':4}
_PATTERN=re.compile(
    r'You get an emblem with "At the beginning of your end step, '
    r'create X ([1-9][0-9]*)/([1-9][0-9]*) (white|blue|black|red|green) '
    r'([A-Z][a-z]+(?: [A-Z][a-z]+)*) creature tokens, where X is '
    r'(one|two|three|four|[1-9][0-9]*) plus the number of '
    r'([A-Z][a-z]+(?: [A-Z][a-z]+)*) you control\."'
)

@dataclass(frozen=True)
class ScaledTokenEmblem:
    base: int
    counted_subtype: str
    token: TokenSpec

@dataclass(frozen=True)
class CombatCreatureSearchEmblem:
    colors: tuple[str, ...]
    damage_source_scope: str = 'controller_creature'
    destination: str = 'battlefield'

@dataclass(frozen=True)
class ActiveEmblem:
    id: str
    owner: int
    program: ScaledTokenEmblem | CombatCreatureSearchEmblem
    origin: object

def compile_emblem(oracle):
    combat=re.fullmatch(
        r'You get an emblem with "Whenever a creature you control deals combat damage '
        r'to a player, search your library for a ([a-z]+) or ([a-z]+) creature card, '
        r'put it onto the battlefield, then shuffle\."',oracle)
    if combat:
        if combat[1] not in _COLOR or combat[2] not in _COLOR or combat[1]==combat[2]:
            return None
        return CombatCreatureSearchEmblem((_COLOR[combat[1]],_COLOR[combat[2]]))
    match=_PATTERN.fullmatch(oracle)
    if match is None:return None
    power,toughness=int(match[1]),int(match[2])
    amount=_WORDS.get(match[5])
    if amount is None:amount=int(match[5])
    if not 1<=power<=99 or not 1<=toughness<=99 or not 1<=amount<=1000:
        return None
    return ScaledTokenEmblem(
        amount,match[6],TokenSpec(1,power,toughness,
        (_COLOR[match[3]],),tuple(match[4].split()),frozenset()))

def create(sim,controller,program,origin):
    if not isinstance(program,(ScaledTokenEmblem,CombatCreatureSearchEmblem)) or controller not in (0,1):
        raise ValueError('Unsupported emblem creation')
    sim.emblem_sequence+=1
    item=ActiveEmblem('emblem-'+str(sim.emblem_sequence),controller,program,origin)
    sim.emblems[controller].append(item)
    sim.log('emblem_created','Planeswalker loyalty ability creates an emblem.',
            actor=controller,emblemId=item.id,source=origin.id,
            emblemType='end_step_tokens' if isinstance(program,ScaledTokenEmblem) else 'combat_library_search')
    return item

def queue_end_step(sim):
    """Snapshot emblem triggers once at the *beginning* of the end step."""
    for emblem in tuple(sim.emblems[sim.active]):
        if not isinstance(emblem.program,ScaledTokenEmblem):continue
        sim._waiting_triggers.append((dict(operation='emblem_end_step',
            controller=emblem.owner,emblemId=emblem.id,
            source=emblem.origin.id,name=emblem.origin.name),emblem.origin))

def _subtype_forms(oracle_plural):
    """Possible singular creature subtypes from a quantified Oracle noun."""
    forms=[oracle_plural]
    if oracle_plural.endswith('s'):forms.append(oracle_plural[:-1])
    if oracle_plural.endswith('ves'):forms.append(oracle_plural[:-3]+'f')
    if oracle_plural.endswith('ies'):forms.append(oracle_plural[:-3]+'y')
    return tuple(dict.fromkeys(forms))

def resolve_end_step(sim,event,card):
    controller=event['controller']
    emblem=next((x for x in sim.emblems[controller]
                 if x.id==event.get('emblemId')),None)
    if emblem is None:raise RuntimeError('Unknown emblem on stack')
    program=emblem.program
    if not isinstance(program,ScaledTokenEmblem):
        raise RuntimeError('Wrong emblem type for end-step resolution')
    game=sim.event_game('main')
    forms=_subtype_forms(program.counted_subtype)
    count=sum(1 for state in game.battlefield.values()
              if state.controller==controller and game.creature(state)
              and any(has_subtype(state.definition,singular) for singular in forms))
    amount=program.base+count
    if amount>1000:raise RuntimeError('Emblem token quantity exceeds supported safety limit')
    spec=dict(asdict(program.token),amount=amount,keywords=[])
    sim.log('emblem_trigger_count','Emblem determines number of tokens at resolution.',
            actor=controller,emblemId=emblem.id,base=program.base,
            counted=count,amount=amount)
    sim._resolve_entry_effects([dict(operation='create_tokens',
        controller=controller,source=emblem.origin.id,
        name=emblem.origin.name,tokenSpec=spec)],card)

def combat_hit_events(sim,source_ids,controller):
    """Return an event per successful creature-to-player combat damage hit.

    The caller has already applied prevention and assigned positive damage.
    Triggering does not require the creature to survive subsequent state checks.
    """
    events=[]
    for identifier in source_ids:
        for emblem in tuple(sim.emblems[controller]):
            if not isinstance(emblem.program,CombatCreatureSearchEmblem):continue
            events.append((dict(operation='emblem_combat_search',
                controller=controller,source=emblem.origin.id,
                name=emblem.origin.name,emblemId=emblem.id,
                damageSource=identifier),emblem.origin))
    return events

def resolve_combat_search(sim,event,card):
    """A fully verified search emblem uses the existing ETB and shuffle path."""
    import random
    owner=event['controller']
    emblem=next((e for e in sim.emblems[owner] if e.id==event.get('emblemId')),None)
    if emblem is None or not isinstance(emblem.program,CombatCreatureSearchEmblem):
        raise RuntimeError('Invalid creature search emblem on stack')
    player=sim.players[owner]
    colors=set(emblem.program.colors)
    # Unsupported creature definitions are not promoted to playable game
    # objects. The diagnostic chooser picks a deterministic supported match.
    choices=[c for c in player.library if c.kind=='creature'
             and colors.intersection(c.colors)]
    chosen=min(choices,key=lambda c:c.id) if choices else None
    if chosen:
        player.library.remove(chosen)
        pending=sim.enter_creatures((chosen,),player)
        sim.resolve_entry_triggers(pending,chosen)
    sim.library_random_sequence+=1
    random.Random(str(sim.seed)+':library:'+str(sim.library_random_sequence)).shuffle(player.library)
    sim.log('emblem_creature_search','Emblem searches and shuffles the library.',
            actor=owner,source=emblem.origin.id,emblemId=emblem.id,
            found=bool(chosen),creature=chosen.name if chosen else None)
