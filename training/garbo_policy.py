"""Two experimental public-only Garbo policies, not trained champions."""
from dataclasses import dataclass
import json
import simulator as s

CAST={'cast','cast_commander','cast_exile','cast_flashback','cast_modal_back','bestow'}
CREATE={'activate_tokens','activate_tribal_tokens','activate_discard_tokens'}

@dataclass(frozen=True)
class GoblinPlan(s.Policy):
    version:int=3
    plan:str='swarm'

    def choose(self,obs:s.Observation)->s.Candidate:
        if self.plan not in ('swarm','counterpunch'):raise ValueError('Unknown plan')
        if not obs.legal_actions:raise ValueError('No legal actions')
        public=json.loads(obs.public_state)
        players=public.get('players',())
        own=players[obs.seat] if len(players)==2 else {}
        enemy=players[1-obs.seat] if len(players)==2 else {}
        friends=own.get('battlefield',())
        threats=enemy.get('battlefield',())
        bodies={item['id']:item for item in friends if item.get('isCreature')}
        blockers=[item for item in threats if item.get('isCreature') and not item.get('tapped')]
        cards={c.id:c for c in obs.own_hand}
        lands=sum(c.get('kind')=='land' for c in friends)
        enemy_life=enemy.get('life',40)

        def rank(action):
            data=dict(zip(s.FEATURES,action.features))
            value=sum(w*f for w,f in zip(self.weights,action.features))
            if action.kind=='pass' and obs.phase in ('main','second_main') and not obs.developed_this_turn:value-=2
            if action.kind in ('land','land_back') and lands<4:value+=5 if lands<2 else 2
            card=cards.get(action.card_id) if action.kind in CAST else None
            if card:
                definition=card.event_definition
                subtypes=definition.subtypes if definition else frozenset()
                types=definition.types if definition else frozenset(card.printed_types)
                goblin=('Goblin' in subtypes or 'Changeling' in subtypes)
                creature='Creature' in types or card.kind in ('creature','token_spell')
                token_payoff=bool(card.token_count or definition and
                    (definition.activations or definition.tribal_tap_tokens or
                     definition.token_action_triggers))
                if goblin:
                    value+=4 if self.plan=='swarm' else 3
                    value+=min(5,len(bodies)*.65)
                if creature and len(bodies)<4:value+=1.8
                if token_payoff:
                    value+=5 if self.plan=='swarm' else 3.5
                    if len(bodies)<2:value+=2
                if card.kind=='token_spell':value+=min(7,card.token_count*1.3)
                if lands<3 and creature and card.printed_mana_value is not None and card.printed_mana_value<=2:
                    value+=2.2
            if action.kind in CREATE:
                value+=4+(2 if self.plan=='swarm' else 1)+min(4,len(bodies)*.5)
            if action.kind=='cast_commander':value+=1 if self.plan=='swarm' else 2
            if action.kind=='attack_group':
                attackers=[bodies[i] for i in action.attack_ids if i in bodies]
                power=sum(max(0,c.get('power',0)) for c in attackers)
                nblock=len(blockers)
                # Raw combined power does not imply lethal through blockers.
                value-=s.DEFAULT_WEIGHTS['lethal']*data.get('lethal',0)
                projected=max(0,power-2*nblock)
                if projected>=enemy_life and projected>0:value+=120
                elif not nblock and power>=enemy_life:value+=120
                elif self.plan=='swarm':
                    value+=2.4*projected+max(0,len(attackers)-nblock)*1.1
                    if nblock>=len(attackers) and projected<2:value-=16
                else:
                    value+=1.6*projected
                    if nblock>=len(attackers) and projected<3:value-=24
                    if len(bodies)<nblock+2 and enemy_life>12:value-=8
            return value,action.id
        return max(obs.legal_actions,key=rank)
