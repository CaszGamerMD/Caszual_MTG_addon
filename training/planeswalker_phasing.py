"""Beginning-of-end-step phase out and next-untap phase in for verified walkers.

Phasing does not change zones, create ETB events, reset loyalty, or erase
activation history. The generic battlefield adapter excludes phased permanents
from game-rule computations. These triggers remain on the ordinary priority
stack and can be countered.
"""

def queue_end_step(sim):
    controller=sim.active
    for item in tuple(sim.players[controller].battlefield):
        card=item.card
        program=card.loyalty_program
        if (item.phased_out or card.kind!='planeswalker' or program is None
                or not program.phase_on_entry_end_step):
            continue
        entered=any(entry['turn']==sim.turn and entry['id']==card.id
                    for entry in sim.entry_history)
        if not entered:continue
        sim._waiting_triggers.append((dict(operation='phase_on_entry_end_step',
            source=card.id,sourceEntry=item.entered_at,controller=controller,
            name=card.name,enteredTurn=sim.turn),card))

def resolve_end_step(sim,event,card):
    owner=event['controller']
    if owner not in (0,1):raise ValueError('Invalid phase-out controller')
    item=next((item for item in sim.players[owner].battlefield
               if item.card.id==event['source'] and not item.phased_out),None)
    if (item is None or item.entered_at!=event['sourceEntry']
            or not item.card.loyalty_program
            or not item.card.loyalty_program.phase_on_entry_end_step
            or not any(entry['turn']==event['enteredTurn']
                       and entry['id']==item.card.id for entry in sim.entry_history)):
        sim.log('phase_out_no_source','No matching entered-this-turn permanent survives.',
                actor=owner,source=card.id)
        return
    item.phased_out=True
    sim.log('planeswalker_phase_out','Permanent phases out without changing zones.',
            actor=owner,source=card.id,loyalty=item.loyalty)

def phase_in_on_untap(sim,owner):
    for item in sim.players[owner].battlefield:
        if not item.phased_out:continue
        item.phased_out=False
        sim.log('planeswalker_phase_in','Permanent phases in without entering the battlefield.',
                actor=owner,source=item.card.id,loyalty=item.loyalty)
