"""Reusable choose-two modal target bindings and stack resolution.

Only invoked for trusted, wholly parsed modal programs. One target is bound
for each selected mode before cost payment. Each choice resolves in Oracle
order, skipping illegal targets without skipping still-legal modes.
"""
from dataclasses import asdict
from itertools import combinations, product


def identifier(mode, owner, obj):
    if mode.target_kind=='player':return f'player:{owner}'
    if mode.target_kind=='loyalty_ability':return f'ability:{obj.id}'
    if mode.target_kind=='graveyard':return obj.id
    return obj.card.id


def options(sim,seat,card,index):
    mode=card.modal_target_program.modes[index]
    if mode.target_kind=='player':
        return tuple((owner,owner) for owner in range(len(sim.players)))
    if mode.target_kind=='loyalty_ability':
        return tuple((frame.controller,frame) for frame in sim.stack.items
                     if frame.payload[0].get('operation')=='loyalty_ability'
                     and frame.payload[0].get('sourceType')=='Planeswalker')
    return sim.modal_target_options(seat,card,index)


def bind(sim,seat,card,modes,targets):
    selected=card.modal_target_program.bind(modes)
    if not isinstance(targets,(tuple,list)) or len(targets)!=len(selected):
        raise ValueError('Provide one separate target for every mode')
    if any(not isinstance(target,str) for target in targets):
        raise ValueError('Modal targets must be identifiers')
    for index,mode,target in zip(modes,selected,targets):
        legal={identifier(mode,owner,obj) for owner,obj in options(sim,seat,card,index)}
        if target not in legal:
            raise ValueError('Mode target is not legal at cast time')
    return tuple(targets)


def choices(sim,seat,card,kind):
    from simulator import Candidate,features
    program=card.modal_target_program
    result=[]
    for indices in combinations(range(len(program.modes)),program.choose):
        available=[options(sim,seat,card,index) for index in indices]
        if not all(available):continue
        for selection in product(*available):
            targets=tuple(identifier(program.modes[index],owner,obj)
                          for index,(owner,obj) in zip(indices,selection))
            power=sum(2 if owner!=seat and program.modes[index].operation in
                      ('destroy','exile','damage','counter_ability') else 1
                      for index,(owner,_) in zip(indices,selection))
            result.append(Candidate(card.id+':modes='+','.join(map(str,indices))+
                ':targets='+','.join(targets),kind,card.id,
                features=features(power=power),
                label='Cast '+card.name+' with modes '+','.join(str(i+1) for i in indices),
                target_permanent=targets,modal_modes=indices))
    return tuple(result)


def resolve(sim,event,card):
    controller=event['controller']
    indices=event.get('modalModes',())
    modes=card.modal_target_program.bind(indices)
    targets=event.get('target')
    if not isinstance(targets,(tuple,list)) or len(targets)!=len(modes):
        raise RuntimeError('Corrupt modal target tuple on stack')
    steps=sorted(zip(indices,modes,targets),key=lambda x:x[0])
    def lookup(index,mode,target):
        return next(((owner,obj) for owner,obj in options(sim,controller,card,index)
                     if identifier(mode,owner,obj)==target),None)
    if all(lookup(index,mode,target) is None for index,mode,target in steps):
        sim.log('modal_target_fizzle','All chosen targets became illegal.',
                source=card.name,actor=controller,targets=tuple(targets))
        return
    for index,mode,target in steps:
        selected=lookup(index,mode,target)
        if selected is None:
            sim.log('modal_target_skipped','Selected mode target became illegal.',
                    source=card.name,actor=controller,mode=index,target=target)
            continue
        owner,obj=selected
        if mode.target_kind=='player':
            if mode.operation=='gain_life':
                sim.gain_life(owner,mode.amount)
                sim.log('modal_life','A selected player gains life.',actor=owner,
                        source=card.name,amount=mode.amount)
            elif mode.operation=='create_tokens' and mode.token:
                sim._resolve_entry_effects([dict(operation='create_tokens',
                    controller=owner,source=card.id,name=card.name,
                    tokenSpec=dict(asdict(mode.token),keywords=sorted(mode.token.keywords)))],card)
            else:raise RuntimeError('Uncompiled modal player step')
        elif mode.target_kind=='loyalty_ability':
            removed=sim.counter_stack_item(obj)
            sim.log('modal_counter_ability','A loyalty ability is countered.',
                    source=card.name,actor=controller,targetStack=obj.id,
                    countered=bool(removed))
        elif mode.target_kind=='graveyard':
            sim.players[owner].graveyard.remove(obj)
            sim.players[owner].exile.append(obj)
            sim.log('modal_exile','A graveyard card is exiled.',source=card.name,
                    actor=controller,target=target)
        else:
            # This branch shares the existing verified destroy/exile/damage
            # primitives rather than reimplementing targeting or ward.
            game=sim.event_game('main')
            state=game.battlefield.get(obj.card.id)
            if mode.operation=='destroy':
                if state and game.has(state,'indestructible'):
                    sim.log('indestructible','Selected permanent cannot be destroyed.',
                            source=card.name,targetPermanent=obj.card.id)
                else:sim.destroy_batch(((owner,obj),),card,reason='modal_destroy')
            elif mode.operation=='exile':
                sim.send_to_destination(sim.players[owner],obj,snapshot=game,to_exile=True)
                sim.log('modal_exile','A permanent is exiled.',
                        source=card.name,targetPermanent=obj.card.id)
            elif mode.operation=='damage':
                obj.marked_damage+=mode.amount
                sim.log('modal_damage','Modal creature damage resolves.',
                        source=card.name,amount=mode.amount,targetPermanent=obj.card.id)
            else:raise RuntimeError('Unknown compiled modal operation')
        if sim.finished:return
        sim.resolve_entry_triggers(sim.state_based_actions(),card)
        if sim.finished:return
