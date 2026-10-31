"""Turn-scoped planeswalker modifiers, separate from end-of-turn cleanup.

A -2/-1 effect until the controller's next turn survives the opponent's
cleanup. Keep actual permanent identity so a leaving/re-entering card cannot
inherit the expired modifier. This registry only contains validated effects.
"""

def apply(sim,item,controller,power,toughness):
    if not -20<=power<=20 or not -20<=toughness<=20:
        raise ValueError('Unvalidated loyalty modifier')
    item.temporary_power+=power
    item.temporary_toughness+=toughness
    sim.loyalty_long_modifiers.append((item,controller,sim.turn,power,toughness))


def after_cleanup(sim,game):
    """The game clears generic EOT modifiers; restore only ongoing effects."""
    active={id(item) for player in sim.players for item in player.battlefield}
    pending=[]
    for item,owner,turn,power,toughness in sim.loyalty_long_modifiers:
        if id(item) not in active:continue
        state=game.battlefield.get(item.card.id)
        if state is not None:
            state.temporary_power+=power
            state.temporary_toughness+=toughness
            pending.append((item,owner,turn,power,toughness))
    sim.loyalty_long_modifiers=pending


def beginning_of_turn(sim,active_seat):
    """'Until your next turn' ends as that controller's next turn begins."""
    pending=[]
    active={id(item) for player in sim.players for item in player.battlefield}
    for item,owner,turn,power,toughness in sim.loyalty_long_modifiers:
        if id(item) not in active:continue
        if owner==active_seat and sim.turn>turn:
            item.temporary_power-=power
            item.temporary_toughness-=toughness
            sim.log('loyalty_modifier_expire','Next-turn loyalty modifier expires.',
                    actor=active_seat,targetPermanent=item.card.id,
                    power=power,toughness=toughness)
        else:
            pending.append((item,owner,turn,power,toughness))
    sim.loyalty_long_modifiers=pending
