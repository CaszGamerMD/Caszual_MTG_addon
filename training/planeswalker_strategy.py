"""Public-board loyalty strategy with explainable tactical choices.

The rules engine still owns legality. This module only ranks legal abilities;
it never peeks at shuffled libraries or the opponent's hand, and no card names
are special-cased. Results are fixed for a given public battlefield.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Evaluation:
    value: float
    reason: str

def evaluate(sim, seat, walker, ability, target=''):
    game=sim.event_game('main')
    power=0.0
    notes=[]
    current=walker.loyalty
    future=current+ability.delta
    enemy=1-seat
    friendly=[item for item in sim.players[seat].battlefield
              if item.card.id in game.battlefield
              and game.creature(game.battlefield[item.card.id])]
    opposing=[item for item in sim.players[enemy].battlefield
              if item.card.id in game.battlefield
              and game.creature(game.battlefield[item.card.id])]
    largest_threat=max((max(0,game.stats(game.battlefield[x.card.id])[0])
                        for x in opposing),default=0)
    ultimate_costs=[-a.delta for a in walker.card.loyalty_program.abilities
                    if a.effect_kind=='emblem' and a.delta<0]
    ultimate=min(ultimate_costs) if ultimate_costs else None

    if ability.delta>0:
        power+=0.8*ability.delta
        notes.append('build loyalty')
        if ultimate and current<ultimate:
            distance=ultimate-future
            power+=2.0 if distance<=0 else 1.2 if distance==1 else 0.55
            notes.append('approach ultimate')
    elif ability.delta<0:
        power-=0.58*(-ability.delta)
        if future==0 and ability.effect_kind!='emblem':
            power-=4.0
            notes.append('would lose planeswalker')
        elif future<=1 and largest_threat>=3 and ability.effect_kind!='emblem':
            power-=1.0

    kind=ability.effect_kind
    if kind=='timed_modifier':
        if not target:
            power+=0.15
            notes.append('no creature selected')
        else:
            owned=next((owner for owner,player in enumerate(sim.players)
                        if any(x.card.id==target for x in player.battlefield)),None)
            state=game.battlefield.get(target)
            if state is None:
                power-=50
            else:
                attack,tough=game.stats(state)
                if owned==seat:
                    power-=9.0+max(0,attack)
                    notes.append('avoid weakening own creature')
                elif owned==enemy:
                    if tough+ability.program.toughness<=0:
                        power+=7.2+min(5,max(0,attack))*0.75
                        notes.append('remove opposing creature')
                    else:
                        power+=1.1+min(6,max(0,attack))*0.6
                        notes.append('reduce opposing pressure')
    elif kind=='mill_optional_creature_return':
        known=sum(1 for x in sim.players[seat].graveyard
                  if x.kind=='creature' or 'Creature' in x.printed_types)
        power+=3.3 if known else 1.2
        notes.append('recover creature' if known else 'mill for potential recovery')
    elif kind=='draw_conditional_discard':
        attacked=seat in sim.attacked_this_turn
        power+=3.5 if attacked else 1.35
        notes.append('keep card after attacking' if attacked else 'draw then discard')
    elif kind=='unblockable_tokens':
        spec=ability.program.token
        power+=3.2+min(spec.amount*spec.power,8)*1.6
        notes.append('add evasive creatures')
    elif kind=='emblem':
        from planeswalker_emblems import ScaledTokenEmblem,CombatCreatureSearchEmblem
        program=ability.program
        if isinstance(program,ScaledTokenEmblem):
            power+=8.0+min(4,len(friendly))*0.5
            notes.append('repeatable end-step board growth')
        elif isinstance(program,CombatCreatureSearchEmblem):
            power+=8.5+min(4,len(friendly))*1.35
            notes.append('repeatable combat creature search')
        else:
            power+=3.0
            notes.append('persistent emblem')
    elif kind=='atomic':
        # Verified one-operation spell effects, with real quantitative weight.
        block=ability.program.blocks[0]
        if block.operation=='draw_cards':
            power+=2.2*block.amount
            notes.append('card advantage')
        elif block.operation=='create_tokens':
            power+=3.0+0.6*block.amount
            notes.append('board development')
        elif block.operation=='gain_life':
            power+=min(4,block.amount*0.45)
            notes.append('stabilize life')
    if power<-20:power=-20
    if power>30:power=30
    return Evaluation(round(power,3),'; '.join(notes))
