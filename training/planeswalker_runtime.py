"""Controlled loyalty activations through the real priority stack."""
from dataclasses import replace

def legal(sim,seat):
    from simulator import Candidate,features
    if seat!=sim.active or seat!=sim.stack.priority or sim.stack.items:
        return ()
    if sim.phase not in ('main','second_main'):return ()
    result=[]
    for item in sim.players[seat].battlefield:
        card=item.card
        if item.phased_out or card.kind!='planeswalker' or card.loyalty_program is None:
            continue
        if item.loyalty is None or item.loyalty_activated_turn==sim.turn:
            continue
        for index,ability in enumerate(card.loyalty_program.abilities):
            if item.loyalty+ability.delta<0:continue
            options=('',)
            if ability.target_kind=='up_to_one_creature':
                options+=tuple(permanent.card.id for _,permanent
                               in sim.creature_targets(seat,card))
            from planeswalker_strategy import evaluate
            for target in options:
                evaluation=evaluate(sim,seat,item,ability,target)
                result.append(Candidate(card.id+':loyalty:'+str(index)+':target='+target,
                    'activate_loyalty',card.id,
                    features=features(power=evaluation.value),
                    label='Activate loyalty '+str(ability.delta)+' of '+card.name+
                          ' ('+evaluation.reason+')',
                    activation_index=index,target_permanent=target))
    return tuple(result)

def activate(sim,seat,source_id,index,target=''):
    if type(index) is not int:raise ValueError('Invalid loyalty ability index')
    selected=next((item for item in sim.players[seat].battlefield
                   if item.card.id==source_id),None)
    if selected is None or selected.card.loyalty_program is None or (
            selected.card.kind!='planeswalker'):
        raise ValueError('No controlled supported planeswalker')
    card=selected.card
    if not 0<=index<len(card.loyalty_program.abilities):
        raise ValueError('Unknown loyalty ability')
    if not any(x.card_id==source_id and x.activation_index==index
               and x.target_permanent==target for x in legal(sim,seat)):
        raise ValueError('Loyalty activation timing, cost or limit invalid')
    ability=card.loyalty_program.abilities[index]
    # The loyalty change is a COST, paid before the opponent gets priority.
    selected.loyalty+=ability.delta
    selected.loyalty_activated_turn=sim.turn
    sim.stack.active=sim.active
    frame=sim.stack.push(seat,(dict(operation='loyalty_ability',
        sourceType='Planeswalker',controller=seat,source=card.id,
        abilityIndex=index,program=ability.program,target=target),card),
        card.name+' loyalty '+str(ability.delta))
    sim.stack.priority=seat
    sim.log('loyalty_activation','Loyalty counters paid and ability added to stack.',
            actor=seat,source=card.id,cost=ability.delta,
            remainingLoyalty=selected.loyalty,stackId=frame.id)
    # A planeswalker that paid its final counter leaves before priority.
    sim.resolve_entry_triggers(sim.state_based_actions(),card,priority=seat)
    return frame

def resolve(sim,event,card):
    plan=event.get('program')
    index=event.get('abilityIndex')
    if (card.loyalty_program is None or type(index) is not int
            or index<0 or index>=len(card.loyalty_program.abilities)
            or card.loyalty_program.abilities[index].program is not plan):
        raise RuntimeError('Unverified loyalty stack program')
    ability=card.loyalty_program.abilities[index]
    if ability.effect_kind=='atomic':
        sim._resolve_entry_effects([plan.stack_event(
            controller=event['controller'],source=card.id,name=card.name)],card)
    elif ability.effect_kind=='timed_modifier':
        from planeswalker_duration import apply
        target=event.get('target','')
        if target:
            legal={permanent.card.id:permanent for _,permanent
                   in sim.creature_targets(event['controller'],card)}
            if target not in legal:
                sim.log('loyalty_target_fizzle','The loyalty target became illegal.',
                        source=card.id,target=target)
                return
            apply(sim,legal[target],event['controller'],plan.power,plan.toughness)
            sim.log('loyalty_timed_modifier','Targeted loyalty effect lasts until your next turn.',
                    actor=event['controller'],source=card.id,target=target,
                    power=plan.power,toughness=plan.toughness)
        else:
            sim.log('loyalty_no_target','Optional creature target was not selected.',
                    actor=event['controller'],source=card.id)
        sim.resolve_entry_triggers(sim.state_based_actions(),card)
    elif ability.effect_kind=='mill_optional_creature_return':
        sim._resolve_entry_effects([dict(operation='mill_cards',controller=event['controller'],
            source=card.id,name=card.name,amount=plan.amount,
            recipient='controller')],card)
        player=sim.players[event['controller']]
        choices=tuple(x for x in player.graveyard if x.kind=='creature'
                      or 'Creature' in x.printed_types)
        # The current diagnostic policy elects to return the lowest stable id.
        # The choice is after milling, and may include a previously milled card.
        if choices:
            chosen=min(choices,key=lambda x:x.id)
            player.graveyard.remove(chosen);player.hand.append(chosen)
            sim.log('loyalty_graveyard_return','An optional creature card is returned.',
                    actor=event['controller'],source=card.id,card=chosen.name)
        else:
            sim.log('loyalty_no_return','No creature card is available to return.',
                    actor=event['controller'],source=card.id)
    elif ability.effect_kind=='emblem':
        from planeswalker_emblems import create
        create(sim,event['controller'],plan,card)
    elif ability.effect_kind in ('draw_conditional_discard','unblockable_tokens'):
        from planeswalker_conditional import resolve as resolve_conditional
        resolve_conditional(sim,event,card,ability)
    else:
        raise RuntimeError('Unhandled compiled loyalty ability kind')
    sim.log('loyalty_resolve','Planeswalker loyalty ability resolves.',
            actor=event['controller'],source=card.id,
            index=event['abilityIndex'])
