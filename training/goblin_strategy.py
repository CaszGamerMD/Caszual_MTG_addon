"""Garbo-specific public-information tempo policy for the diagnostic MTG simulator.

This is an experimental challenger, not the Wilds policy or a trained Commander AI.
Only chooses from engine-provided legal actions. No library/deck-order knowledge.
"""
from dataclasses import dataclass
import json
import re
import simulator as s

_CASTS = {'cast', 'cast_commander', 'cast_exile', 'cast_flashback',
          'cast_modal_back', 'bestow'}


def _words(permanent):
    return {x.strip().lower() for x in permanent.get('traits', '').split(';')[-1].split(',') if x.strip()}


def _mana_value(card):
    if card.printed_mana_value is not None:
        return card.printed_mana_value
    return sum(int(t) if t.isdigit() else 0 if t.upper() == 'X' else 1
               for t in re.findall(r'\{([^{}]+)\}', card.mana_cost))


def _can_block(attacker, blocker):
    a, b = _words(attacker), _words(blocker)
    if 'shadow' in a and 'shadow' not in b or 'shadow' in b and 'shadow' not in a:
        return False
    if 'flying' in a and not ('flying' in b or 'reach' in b):
        return False
    if 'unblockable' in a or 'can\'t be blocked' in a:
        return False
    return True


def _combat_estimate(attackers, defenders):
    """Conservative one/two-blocker proxy, not a claim to solve combat rules."""
    remaining = list(defenders)
    damage = 0.0
    lost = 0.0
    for attacker in sorted(attackers, key=lambda c: (-max(0, c.get('power', 0)), c['id'])):
        power = max(0, attacker.get('power', 0))
        traits = _words(attacker)
        minimum = 2 if 'menace' in traits else 1
        viable = [b for b in remaining if _can_block(attacker, b)]
        if len(viable) < minimum:
            damage += power
            continue
        # The defender can use effective blockers, but not assign one twice.
        selected = sorted(viable, key=lambda b: (b.get('toughness', 0), b.get('power', 0)), reverse=True)[:minimum]
        for blocker in selected:
            remaining.remove(blocker)
        toughness = sum(max(0, b.get('toughness', 0)) for b in selected)
        if 'trample' in traits:
            damage += max(0, power - toughness)
        retaliation = sum(max(0, b.get('power', 0)) for b in selected)
        deadly = any('deathtouch' in _words(b) and b.get('power', 0) > 0 for b in selected)
        first = 'first strike' in traits or 'double strike' in traits
        kills_first = first and (power >= toughness or 'deathtouch' in traits and power >= minimum)
        protected = 'indestructible' in traits
        if not protected and (deadly or retaliation >= max(1, attacker.get('toughness', 1))) and not kills_first:
            lost += 1.8 + 0.5 * power
    return damage, lost


