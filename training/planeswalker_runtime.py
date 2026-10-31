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
        if card.kind!='planeswalker' or card.loyalty_program is None:
            continue
        if item.loyalty is None or item.loyalty_activated_turn==sim.turn:
            continue
        for index,ability in enumerate(card.loyalty_program.abilities):
            if item.loyalty+ability.delta<0:continue
            power=sum(block.amount for block in ability.program.blocks)
            result.append(Candidate(card.id+':loyalty:'+str(index),
                'activate_loyalty',card.id,features=features(power=power),
                label='Activate loyalty '+str(ability.delta)+' of '+card.name,
                activation_index=index))
    return tuple(result)

def activate(sim,seat,source_id,index):
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
               for x in legal(sim,seat)):
        raise ValueError('Loyalty activation timing, cost or limit invalid')
    ability=card.loyalty_program.abilities[index]
    # The loyalty change is a COST, paid before the opponent gets priority.
    selected.loyalty+=ability.delta
    selected.loyalty_activated_turn=sim.turn
    sim.stack.active=sim.active
    frame=sim.stack.push(seat,(dict(operation='loyalty_ability',
        sourceType='Planeswalker',controller=seat,source=card.id,
        abilityIndex=index,program=ability.program),card),
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
    if card.loyalty_program is None or not any(
            step.program is plan for step in card.loyalty_program.abilities):
        raise RuntimeError('Unverified loyalty stack program')
    sim._resolve_entry_effects([plan.stack_event(
        controller=event['controller'],source=card.id,name=card.name)],card)
    sim.log('loyalty_resolve','Planeswalker loyalty ability resolves.',
            actor=event['controller'],source=card.id,
            index=event['abilityIndex'])
