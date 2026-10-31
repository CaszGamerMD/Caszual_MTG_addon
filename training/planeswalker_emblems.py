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
class ActiveEmblem:
    id: str
    owner: int
    program: ScaledTokenEmblem
    origin: object

def compile_emblem(oracle):
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
    if not isinstance(program,ScaledTokenEmblem) or controller not in (0,1):
        raise ValueError('Unsupported emblem creation')
    sim.emblem_sequence+=1
    item=ActiveEmblem('emblem-'+str(sim.emblem_sequence),controller,program,origin)
    sim.emblems[controller].append(item)
    sim.log('emblem_created','Planeswalker loyalty ability creates an emblem.',
            actor=controller,emblemId=item.id,source=origin.id,
            subtype=program.counted_subtype)
    return item

def queue_end_step(sim):
    """Snapshot emblem triggers once at the *beginning* of the end step."""
    for emblem in tuple(sim.emblems[sim.active]):
        sim._waiting_triggers.append((dict(operation='emblem_end_step',
            controller=emblem.owner,emblemId=emblem.id,
            source=emblem.origin.id,name=emblem.origin.name),emblem.origin))

def resolve_end_step(sim,event,card):
    controller=event['controller']
    emblem=next((x for x in sim.emblems[controller]
                 if x.id==event.get('emblemId')),None)
    if emblem is None:raise RuntimeError('Unknown emblem on stack')
    program=emblem.program
    game=sim.event_game('main')
    count=sum(1 for state in game.battlefield.values()
              if state.controller==controller and game.creature(state)
              and has_subtype(state.definition,program.counted_subtype))
    amount=program.base+count
    if amount>1000:raise RuntimeError('Emblem token quantity exceeds supported safety limit')
    spec=dict(asdict(program.token),amount=amount,keywords=[])
    sim.log('emblem_trigger_count','Emblem determines number of tokens at resolution.',
            actor=controller,emblemId=emblem.id,base=program.base,
            counted=count,amount=amount)
    sim._resolve_entry_effects([dict(operation='create_tokens',
        controller=controller,source=emblem.origin.id,
        name=emblem.origin.name,tokenSpec=spec)],card)