@dataclass(frozen=True)
class GarboPressurePolicy(s.Policy):
    """Build width, push meaningful damage, and avoid bad all-in attacks."""
    version: int = 3
    scope: str = 'garbo-public-tempo-diagnostic-v1'

    def choose(self, observation: s.Observation) -> s.Candidate:
        if not observation.legal_actions:
            raise ValueError('No legal action')
        state = json.loads(observation.public_state)
        players = state.get('players', ())
        if len(players) != 2 or observation.seat not in (0, 1):
            return super().choose(observation)
        own = players[observation.seat]
        enemy = players[1 - observation.seat]
        board = own.get('battlefield', ())
        foes = enemy.get('battlefield', ())
        creatures = {p['id']: p for p in board if p.get('isCreature')}
        defenders = [p for p in foes if p.get('isCreature') and not p.get('tapped')]
        lands = sum(p.get('kind') == 'land' for p in board)
        enemy_life = enemy.get('life', 40)
        own_life = own.get('life', 40)
        hand = {c.id: c for c in observation.own_hand}
        enemy_creatures = sum(p.get('isCreature', False) for p in foes)
        enemy_permanents = {p['id']: p for p in foes}
        own_permanents = {p['id']: p for p in board}
        previous_damage = enemy.get('commanderDamage') or {}

        def score(action):
            value = sum(w * f for w, f in zip(self.weights, action.features))
            kind = action.kind
            if kind in ('land', 'land_back'):
                # Land drops don't exhaust the main phase; unlock future casts.
                value += (12 if lands < 2 else 8 if lands < 3 else
                          4 if lands < 4 else 1.5 if lands < 6 else -2)
                card = hand.get(action.card_id)
                if card:
                    land = card.modal_land_face if kind == 'land_back' else card
                    if land is not None:
                        value -= 1.25 if land.enters_tapped else 0
                        value += 0.2 * min(3, land.mask.bit_count())
                    if kind == 'land_back' and lands >= 3:
                        value -= 3  # Preserve spell face when mana is established.
            elif kind in _CASTS:
                card = hand.get(action.card_id)
                if kind == 'cast_commander':
                    value += (4 if lands >= 4 else 1) + (1 if not creatures else 0)
                elif card:
                    definition = card.event_definition
                    types = definition.types if definition else frozenset(card.printed_types)
                    subtypes = definition.subtypes if definition else frozenset()
                    is_goblin = 'Goblin' in subtypes
                    mv = _mana_value(card)
                    if 'Creature' in types or card.kind == 'creature':
                        value += 2.5 + (3.5 if is_goblin else 0) + (1.5 if len(creatures) < 3 else 0)
                        value += max(-2, 2 - mv) if observation.turn <= 4 else 0
                    if card.kind == 'token_spell' or card.x_effect == 'tokens':
                        count = action.x_value if action.x_value is not None else card.token_count
                        value += 2 + min(7, max(0, count) * (1.1 if len(creatures) < 7 else 0.45))
                    if definition:
                        if definition.cost_reductions:
                            value += 3 if observation.turn <= 5 else 1
                        if definition.token_replacements or definition.token_action_triggers:
                            value += 2.5 if len(creatures) >= 2 else 1
                        if definition.attack_effects or definition.attack_watchers:
                            value += 1.5 if creatures else 0.5
                        if definition.triggers and len(creatures) >= 2:
                            value += 1
                    if card.removal in ('destroy_all_creatures', 'destroy_creatures_reward', 'destroy_toughness_min', 'modal_sweep'):
                        # Board wipes often reverse Garbo's best advantage.
                        value += 3.5 * (enemy_creatures - len(creatures)) - 5
                    if card.kind == 'removal_spell' and action.target_permanent in enemy_permanents:
                        target = enemy_permanents[action.target_permanent]
                        value += min(7, max(0, target.get('power', 0))) + (3 if target.get('isCreature') else 1)
                    elif card.kind == 'removal_spell' and action.target_permanent in own_permanents:
                        value -= 20
            elif kind == 'attack_group':
                group = [creatures[i] for i in action.attack_ids if i in creatures]
                expected, casualties = _combat_estimate(group, defenders)
                # Replace the engine's optimistic raw-damage and lethal features.
                damage_index = s.FEATURES.index('damage')
                value += self.weights[damage_index] * (expected - action.features[damage_index])
                if expected < enemy_life:
                    lethal_index = s.FEATURES.index('lethal')
                    value -= self.weights[lethal_index] * action.features[lethal_index]
                value += expected * (0.6 if observation.turn >= 5 else 0.3)
                value -= 4 * casualties
                if expected >= enemy_life:
                    value += 200
                if not group:
                    value -= 5
                if not expected and defenders:
                    value -= 4
                if len(group) >= 2 and len(creatures) >= 2:
                    value += 1.5  # Group-attack triggers may reward a wide board.
                if not defenders and expected and enemy_life <= 2 * expected:
                    value += 5
                for attacker in group:
                    prior = previous_damage.get(attacker['id'], 0)
                    if prior + max(0, attacker.get('power', 0)) >= 21 and not defenders:
                        value += 200  # Potential 21 commander-damage finish.
            elif kind in ('activate_tokens', 'activate_tribal_tokens', 'activate_discard_tokens'):
                value += 2 if len(creatures) < 7 else -1
                if kind == 'activate_discard_tokens':
                    value -= 3  # Discarding a card is a real cost.
            elif kind == 'equip' or kind == 'equip_planeswalker':
                source = own_permanents.get(action.card_id, {})
                target = own_permanents.get(action.target_permanent, {})
                value -= 12 if source.get('attachedTo') else 2
                if target.get('isCreature') and not target.get('fresh'):
                    value += 0.5 * max(0, target.get('power', 0))
            elif kind.startswith('activate_sacrifice'):
                value -= 6  # Do not convert board presence into trivial +1/+1.
            elif kind == 'pass':
                if observation.phase in ('main', 'second_main') and not observation.developed_this_turn:
                    value -= 3
            if kind == 'group_blocks':
                for attacker_id, blocker_ids in action.blocks:
                    attacker = enemy_permanents.get(attacker_id, {})
                    blocks = [own_permanents[b] for b in blocker_ids if b in own_permanents]
                    if not attacker or not blocks:
                        continue
                    force = sum(max(0, b.get('power', 0)) for b in blocks)
                    if force >= max(1, attacker.get('toughness', 1)) or any(
                            'deathtouch' in _words(b) for b in blocks):
                        value += 2 + 1.3 * max(0, attacker.get('power', 0))
                    for blocker in blocks:
                        if attacker.get('power', 0) >= max(1, blocker.get('toughness', 1)) or (
                                'deathtouch' in _words(attacker)):
                            value -= 2 + 1.25 * max(0, blocker.get('power', 0))
                if own_life <= 7:
                    value -= 2 * action.features[s.FEATURES.index('damage')]
            return value, action.id

        return max(observation.legal_actions, key=score)
