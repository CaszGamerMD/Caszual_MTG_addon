"""Conservative Garbo tactical overlay on the proven default decision policy.

Wilds is NEVER passed this policy: each gauntlet builds (Policy(), Policy())
and installs AdaptiveGarboPolicy only into Garbo's seat.

The adaptation deliberately does not reweight general spell sequencing after
the aggressive commander-clock variant lost baseline win 5258001. Instead it
adds two narrowly observable tactical responses: prioritize immediately
unblocked lethal commander attacks, and block lethal commander damage from
the enemy when the *legally offered* block candidates make that possible.

No deck/hand/library inspection beyond own-hand plus public observation.
"""
from dataclasses import dataclass
import json
import simulator as s


def abilities(permanent):
    """Effective combat keywords are published after the two P/T separators."""
    return frozenset(str(permanent.get('traits','')).split(';')[-1].split(','))


def defender_can_block(attacker, defenders):
    """Conservative estimate: only declare an unblockable route when certain.

    This estimates public flying/menace. Other restrictions or hidden spells
    can also matter, but we never presume an otherwise ordinary blocker cannot
    block because of undocumented color/subtype rules.
    """
    keywords=abilities(attacker)
    blockers=[x for x in defenders if x.get('isCreature') and not x.get('tapped')]
    if 'flying' in keywords:
        blockers=[x for x in blockers
                  if 'flying' in abilities(x) or 'reach' in abilities(x)]
    if 'menace' in keywords:
        return len(blockers)>=2
    return bool(blockers)


@dataclass(frozen=True)
class AdaptiveGarboPolicy(s.Policy):
    version: int = 5
    scope: str = 'garbo-public-tactical-overlay-v1'

    def choose(self, observation: s.Observation) -> s.Candidate:
        original=super().choose(observation)
        if observation.phase not in ('attack','block'):
            return original
        state=json.loads(observation.public_state)
        players=state.get('players',[])
        if len(players)!=2:
            return original
        seat=observation.seat
        own=players[seat]
        opponent=players[1-seat]
        if observation.phase=='attack':
            commander_id=str(seat)+'-commander'
            commander=next((x for x in own.get('battlefield',[])
                            if x['id']==commander_id and x.get('isCreature')),None)
            if commander is None or defender_can_block(commander,opponent.get('battlefield',[])):
                return original
            already=(opponent.get('commanderDamage') or {}).get(commander_id,0)
            # Public P/T includes all known battlefield modifiers. Do not
            # invent a victory if the commander cannot finish this turn.
            damage=max(0,commander.get('power',0))
            if already+damage<21:
                return original
            finishing=[a for a in observation.legal_actions if a.kind=='attack_group'
                       and commander_id in a.attack_ids]
            return max(finishing,key=lambda a:(
                sum(w*f for w,f in zip(self.weights,a.features)),a.id)) if finishing else original

        enemy_commander_id=str(1-seat)+'-commander'
        commander=next((x for x in opponent.get('battlefield',[])
                        if x['id']==enemy_commander_id and x.get('isCreature')),None)
        if commander is None:
            return original
        damage=(own.get('commanderDamage') or {}).get(enemy_commander_id,0)
        # The defensive kernel generates a finite set of legal block
        # assignments. Prefer any candidate that explicitly blocks the lethal
        # incoming commander, then use the original utility to break ties.
        if damage+max(0,commander.get('power',0))<21:
            return original
        candidates=[a for a in observation.legal_actions if a.kind=='group_blocks'
                    and any(attacker==enemy_commander_id and blockers
                            for attacker,blockers in a.blocks)]
        if not candidates:
            return original
        return max(candidates,key=lambda a:(
            sum(w*f for w,f in zip(self.weights,a.features)),a.id))
