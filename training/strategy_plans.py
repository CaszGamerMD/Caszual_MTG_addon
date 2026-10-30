"""Phase-aware strategy hypothesis: legal public decisions only; no private library peek."""
from dataclasses import dataclass
import json
import simulator as s

CASTS={'cast','cast_commander','cast_exile','cast_flashback','cast_modal_back','bestow'}
@dataclass(frozen=True)
class PhasePlanPolicy(s.Policy):
    version:int=2
    def choose(self,observation:s.Observation)->s.Candidate:
        if not observation.legal_actions:raise ValueError('No legal action')
        state=json.loads(observation.public_state)
        players=state.get('players',[])
        own=players[observation.seat] if len(players)==2 else {}
        enemy=players[1-observation.seat] if len(players)==2 else {}
        board=own.get('battlefield',[]);foes=enemy.get('battlefield',[])
        cards={c.id:c for c in observation.own_hand}
        lands=sum(x.get('kind')=='land' for x in board)
        creatures={x['id']:x for x in board if x.get('isCreature')}
        enchants=sum(x.get('kind') in ('aura','enchantment') for x in board)
        blockers=sum(x.get('isCreature') and not x.get('tapped') for x in foes)
        enemy_life=enemy.get('life',40)
        def utility(a):
            score=sum(w*f for w,f in zip(self.weights,a.features))
            if a.kind=='pass' and observation.phase in ('main','second_main') and not observation.developed_this_turn:
                score-=2
            if a.kind in ('land','land_back') and lands<4:
                score+=6.5 if lands<2 else 2
            if a.kind in CASTS:
                card=cards.get(a.card_id)
                if card:
                    d=card.event_definition
                    types=d.types if d else frozenset(card.printed_types)
                    if 'Creature' in types and lands<4:score+=2
                    if 'Enchantment' in types:
                        score+=1+min(2,enchants*.6)
                        if creatures:score+=1
                    if card.kind in ('token_spell','creature') and len(creatures)<3:score+=1
                    if lands>=4 and enemy_life<=20 and 'Creature' in types:score+=.8
                elif a.kind=='cast_commander':score+=1.5
            if a.kind in ('activate_tokens','activate_tribal_tokens','activate_discard_tokens') and len(creatures)<3:
                score+=1.3
            if a.kind=='attack_group':
                attacking=[creatures[i] for i in a.attack_ids if i in creatures]
                power=sum(max(0,c.get('power',0)) for c in attacking)
                expected=max(0,power-2*blockers)  # public risk proxy only
                score+=expected*1.4
                if power>=enemy_life and blockers==0:score+=30
                if blockers>len(attacking) and expected<2:
                    score-=min(8,2*(blockers-len(attacking)))
            return score,a.id
        return max(observation.legal_actions,key=utility)
