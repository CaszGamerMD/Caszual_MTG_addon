"""Complete, name-independent planeswalker conditional and token ability blocks.

Fail closed on any text outside these exact supported patterns; abilities
are only executed by the loyalty activation stack, not on card import.
"""
from dataclasses import dataclass
from oracle_abilities import TokenSpec
import re

@dataclass(frozen=True)
class DrawThenConditionalDiscard:
    draws: int
    discard_unless_attacked: bool = True

@dataclass(frozen=True)
class UnblockableTokenProgram:
    token: TokenSpec

_DRAW=re.compile(r'Draw (a|one|two|three|[1-9][0-9]*) cards?\. Then discard a card unless you attacked this turn\.')
_TOKEN=re.compile(r'Create (a|one|two|three|[1-9][0-9]*) ([1-9][0-9]*)/([1-9][0-9]*) (white|blue|black|red|green) ([A-Z][a-z]+(?: [A-Z][a-z]+)*) creature tokens? with "This token can(?:\x27|\u2019)t be blocked\."')
_NUM={'a':1,'one':1,'two':2,'three':3}
_COLORS={'white':'White','blue':'Blue','black':'Black','red':'Red','green':'Green'}

def _number(text):
    return _NUM.get(text,int(text) if text.isdigit() else 0)

def compile_ability(text):
    if not isinstance(text,str):return None
    match=_DRAW.fullmatch(text)
    if match:
        count=_number(match[1])
        return DrawThenConditionalDiscard(count) if 1<=count<=1000 else None
    match=_TOKEN.fullmatch(text)
    if match:
        number,power,toughness=(_number(match[1]),int(match[2]),int(match[3]))
        if not 1<=number<=1000 or not 1<=power<=99 or not 1<=toughness<=99:
            return None
        spec=TokenSpec(number,power,toughness,(_COLORS[match[4]],),
                       tuple(match[5].split()),frozenset({'unblockable'}))
        return UnblockableTokenProgram(spec)
    return None

def resolve(sim,event,card,ability):
    from dataclasses import asdict
    controller=event['controller']
    program=ability.program
    if ability.effect_kind=='draw_conditional_discard':
        for _ in range(program.draws):
            sim.draw(controller)
        if controller not in sim.attacked_this_turn and sim.players[controller].hand:
            # Declared sandbox policy: choose minimum stable id after drawing,
            # not at loyalty activation. Human choices can replace this later.
            player=sim.players[controller]
            chosen=min(player.hand,key=lambda c:c.id)
            player.hand.remove(chosen)
            player.graveyard.append(chosen)
            sim.log('loyalty_discard','Conditional loyalty draw requires discard.',
                    actor=controller,source=card.id,card=chosen.name)
        else:
            sim.log('loyalty_discard_skipped','Attacked this turn or no card to discard.',
                    actor=controller,source=card.id,
                    attacked=controller in sim.attacked_this_turn)
    elif ability.effect_kind=='unblockable_tokens':
        spec=dict(asdict(program.token),keywords=sorted(program.token.keywords))
        sim._resolve_entry_effects([dict(operation='create_tokens',controller=controller,
             source=card.id,name=card.name,tokenSpec=spec)],card)
    else:raise RuntimeError('Unverified conditional loyalty effect')
