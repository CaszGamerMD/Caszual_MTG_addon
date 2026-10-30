"""Commander-damage race policy for the standalone two-player MTG diagnostic.

Only reads Observation.own_hand, Observation.public_state and legal actions.
No private-zone access, engine reference, opponent-hand or library inspection.
The Goblin engine stays a backup when the commander clock is contested.
"""
from dataclasses import dataclass
import json
import simulator as s

CAST={'cast','cast_commander','cast_exile','cast_flashback','bestow'}
CREATORS={'activate_tokens','activate_tribal_tokens','activate_discard_tokens'}

@dataclass(frozen=True)
class CommanderClockPolicy(s.Policy):
    version: int = 4

    def choose(self, obs: s.Observation) -> s.Candidate:
        if not obs.legal_actions: raise ValueError('No legal actions')
        state=json.loads(obs.public_state)
        players=state.get('players',[])
        own=players[obs.seat] if len(players)==2 else {}
        enemy=players[1-obs.seat] if len(players)==2 else {}
        friends=own.get('battlefield',[])
        enemies=enemy.get('battlefield',[])
        allies={p['id']:p for p in friends if p.get('isCreature')}
        opponents={p['id']:p for p in enemies if p.get('isCreature')}
        blockers=[p for p in opponents.values() if not p.get('tapped')]
        hand={c.id:c for c in obs.own_hand}
        lands=sum(p.get('kind')=='land' for p in friends)
        commander_id=str(obs.seat)+'-commander'
        commander=allies.get(commander_id)
        damage=(enemy.get('commanderDamage') or {}).get(commander_id,0)
        remaining=max(0,21-damage)
        enemy_life=enemy.get('life',40)

        def utility(a):
            factors=dict(zip(s.FEATURES,a.features))
            value=sum(w*f for w,f in zip(self.weights,a.features))
            if a.kind=='pass' and obs.phase in ('main','second_main') and not obs.developed_this_turn:
                value-=2
            if a.kind in ('land','land_back') and lands<5:
                value+=6 if lands<3 else 3
            if a.kind=='cast_commander':
                # Casting is only offered when legal and payable. Rushing Zurgo
                # is the primary game plan, but do not override all other costs.
                value+=19 if remaining>=7 else 5
            if a.kind in CAST:
                card=hand.get(a.card_id)
                if card:
                    definition=card.event_definition
                    subtype=definition.subtypes if definition else frozenset()
                    creature=('Creature' in definition.types if definition else
                              card.kind=='creature')
                    goblin=('Goblin' in subtype or 'Changeling' in subtype)
                    token_plan=bool(card.token_count or definition and
                        (definition.activations or definition.tribal_tap_tokens or
                         definition.token_action_triggers))
                    if creature and len(allies)<3:value+=1.5
                    if goblin:value+=2.5+min(3,len(allies)*.4)
                    if token_plan:value+=3.5
                    if card.kind=='token_spell':value+=min(5,card.token_count)
                    if card.printed_mana_value is not None and card.printed_mana_value<=2 and lands<3:
                        value+=1.5
                if a.target_permanent==commander_id:
                    # A legal boost/equipment attachment to Zurgo contributes
                    # to the 21-damage objective, but may still be nonlethal.
                    value+=6 if commander is not None else 0
                if a.target_permanent in opponents and commander is not None:
                    # Removing an untapped blocker opens the commander route.
                    value+=5 if not opponents[a.target_permanent].get('tapped') else 1
            if a.kind in CREATORS:
                value+=3+min(3,len(allies)*.4)
            if a.kind=='attack_group':
                attacking=[allies[i] for i in a.attack_ids if i in allies]
                total_power=sum(max(0,p.get('power',0)) for p in attacking)
                nblock=len(blockers)
                # The engine's raw-power lethal feature assumes no blockers,
                # so remove that heuristic for this defensive estimate.
                value-=s.DEFAULT_WEIGHTS['lethal']*factors.get('lethal',0)
                estimated=max(0,total_power-2*nblock)
                value+=1.5*estimated
                if estimated>=enemy_life and estimated>0:value+=100
                if commander_id in a.attack_ids and commander is not None:
                    cp=max(0,commander.get('power',0))
                    # A full legal block assignment is chosen by the defender:
                    # this is a cautious public-board proxy, NOT a guaranteed hit.
                    spare_attackers=max(0,len(attacking)-1)
                    defender_capacity=max(0,nblock-spare_attackers)
                    can_connect=defender_capacity==0
                    if can_connect:
                        value+=15+min(cp,remaining)*4
                        if cp>=remaining:value+=120
                    else:
                        value+=5
                        if len(attacking)==1 and cp<remaining:value-=8
                elif commander is not None and nblock>=len(attacking):
                    value-=10
            # Survive/blocks priority remains with the underlying Policy if
            # no special commander action is present.
            return value,a.id
        return max(obs.legal_actions,key=utility)
