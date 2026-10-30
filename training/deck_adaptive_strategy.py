"""Deck-derived, public-state-adaptive Commander policy (diagnostic only).

The exact same algorithm runs for every deck. A pre-game profile is inferred from
the OWN submitted decklist (all printed cards are known to their owner), never
from the shuffled library order, opponent hand/decklist, or future game events.
During play the strategy recomputes from the own hand and public observation.
This is a heuristic strategy hypothesis, NOT reinforcement learning or legal MTG AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
import json
import re

import simulator as s
from goblin_strategy import _combat_estimate, _mana_value, _words
from strategy_building_blocks import StrategyRoute, map_mechanics, compose_routes, dependency_links

_CASTS = frozenset(('cast','cast_commander','cast_exile','cast_flashback','cast_modal_back','bestow'))
_TYPES = ('Creature','Enchantment','Artifact','Land','Instant','Sorcery')
_THEMES = ('tribal_swarm','token_swarm','enchantment_value','lifegain',
           'spellslinger','artifact_value','graveyard_value','midrange')


@dataclass(frozen=True)
class DeckPlan:
    """Immutable deck knowledge, independent of shuffled draw order."""
    primary: str = 'midrange'
    secondary: str = 'midrange'
    tribe: str = ''
    metrics: tuple[tuple[str, int], ...] = ()
    rankings: tuple[tuple[str, float], ...] = ()
    commander_types: tuple[str, ...] = ()
    routes: tuple[StrategyRoute, ...] = ()
    card_roles: tuple[tuple[str, tuple[str, ...]], ...] = ()
    commander_roles: tuple[str, ...] = ()
    links: tuple[tuple[str, str, str], ...] = ()

    def metric(self, name):
        return dict(self.metrics).get(name, 0)

    def score(self, name):
        return dict(self.rankings).get(name, 0.0)

    def describe(self):
        return dict(primary=self.primary, secondary=self.secondary, tribe=self.tribe,
                    metrics=dict(self.metrics), rankings=dict(self.rankings),
                    strategyRoutes=[r.describe() for r in self.routes],
                    strategyDependencies=[dict(source=a, supplies=b, enables=c)
                                          for a,b,c in self.links[:20]],
                    totalDependencies=len(self.links))


def _card_mana_value(raw):
    tokens = re.findall(r'\{([^{}]+)\}', raw.get('manaCost') or '')
    return sum(int(t) if t.isdigit() else 0 if t.upper() == 'X' else 1 for t in tokens)


def analyze_deck(deck: dict) -> DeckPlan:
    """Infer repeatable synergistic lines from printed text/types, not card names.

    The commander is counted twice in the textual synergy signals because it is
    reliably available. The mainboard's quantity matters, not unique entries.
    """
    cards = []
    for raw in deck.get('mainboard', ()):
        count = max(0, int(raw.get('quantity', 1)))
        cards.extend([raw] * min(count, 100))
    commanders = list(deck.get('commanders', ()))
    if not cards or not commanders:
        raise ValueError('Deck strategy needs mainboard and a commander')
    creatures = [c for c in cards if 'Creature' in c.get('types', ())]
    subtype_counts = Counter(t for c in creatures for t in c.get('subTypes', ())
                             if t not in ('Aura','Equipment','Vehicle'))
    tribe, tribe_count = subtype_counts.most_common(1)[0] if subtype_counts else ('', 0)
    combined = cards + commanders * 2
    metrics = Counter()
    for card in cards:
        for kind in _TYPES:
            if kind in card.get('types', ()):
                metrics[kind.lower()] += 1
        if 'Aura' in card.get('subTypes', ()):
            metrics['auras'] += 1
        if 'Land' not in card.get('types', ()) and _card_mana_value(card) <= 3:
            metrics['cheap_spells'] += 1
    for card in combined:
        text = card.get('oracleText', '').lower()
        if re.search(r'\bcreate\b.{0,110}\btoken\b', text, re.S):
            metrics['token_makers'] += 1
        if re.search(r'\b(gain \d+ life|gain life|lifelink|life you gain|whenever you gain life)\b', text):
            metrics['lifegain_payoffs'] += 1
        if re.search(r'\b(enchantment|enchanted|enchantments|aura|constellation)\b', text):
            metrics['enchantment_payoffs'] += 1
        if re.search(r'\bwhenever you cast\b|\binstant or sorcery\b|\bcopy target (?:instant|sorcery)\b', text):
            metrics['spell_payoffs'] += 1
        if re.search(r'\bartifact(s)? you control\b|\bwhenever an artifact\b', text):
            metrics['artifact_payoffs'] += 1
        if re.search(r'\bgraveyard\b|\breturn target creature card\b', text):
            metrics['graveyard_payoffs'] += 1
        if tribe and re.search(r'\b' + re.escape(tribe.lower()) + r's?\b', text):
            metrics['tribal_payoffs'] += 1
    metrics['tribe_members'] = tribe_count
    metrics['creature_count'] = len(creatures)
    metrics['deck_size'] = len(cards)
    metrics['average_mana_value_x100'] = round(
        100 * sum(_card_mana_value(c) for c in cards if 'Land' not in c.get('types', ())) /
        max(1, len(cards) - metrics['land']))
    metrics['commander_mana_value'] = _card_mana_value(commanders[0])
    ranks = {
        'tribal_swarm': (0.28 * max(0, tribe_count - 3) + 0.18 * metrics['tribal_payoffs']
                         + 0.08 * metrics['token_makers']) if tribe_count >= 6 else 0,
        'token_swarm': 0.31 * metrics['token_makers'] + 0.045 * metrics['creature_count'],
        'enchantment_value': (0.23 * metrics['enchantment'] +
                              0.16 * metrics['enchantment_payoffs'] +
                              0.11 * metrics['auras']),
        'lifegain': 0.32 * metrics['lifegain_payoffs'],
        'spellslinger': 0.19 * (metrics['instant'] + metrics['sorcery']) +
                        0.44 * metrics['spell_payoffs'],
        'artifact_value': 0.24 * metrics['artifact'] + 0.23 * metrics['artifact_payoffs'],
        'graveyard_value': 0.28 * metrics['graveyard_payoffs'],
        'midrange': 1.7,
    }
    ranked = sorted(ranks.items(), key=lambda row: (-row[1], row[0]))
    # Strategy routes are composed from reusable rules-text roles, independent
    # of the legacy archetype names and from the exact same own decklist.
    mechanics = map_mechanics(deck)
    routes = compose_routes(mechanics)
    return DeckPlan(ranked[0][0], ranked[1][0], tribe,
                    tuple(sorted(metrics.items())), tuple(sorted((k,round(v,3)) for k,v in ranks.items())),
                    tuple(commanders[0].get('types', ())), routes,
                    tuple((c.name, c.blocks) for c in mechanics), mechanics[-1].blocks,
                    dependency_links(mechanics))


def tactical_mode(observation: s.Observation) -> str:
    """In-game adaptation using only the observation boundary."""
    try:
        state = json.loads(observation.public_state)
        own = state['players'][observation.seat]
        foe = state['players'][1-observation.seat]
    except (ValueError, KeyError, IndexError, TypeError):
        return 'develop'
    my_life, foe_life = own.get('life', 40), foe.get('life', 40)
    friends = [x for x in own.get('battlefield', ()) if x.get('isCreature')]
    enemies = [x for x in foe.get('battlefield', ()) if x.get('isCreature')]
    ready_enemies = [x for x in enemies if not x.get('tapped')]
    ready_friends = [x for x in friends if not x.get('tapped') and not x.get('fresh')]
    my_power = sum(max(0,x.get('power',0)) for x in ready_friends)
    enemy_power = sum(max(0,x.get('power',0)) for x in ready_enemies)
    # Never assume all available power connects through blockers.
    reachable, _ = _combat_estimate(ready_friends, ready_enemies)
    if (my_life <= max(10, enemy_power + 3) and
            (my_life <= 15 or enemy_power >= my_life)):
        return 'stabilize'
    if foe_life <= max(10, reachable * 1.1) and friends:
        return 'finish'
    if observation.turn >= 7 and len(friends) <= 1 and len(enemies) >= 2:
        return 'rebuild'
    if observation.turn <= 4:
        return 'develop'
    return 'pressure' if friends and (my_power > 2 or foe_life < 25) else 'develop'


@dataclass(frozen=True)
class AdaptiveDeckPolicy(s.Policy):
    """One AI algorithm: profile own deck, assess battlefield, pursue current goal."""
    version: int = 5
    scope: str = 'deck-adaptive-public-diagnostic-v2'
    plan: DeckPlan = field(default_factory=DeckPlan)

    def decision_context(self, observation: s.Observation) -> dict:
        return {'strategyPlan': self.plan.primary, 'strategySupport': self.plan.secondary,
                'strategyMode': tactical_mode(observation),
                'strategyRoute': self.plan.routes[0].describe() if self.plan.routes else None}

    def choose(self, observation: s.Observation) -> s.Candidate:
        if not observation.legal_actions:
            raise ValueError('No legal action')
        try:
            state = json.loads(observation.public_state)
            own = state['players'][observation.seat]
            foe = state['players'][1 - observation.seat]
        except (ValueError, KeyError, IndexError, TypeError):
            return super().choose(observation)
        mode = tactical_mode(observation)
        own_board = own.get('battlefield', ())
        foe_board = foe.get('battlefield', ())
        creatures = {p['id']:p for p in own_board if p.get('isCreature')}
        defenders = [p for p in foe_board if p.get('isCreature') and not p.get('tapped')]
        own_permanents = {p['id']:p for p in own_board}
        enemy_permanents = {p['id']:p for p in foe_board}
        lands = sum(p.get('kind')=='land' for p in own_board)
        enchants = sum(p.get('kind') in ('aura','enchantment') for p in own_board)
        enemy_life = foe.get('life', 40)
        own_life = own.get('life', 40)
        hand = {c.id:c for c in observation.own_hand}
        p, q = self.plan.primary, self.plan.secondary
        roles = dict(self.plan.card_roles)
        route_steps = set(self.plan.routes[0].steps) if self.plan.routes else set()
        def affinity(name):
            return 1.0 if p == name else 0.45 if q == name else 0.0

        def utility(a):
            score = sum(w*f for w,f in zip(self.weights,a.features))
            kind = a.kind
            if kind in ('land','land_back'):
                score += (12 if lands < 2 else 8 if lands < 3 else
                          4 if lands < 4 else 2 if lands < 6 else -1)
                card = hand.get(a.card_id)
                if card:
                    land = card.modal_land_face if kind == 'land_back' else card
                    if land:
                        score -= 1.2 if land.enters_tapped else 0
                        score += 0.2 * min(3,land.mask.bit_count())
                    if kind == 'land_back' and lands >= 3:
                        score -= 3
            elif kind in _CASTS:
                card = hand.get(a.card_id)
                action_roles = set(self.plan.commander_roles if kind == 'cast_commander'
                                   else roles.get(card.name, ()) if card else ())
                # Generalizable rules-to-strategy path: mana -> board -> engines
                # -> buffs -> combat. Roles have value ONLY for already-legal
                # actions and are adjusted by visible board conditions.
                route_factor = 1 if not route_steps else 1 if action_roles & route_steps else 0.3
                if 'mana_engine' in action_roles and observation.turn <= 5 and lands < 6:
                    score += 3 * route_factor
                if 'creature_supply' in action_roles or 'token_supply' in action_roles:
                    score += (3.5 if mode == 'rebuild' or not creatures else 1.2) * route_factor
                if 'board_amplifier' in action_roles:
                    score += (4.5 if len(creatures) >= 3 else 2 if creatures else -4) * route_factor
                if 'card_engine' in action_roles:
                    score += (3 if len(hand) <= 3 else 1.2) * route_factor
                if 'damage_payoff' in action_roles:
                    score += (4 if len(creatures) >= 3 else 1.5) * route_factor
                if 'life_engine' in action_roles and mode == 'stabilize':
                    score += 3
                if kind == 'cast_commander':
                    score += 2 + (3 if lands >= self.plan.metric('commander_mana_value') else 0)
                    if p=='enchantment_value' and 'Creature' in self.plan.commander_types:
                        score += 2 + min(3,enchants * 0.45)
                    if mode=='rebuild':
                        score += 4
                elif card:
                    definition = card.event_definition
                    types = definition.types if definition else frozenset(card.printed_types)
                    subtypes = definition.subtypes if definition else frozenset()
                    mv = _mana_value(card)
                    is_creature = 'Creature' in types or card.kind=='creature'
                    if is_creature:
                        score += 2 + (2 if len(creatures) < 2 else 0)
                        if observation.turn <= 4:
                            score += max(-2, 2.5 - 0.6 * mv)
                        if self.plan.tribe in subtypes and self.plan.tribe:
                            score += 4.5 * affinity('tribal_swarm')
                        if mode=='rebuild':
                            score += 2.5
                    if 'Enchantment' in types or card.kind=='enchantment':
                        score += (5 + min(4,enchants * 0.55)) * affinity('enchantment_value')
                        if 'Aura' in subtypes:
                            score += 2 * affinity('enchantment_value') if creatures else -4
                    if 'Artifact' in types or card.kind in ('artifact','equipment','mana_artifact'):
                        score += 2 * affinity('artifact_value')
                    if 'Instant' in types or 'Sorcery' in types:
                        score += 2 * affinity('spellslinger')
                    text_program = definition if definition else None
                    if text_program:
                        if text_program.cost_reductions:
                            score += 2.5 if observation.turn <= 5 else 1
                        if text_program.token_replacements or text_program.token_action_triggers:
                            score += 2.5 * max(affinity('token_swarm'),affinity('tribal_swarm'))
                        if text_program.attack_effects or text_program.attack_watchers:
                            score += 1.2 if creatures else 0
                        if text_program.triggers and len(creatures) >= 2:
                            score += 0.5
                    if card.kind=='token_spell' or card.x_effect=='tokens':
                        tokens = a.x_value if a.x_value is not None else card.token_count
                        score += (1.5 + min(7,max(0,tokens) * 0.85)) * max(affinity('token_swarm'),affinity('tribal_swarm'),0.2)
                    if card.life or 'lifelink' in card.traits.lower():
                        score += (1.5 if mode=='stabilize' else 1) * affinity('lifegain')
                    if card.removal in ('destroy_all_creatures','destroy_creatures_reward','destroy_toughness_min','modal_sweep'):
                        score += 3.5 * (len(defenders) - len(creatures)) - 4
                        if mode=='stabilize' and len(defenders) > len(creatures):
                            score += 5
                    if card.kind=='removal_spell' and a.target_permanent in enemy_permanents:
                        target=enemy_permanents[a.target_permanent]
                        score += min(8,max(0,target.get('power',0))) + (5 if mode=='stabilize' else 2)
                    elif card.kind=='removal_spell' and a.target_permanent in own_permanents:
                        score -= 20
            elif kind == 'attack_group':
                attackers = [creatures[i] for i in a.attack_ids if i in creatures]
                expected, casualties = _combat_estimate(attackers, defenders)
                damage_i = s.FEATURES.index('damage')
                lethal_i = s.FEATURES.index('lethal')
                score += self.weights[damage_i] * (expected - a.features[damage_i])
                if expected < enemy_life:
                    score -= self.weights[lethal_i] * a.features[lethal_i]
                score += expected * (1.3 if mode=='finish' else
                                     0.7 if mode=='pressure' else 0.35)
                score -= casualties * (8 if mode=='stabilize' else 6 if mode=='rebuild' else 4)
                if expected >= enemy_life:
                    score += 200
                if not attackers:
                    score -= 5
                if not expected and defenders:
                    score -= 5
                if len(attackers)>=2 and p in ('tribal_swarm','token_swarm'):
                    score += 1.5
                if mode=='stabilize' and casualties and own_life < 15:
                    score -= 5
                if not defenders:
                    prior = foe.get('commanderDamage') or {}
                    for x in attackers:
                        if prior.get(x['id'],0)+max(0,x.get('power',0)) >= 21:
                            score += 200
            elif kind in ('activate_tokens','activate_tribal_tokens','activate_discard_tokens'):
                score += 2.5 * max(affinity('token_swarm'),affinity('tribal_swarm'),0.3)
                if len(creatures)>8:
                    score -= 4
                if kind=='activate_discard_tokens':
                    score -= 3
            elif kind in ('equip','equip_planeswalker'):
                source = own_permanents.get(a.card_id,{})
                score -= 10 if source.get('attachedTo') else 2
            elif kind.startswith('activate_sacrifice'):
                score -= 5 if p in ('tribal_swarm','token_swarm') else 2
            elif kind=='group_blocks':
                for attacker_id, blocker_ids in a.blocks:
                    attacker=enemy_permanents.get(attacker_id,{})
                    blocks=[own_permanents[b] for b in blocker_ids if b in own_permanents]
                    if not attacker or not blocks:
                        continue
                    if sum(max(0,b.get('power',0)) for b in blocks)>=max(1,attacker.get('toughness',1)) or any('deathtouch' in _words(b) for b in blocks):
                        score += 3 + 1.3 * max(0,attacker.get('power',0))
                    for b in blocks:
                        if attacker.get('power',0)>=max(1,b.get('toughness',1)) or 'deathtouch' in _words(attacker):
                            score -= (2 if mode=='stabilize' else 4) + max(0,b.get('power',0))
            elif kind=='pass' and observation.phase in ('main','second_main') and not observation.developed_this_turn:
                score -= 3
            return score, a.id
        return max(observation.legal_actions,key=utility)
