#!/usr/bin/env python3
"""Independent self-play sandbox, strict real-deck intake, and human-readable replays.
The Java subset supplies card parsing and combat; diagnostic mana pools extend its payment rules.
This is NOT a complete Commander rules engine or a Minecraft entity test.
"""
from __future__ import annotations
import argparse
from card_events import Game as EventGame, Permanent as EventPermanent, Definition as EventDefinition, parse_card as parse_event_card, rule_text
import base64
from oracle_abilities import parse_token_creation, StaticEffect, Selector
import mana_pool
import opening_hand
import x_spells
from advanced_simulator import AdvancedRules,root
import library_effects
from priority_stack import PriorityStack
from dataclasses import dataclass, field, replace, asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import tempfile
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FEATURES = ("power", "toughness", "evasion", "haste", "lethal", "damage",
            "survive", "life", "draw", "cost", "pass")
DEFAULT_WEIGHTS = dict(zip(FEATURES, (1., .3, .8, .6, 100., 3., 1., .2, .7, -.1, -2.)))
DIAGNOSTIC_RULINGS = {
    "Blood Artist": "Each creature death, including an opponent's creature or Blood Artist itself, creates a separate trigger. Simultaneous deaths use the battlefield immediately before the deaths. The two-player diagnostic chooses the opponent as the target.",
    "Zulaport Cutthroat": "Each death of a creature controlled by Cutthroat's controller, including Cutthroat itself, creates a separate life-loss/life-gain trigger. Opposing creature deaths do not trigger it.",
    "Nested Shambler": "Use its power immediately before it died, including applicable bonuses and counters. Create that many tapped green 1/1 Squirrel tokens under its last controller's control; zero or negative power creates none.",
    "Impact Tremors": "Trigger separately for each creature entering under its controller's control, including tokens. Finish the entire token-creation ability before resolving these noncombat damage triggers. Vehicles entering as noncreatures do not trigger it.",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically so interrupted writes do not corrupt retained checkpoints.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class RulesBridge:
    """Long-lived local Java worker; requests contain data, never shell code."""
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="casz-mtg-rules-")
        source = ROOT / "src/main/java/dev/casz/caszualmtg"
        paths = [source / (name + ".java") for name in
                 ("CommanderOracle", "CommanderMana", "CommanderSimpleCards", "CommanderSimpleSpells")]
        paths.append(HERE / "java/RulesBridge.java")
        compiler = [shutil.which("javac")] if shutil.which("javac") else ["java", "com.sun.tools.javac.Main"]
        try:
            subprocess.run(compiler + ["-d", self.directory.name] + [str(p) for p in paths],
                           check=True, capture_output=True, text=True)
            self.process = subprocess.Popen(
                ["java", "-cp", self.directory.name, "dev.casz.caszualmtg.training.RulesBridge"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", bufsize=1)
        except Exception:
            self.directory.cleanup()
            raise
        self.cache: dict[tuple[str, ...], dict] = {}

    def query(self, *args) -> dict:
        key = tuple(str(a) for a in args)
        if key not in self.cache:
            assert self.process.stdin is not None and self.process.stdout is not None
            self.process.stdin.write("\t".join(base64.b64encode(a.encode()).decode() for a in key) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Rules worker stopped; match must not continue.")
            result = json.loads(line)
            if "error" in result:
                raise RuntimeError(result["error"])
            self.cache[key] = result
        return dict(self.cache[key])

    def close(self):
        if hasattr(self, "process"):
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process.stdout.close()
            self.process.stderr.close()
        self.directory.cleanup()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


def type_line(card: dict) -> str:
    return " ".join(card.get("superTypes", []) + card.get("types", [])) + (
        " — " + " ".join(card["subTypes"]) if card.get("subTypes") else "")


def audit_card(rules: RulesBridge, card: dict) -> dict:
    # The small interpreter must not silently choose a face of a transform/MDFC.
    if card.get("layout", "normal") != "normal" or card.get("faces"):
        return {"kind": "unsupported", "reason": "multiple faces or non-normal layout"}
    return rules.query("audit", card["name"], type_line(card), card.get("oracleText", ""),
                       card.get("manaCost") or "", card.get("power") or "", card.get("toughness") or "")


def question(card: dict, reason: str, deck: str) -> dict:
    identity = {k: card.get(k) for k in
                ("name", "oracleId", "oracleText", "manaCost", "power", "toughness", "layout", "faces")}
    identity["typeLine"] = type_line(card)
    identifier = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    return {"id": identifier, "status": "open", "blocking": True, "deck": deck,
            "card": card["name"], "oracleText": card.get("oracleText", ""),
            "typeLine": type_line(card), "reason": reason,
            "question": "How should the rules backend resolve " + reason + " for " + card["name"]
                        + ", including required timing, targets, choices, costs and zone changes?",
            "answer": None, "resolution": "Needs implementation and regression tests; an answer alone does not enable the card."}


def audit_decks(rules: RulesBridge, decks: list[dict]) -> dict:
    questions: dict[str, dict] = {}
    coverage = []
    for deck in decks:
        supported, unsupported = [], []
        for card in deck.get("commanders", []) + deck.get("mainboard", []):
            result = audit_card(rules, card)
            record = {"card": card["name"], "quantity": card["quantity"], **result}
            (unsupported if result["kind"] == "unsupported" else supported).append(record)
            if result["kind"] == "unsupported":
                q = question(card, result["reason"], deck["name"])
                if q["id"] in questions:
                    questions[q["id"]]["alsoInDecks"] = sorted(set(
                        questions[q["id"]].get("alsoInDecks", []) + [deck["name"]]))
                else:
                    questions[q["id"]] = q
        count = sum(c["quantity"] for c in deck.get("mainboard", []))
        commanders = sum(c["quantity"] for c in deck.get("commanders", []))
        if commanders != 1 or count != 99:
            q = {"id": "deck-size-" + str(deck.get("sourceDeckId", deck["name"])),
                 "status": "open", "blocking": True, "deck": deck["name"], "card": "",
                 "reason": "deck structure", "question": "Resolve expected one commander plus 99 main-deck cards.",
                 "answer": None}
            questions[q["id"]] = q
        coverage.append({"name": deck["name"], "commanders": commanders, "mainCount": count,
                         "supported": supported, "unsupported": unsupported})
    # Even completely parsed decks need the full game backend before real Commander training.
    questions["full-commander-backend"] = {
        "id": "full-commander-backend", "status": "open", "blocking": True, "card": "",
        "reason": "simulation scope",
        "question": "Complete arbitrary Commander targeting, replacement/prevention and continuous-effect dependencies, multiplayer and unsupported card programs before treating diagnostics as full games.",
        "answer": None}
    return {"schemaVersion": 1, "kind": "rules-review", "status": "blocked",
            "learningEligible": False, "decks": coverage, "questions": list(questions.values())}


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    kind: str
    mana_cost: str = ""
    traits: str = ""
    power: int = 0
    toughness: int = 0
    mask: int = 0
    mana_production: tuple[int, ...] = ()
    enters_tapped: bool = False
    draw: int = 0
    life: int = 0
    land_rule: str = ""
    land_subtypes: tuple[str, ...] = ()
    basic_land: bool = False
    snow: bool = False
    event_definition: EventDefinition | None = None
    storm: bool = False
    x_effect: str = ""
    token_count: int = 0
    token_definition: EventDefinition | None = None
    token_tapped: bool = False
    is_token: bool = False
    colors: tuple[str, ...] = ()
    legendary: bool = False
    instant: bool = False
    counter_filter: str = ""
    removal: str = ""
    removal_min_toughness: int = 0
    removal_no_regenerate: bool = False
    printed_types: tuple[str, ...] = ()
    printed_mana_value: int | None = None
    physical_id: str = ""
    blink: bool = False
    rebound: bool = False
    blink_to_controller: bool = False
    flashback_cost: str = ""
    graveyard_return_subtype: str = ""
    target_modifier: tuple = ()  # (power, toughness, keyword choices, conditional draw subtype).
    modal_sweeps: tuple = ()  # Ordered destroy modes, with two indices selected on casting.
    sweep_reward: tuple = ()  # (nontoken only, Treasures per destroyed creature, tapped).
    forced_sacrifice: tuple = ()  # (opponents/all players, count) on spell resolution.
    mana_as_any_color: bool = False
    color_draw_cost: str = ''
    # Modal double-faced cards are one physical card. The front card is kept
    # in all hidden/nonbattlefield zones; a land back may be chosen only on play.
    modal_land_face: Card | None = None
    modal_front_face: Card | None = None
    modal_spell_face: Card | None = None  # Alternate castable back, same physical card.
    transform_back_face: Card | None = None  # Noncastable back for a transforming Saga.



def land_enters_tapped(card: Card, lands: list[Card]) -> bool:
    if card.land_rule == "two_other_lands":
        return len(lands) < 2
    if card.land_rule == "two_basics":
        return sum(land.basic_land for land in lands) < 2
    if card.land_rule.startswith("has_type:"):
        required = set(card.land_rule.removeprefix("has_type:").split(","))
        return not any(required.intersection(land.land_subtypes) for land in lands)
    return card.enters_tapped


@dataclass
class Permanent:
    card: Card
    tapped: bool = False
    fresh: bool = True
    saddled: bool = False
    animated: bool = False
    counters: int = 0
    marked_damage: int = 0
    attached_to: str | None = None
    temporary_power: int = 0
    temporary_toughness: int = 0
    temporary_abilities: frozenset[str] = frozenset()
    bestowed: bool = False
    entered_at: int = 0
    attachment_at: int = 0
    lost_abilities: dict[str,int] = field(default_factory=dict)
    temporary_ability_times: dict[str,int] = field(default_factory=dict)
    loyalty: int | None = None
    charge_counters: int = 0
    chosen_subtype: str = ''
    keyword_counters: frozenset[str] = frozenset()
    regeneration_shields: int = 0
    temporary_land_power: int | None = None
    temporary_land_subtype: str = ''
    class_level: int = 1
    lore_counters: int = 0


@dataclass
class Player:
    library: list[Card]
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    exile: list[Card] = field(default_factory=list)
    life: int = 40
    failed_draw: bool = False
    mana_pool: list[int] = field(default_factory=lambda: [0]*6)
    command_zone: Card | None = None
    commander_id: str = ""
    commander_casts: int = 0
    commander_damage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    card_id: str = ""
    features: tuple[float, ...] = ()
    label: str = ""
    tap_ids: tuple[str, ...] = ()
    x_value: int | None = None
    target_stack: int | None = None
    target_permanent: str = ""
    activation_index: int = 0
    attack_ids: tuple[str, ...] = ()
    blocks: tuple = ()
    discard_id: str = ''
    modal_modes: tuple[int, ...] = ()


@dataclass(frozen=True)
class Observation:
    """The agent boundary: own hand + public information, no library order or enemy hand."""
    seat: int
    turn: int
    phase: str
    own_hand: tuple[Card, ...]
    public_state: str  # JSON string is immutable; it contains no private identities.
    legal_actions: tuple[Candidate, ...]
    developed_this_turn: bool = False


@dataclass(frozen=True)
class Policy:
    version: int = 0
    weights: tuple[float, ...] = tuple(DEFAULT_WEIGHTS.values())
    scope: str = "sandbox-single-attacker-v1"

    def choose(self, observation: Observation) -> Candidate:
        if not observation.legal_actions:
            raise ValueError("No legal action")
        # Identical observations give identical decisions. No access to the engine or replay.
        development={"cast","cast_commander","cast_flashback","bestow","equip","station",
                     "history_tokens","activate_tokens","activate_strip"}
        def utility(action):
            score=sum(w*f for w,f in zip(self.weights,action.features))
            if observation.phase in ("main","second_main") and not observation.developed_this_turn:
                if action.kind in development:score+=1.25
                if action.kind=="pass":score-=0.75
            return score,action.id
        return max(observation.legal_actions,key=utility)

    def to_json(self):
        return {"schemaVersion": 1, "version": self.version, "scope": self.scope,
                "weights": dict(zip(FEATURES, self.weights))}

    @staticmethod
    def from_json(value):
        if value.get("scope") != "sandbox-single-attacker-v1":
            raise ValueError("Policy scope mismatch")
        weights = tuple(float(value["weights"][k]) for k in FEATURES)
        if not all(math.isfinite(w) for w in weights):
            raise ValueError("Non-finite policy weight")
        return Policy(int(value["version"]), weights)


def features(**values) -> tuple[float, ...]:
    return tuple(float(values.get(k, 0)) for k in FEATURES)


def demo_deck(seat: int) -> list[Card]:
    """Synthetic sandbox fixture, intentionally NOT represented as a legal Commander deck."""
    result = []
    for i in range(14):
        result.append(Card(f"{seat}-forest-{i}", "Forest", "land", mask=16))
    for i in range(14):
        # Vary casting/attack decisions without unsupported abilities.
        patterns = ((2, 2, "{1}{G}", ""), (3, 3, "{2}{G}", ""),
                               (1, 1, "{G}", "haste"), (4, 4, "{3}{G}", "trample"),
                               (2, 3, "{2}{G}", "vigilance"), (2, 2, "{2}{G}", "lifelink"),
                               (2, 2, "{2}{G}", "double strike"))
        p, t, cost, keywords = patterns[i % 7]
        if seat == 1 and i % 7 == 1: p, t = 2, 4
        result.append(Card(f"{seat}-creature-{i}", ("Training A " if seat == 0 else "Training B ") + str(i + 1), "creature",
                           cost, f"{p};{t};{keywords}", p, t))
    return result


class Simulator(AdvancedRules):
    """Deterministic classroom model with a broader, non-training-eligible real-deck diagnostic."""
    def __init__(self, rules: RulesBridge, seed: int, starter: int = 0,
                 policies: tuple[Policy, Policy] = (Policy(), Policy()), max_turns: int = 100,
                 decks: tuple[list[Card], list[Card]] | None = None, starting_life: int = 40,
                 diagnostic: bool = False, commanders: tuple[Card, Card] | None = None):
        if starter not in (0, 1) or max_turns < 1 or starting_life < 1:
            raise ValueError("Invalid simulation options")
        if decks is not None:
            def signature(cards, commander):
                main = sorted((c.name.casefold(),c.kind,c.mana_cost,c.traits,c.mask,c.token_count) for c in cards)
                return (commander.name.casefold() if commander else "", main)
            if signature(decks[0],commanders[0] if commanders else None) == signature(decks[1],commanders[1] if commanders else None):
                raise ValueError("Mirror matches are disabled.")
        self.rules, self.seed, self.starter = rules, seed, starter
        self.diagnostic = diagnostic
        self.policies = tuple(replace(p) for p in policies)  # frozen per-match snapshots
        self.max_turns = max_turns
        self.players = []
        for seat, cards in enumerate(decks or (demo_deck(0), demo_deck(1))):
            cards = list(cards)
            random.Random(seed * 2 + seat).shuffle(cards)
            commander = commanders[seat] if commanders else None
            self.players.append(Player(cards, life=starting_life, command_zone=commander,
                                       commander_id=commander.id if commander else ""))
        all_cards = [c for p in self.players for c in p.library] + [p.command_zone for p in self.players if p.command_zone]
        if len({c.id for c in all_cards}) != len(all_cards):
            raise ValueError("Card identities must be unique")
        self.card_owners={root(c):seat for seat,p in enumerate(self.players) for c in p.library+([p.command_zone] if p.command_zone else [])}
        self.total_cards = tuple(len(p.library) + int(p.command_zone is not None) for p in self.players)
        self.turn, self.active, self.phase = 0, starter, "setup"
        self.events: list[dict] = []
        self.decisions: list[dict] = []  # post-match data; never supplied to either player
        self.questions: list[dict] = []
        self.finished = False
        self.winner: int | None = None
        self.result = "running"
        self.combat_context=None
        self.group_combat=None
        self.entry_history=[]
        self.rebound_pending=[]
        self.exile_cast_permissions={}  # Card id -> (controller, expiry turn, creature subtype).
        self.object_sequence=0
        self._rebound_permission=None
        self.pending: str | None = None
        self.land_played = False
        self.land_plays_this_turn = 0
        self.turn_development=[False,False]
        self.opening_mulligans=[0,0]
        self.opening_reviews=[None,None]  # Private; not part of public state or AI observations
        self.opening_rng=[random.Random(f"{seed}:friendly-opening:{seat}") for seat in (0,1)]
        self.main_return = ""
        self.stack=PriorityStack(starter)
        self._current_spell=None
        self.manual_priority=False
        self._draining_priority=False
        self._resolving_stack=False
        self._waiting_triggers=[]
        self.aura_exiles={}  # Aura object id -> (owner seat, physical card) still in exile.
        self.linked_exiles={}  # (source id, entry identity) -> cards exiled by its ETB trigger.
        self.life_gained_turn=[0,0]
        self.damage_to_players=[set(),set()]  # Permanent identities that dealt positive damage to each player this turn.
        self._end_step_triggers_queued=False
        self.token_sequence = 0
        self.effect_clock = 0
        self.library_random_sequence = 0
        self.log("setup", "Two independent agents use frozen policies; sandbox rules apply.")
        for player in self.players:
            for card in player.library:
                if card.kind == "unsupported" and self.diagnostic:
                    continue  # Retained in the real library/hand but never treated as playable.
                if self.diagnostic and card.event_definition and card.event_definition.supported:
                    continue
                if self.diagnostic and card.kind == "token_spell" and card.token_count > 0 and card.token_definition is not None:
                    continue
                if self.diagnostic and card.kind == "mana_artifact" and len(card.mana_production)==6:
                    continue
                if self.diagnostic and card.kind == "x_spell" and card.x_effect in ("tokens","draw","life"):
                    continue
                if self.diagnostic and card.kind=='modifier_spell' and card.target_modifier:
                    continue
                if self.diagnostic and card.kind=="removal_spell" and card.removal in ("destroy","opponent_nonlands","destroy_artifact_enchantment","destroy_artifact_creature_token","destroy_artifact","exile_creature_life","exile_creature_basic_land","exile_creature_damaged_you","destroy_all_creatures","destroy_toughness_min","destroy_creatures_reward","modal_sweep"):
                    continue
                if self.diagnostic and card.kind=="graveyard_return_spell" and card.graveyard_return_subtype:
                    continue
                if self.diagnostic and card.blink:continue
                if self.diagnostic and card.kind=="counter_spell" and card.counter_filter in ("any","creature","noncreature"):
                    continue
                if card.kind not in ("land", "creature", "spell"):
                    self.pause("Unsupported sandbox card kind: " + card.kind, card)
                    return
                if card.kind == "land" and not 0 < card.mask <= 63:
                    self.pause("Unsupported land production", card)
                    return
                if card.kind == "creature":
                    parsed = card.traits.split(";")
                    if len(parsed) != 3 or parsed[:2] != [str(card.power), str(card.toughness)]:
                        self.pause("Missing or inconsistent creature traits", card)
                        return
                    audit = self.rules.query("audit", card.name, "Creature", parsed[2],
                                             card.mana_cost, card.power, card.toughness)
                    if audit["kind"] != "creature":
                        self.pause("Unsupported creature rule", card)
                        return
                if card.kind == "spell":
                    text = ("Draw " + str(card.draw) + " cards." if card.draw else
                            "You gain " + str(card.life) + " life.")
                    audit = self.rules.query("audit", card.name, "Sorcery", text, card.mana_cost, "", "")
                    if card.draw and card.life or audit["kind"] != "spell":
                        self.pause("Unsupported spell rule", card)
                        return
        for seat in (0, 1):
            self.prepare_opening_hand(seat)

    def prepare_opening_hand(self,seat:int):
        """Draw seven in one event; free redraws keep all seven cards."""
        p=self.players[seat]
        for attempt in range(opening_hand.FRIENDLY_MULLIGAN_LIMIT+1):
            p.hand.extend(p.library.pop() for _ in range(min(7,len(p.library))))
            self.log("opening_hand",f"Player {seat+1} draws {len(p.hand)} opening cards at once.",
                     actor=seat,count=len(p.hand),attempt=attempt)
            review=opening_hand.assess(p.hand)
            self.opening_reviews[seat]=review
            # Pursue an ideal curve first; after six free redraws prefer any
            # workable two-land/cheap-play start to a disastrous final hand.
            if (review["keep"] or
                    (attempt>=6 and opening_hand.fallback(p.hand)) or
                    attempt==opening_hand.FRIENDLY_MULLIGAN_LIMIT):
                self.opening_mulligans[seat]=attempt
                self.log("keep_hand",f"Player {seat+1} keeps {len(p.hand)} cards.",
                         actor=seat,count=len(p.hand),mulligans=attempt)
                return
            self.log("mulligan",f"Player {seat+1} takes a free friendly mulligan.",
                     actor=seat,mulligan=attempt+1)
            p.library.extend(p.hand)
            p.hand.clear()
            self.opening_rng[seat].shuffle(p.library)

    def display_permanent(self, item: Permanent) -> dict:
        game=self.event_game('main');state=game.battlefield.get(item.card.id)
        effective = self.effective_card(item,game)
        c = effective or item.card
        return {"id": c.id, "name": c.name, "kind": "aura" if item.bestowed else ("enchantment" if not effective and c.event_definition and c.event_definition.devotion else c.kind), "power": c.power,
                "toughness": c.toughness, "traits": c.traits, "tapped": item.tapped,
                "fresh": item.fresh, "saddled": item.saddled, "counters": item.counters, "isCreature": effective is not None, "bestowed": item.bestowed, "attachedTo": item.attached_to,
                "hexproof": bool(state and game.has(state,'hexproof')), "wardCosts": list(game.ward_costs(state)) if state else [], "loyalty": item.loyalty, "chargeCounters": item.charge_counters,"classLevel": item.class_level if item.card.event_definition and item.card.event_definition.class_program else None,
                "loreCounters":item.lore_counters if item.card.event_definition and item.card.event_definition.saga_chapter_scale else None}

    def state(self) -> dict:
        return {"active": self.active, "turn": self.turn, "phase": self.phase,
                "stack": self.stack.public(), "priority": self.stack.priority,
                "players": [{"seat": i, "life": p.life, "handCount": len(p.hand),
                             "libraryCount": len(p.library), "manaPool": list(p.mana_pool),
                             "battlefield": [self.display_permanent(x) for x in p.battlefield],
                             "commanderInZone": p.command_zone is not None,
                             "commanderDamage": dict(p.commander_damage),
                             "graveyard": [{"id": c.id, "name": c.name} for c in p.graveyard],
                             "exile": [{"id":c.id,"name":c.name} for c in p.exile]}
                            for i, p in enumerate(self.players)]}

    def invariant(self):
        cards=[]
        for seat,p in enumerate(self.players):
            cards.extend((seat,c) for c in p.library+p.hand+p.graveyard+p.exile+[x.card for x in p.battlefield]+([p.command_zone] if p.command_zone else []))
        cards.extend((frame.controller,frame.payload[1]) for frame in self.stack.items if frame.payload[0].get('operation')=='spell' and not frame.payload[0].get('copy'))
        if self._current_spell and not any(root(c)==root(self._current_spell[1]) for _,c in cards):cards.append(self._current_spell)
        physical=[root(c) for _,c in cards if not c.is_token]
        counts=[sum(not c.is_token and self.card_owners.get(root(c),seat)==owner for seat,c in cards) for owner in (0,1)]
        if tuple(counts)!=self.total_cards or len(physical)!=len(set(physical)) or len([c.id for _,c in cards])!=len({c.id for _,c in cards}):
            raise RuntimeError('Card conservation failed')

    def bestowed_definition(self,definition):
        # The supported bestow grammar has creature subtypes and no enchantment subtypes.
        return replace(definition,types=frozenset({'Enchantment'}),subtypes=frozenset({'Aura'}),
                       attachment=definition.bestow[2])

    def gain_life(self, seat: int, amount: int):
        """Track life gained, independent of damage/losses and total life change."""
        if amount<0:raise ValueError('Life gain amount must be nonnegative')
        # Default legal replacement ordering maximizes life gain.
        # Later decision policies may select another permitted ordering.
        gained=amount
        if amount:
            definitions=[p.card.event_definition for p in self.players[seat].battlefield if p.card.event_definition]
            gained+=sum(d.life_addition for d in definitions)
            for definition in definitions:
                if definition.life_multiplier!=1:gained*=definition.life_multiplier
        self.players[seat].life+=gained
        self.life_gained_turn[seat]+=gained
        if gained:
            # Queue once for this event even if a replacement doubled it.
            # Resolving the stack flushes these snapshots in APNAP order.
            watchers=self.event_game('main').life_gain_triggers(seat,gained)
            self._waiting_triggers.extend(
                (trigger,next(p.card for p in self.players[seat].battlefield
                              if p.card.id==trigger['source']))
                for trigger in watchers)
        if gained!=amount:self.log('life_replacement','Life-gain replacement modifies the event.',actor=seat,original=amount,gained=gained)

    def event_game(self, phase: str) -> EventGame:
        """Adapt public battlefield state to the shared type-aware event kernel."""
        game = EventGame(turn_player=self.active, phase=phase,clock=self.effect_clock,
                         life_totals={seat:player.life for seat,player in enumerate(self.players)})
        for seat, player in enumerate(self.players):
            for item in player.battlefield:
                card = item.card
                definition = card.event_definition
                if definition is None:
                    if card.kind not in ("creature","mana_artifact","land"): continue
                    keywords = frozenset(k for k in card.traits.split(";")[-1].split(",") if k)
                    definition = EventDefinition(card.name, frozenset({"Land"} if card.kind=="land" else {"Artifact"} if card.kind=="mana_artifact" else {"Creature"}), frozenset(card.land_subtypes),
                                                 card.legendary, card.power, card.toughness, keywords,
                                                 colors=frozenset(card.colors))
                if item.bestowed:definition=self.bestowed_definition(definition)
                if item.temporary_land_power is not None:
                    definition=replace(definition,
                        types=frozenset(set(definition.types)|{'Creature','Land'}),
                        subtypes=frozenset(set(definition.subtypes)|{item.temporary_land_subtype}),
                        power=item.temporary_land_power,toughness=item.temporary_land_power)
                if definition.class_program and item.class_level>=2:
                    program=definition.class_program
                    anthem=StaticEffect(Selector(relation='controller',creature=True),
                                        program[2],program[3])
                    definition=replace(definition,
                        static_effects=definition.static_effects+(anthem,))
                definition=replace(definition,mana_cost=card.mana_cost)
                game.battlefield[card.id] = EventPermanent(card.id, definition, seat, item.tapped,
                    item.fresh, item.saddled, item.animated, counters=item.counters, token=item.card.is_token,temporary_power=item.temporary_power,
                    temporary_toughness=item.temporary_toughness,temporary_abilities=item.temporary_abilities,attached_to=item.attached_to,
                    entered_at=item.entered_at,attachment_at=item.attachment_at,lost_abilities=dict(item.lost_abilities),
                    temporary_ability_times=dict(item.temporary_ability_times),loyalty=item.loyalty,charge_counters=item.charge_counters,chosen_subtype=item.chosen_subtype,keyword_counters=item.keyword_counters,
                    attacking=(1-seat if self.group_combat and card.id in self.group_combat['attackers'] else None))
        # Equipment's layer-4 type-changing effect acts on the actual equipped
        # permanent, including an otherwise noncreature planeswalker. Rebuild
        # from the original Card definition each time, so detachment restores
        # the original type without changing zone identity.
        for equipment in list(game.battlefield.values()):
            if equipment.definition.equipment_creature_conversion and equipment.attached_to in game.battlefield:
                target=game.battlefield[equipment.attached_to]
                types=(set(target.definition.types)|{'Creature'})-{'Planeswalker'}
                target.definition=replace(target.definition,types=frozenset(types))
        self.apply_land_type_effects(game)
        return game

    def apply_land_type_effects(self,game):
        """Layer-4 basic land types; replacing nonbasic land abilities removes their own effects."""
        from land_type_effects import BASIC_TYPES
        all_sources=[state for state in game.battlefield.values()
                     if state.definition.land_type_effect]
        if not all_sources:return
        items_by_id={item.card.id:item for player in self.players for item in player.battlefield}
        replacements=[state for state in all_sources
                      if state.definition.land_type_effect[:2]==('nonbasic','replace')]
        # A nonbasic land granting land types loses that ability under an active
        # nonbasic type replacement (e.g. Urborg under Blood Moon).
        sources=[state for state in all_sources if not (
            'Land' in state.definition.types and replacements and
            not items_by_id[state.id].card.basic_land)]
        # Continuous effects that set or add basic land types apply in
        # timestamp order, not player/battlefield enumeration order.
        sources.sort(key=lambda source: source.entered_at)
        for state in game.battlefield.values():
            if 'Land' not in state.definition.types:continue
            item=items_by_id[state.id]
            types=set(state.definition.subtypes)
            replaced=False
            for source in sources:
                scope,mode,granted=source.definition.land_type_effect
                if scope=='nonbasic' and item.card.basic_land:continue
                if scope=='controller' and source.controller!=state.controller:continue
                if mode=='replace':
                    types=set(granted);replaced=True
                else:types.update(granted)
            if replaced:
                # A land becoming a basic land type loses its printed abilities;
                # it does not become Basic, and it retains nonland card types.
                original=state.definition
                state.definition=EventDefinition(original.name,original.types,
                    frozenset(types),original.legendary,original.power,original.toughness,
                    frozenset(),colors=original.colors,mana_cost=original.mana_cost)
                state.land_overridden=True
            elif types!=set(state.definition.subtypes):
                state.definition=replace(state.definition,subtypes=frozenset(types))

    def sync_events(self, game: EventGame):
        self.effect_clock=max(self.effect_clock,game.clock)
        for player in self.players:
            for item in player.battlefield:
                state = game.battlefield.get(item.card.id)
                if state:
                    item.attached_to=state.attached_to
                    item.entered_at,item.attachment_at=state.entered_at,state.attachment_at
                    item.loyalty=state.loyalty
                    item.charge_counters=state.charge_counters
                    item.chosen_subtype=state.chosen_subtype
                    item.keyword_counters=state.keyword_counters
                    item.lost_abilities=dict(state.lost_abilities);item.temporary_ability_times=dict(state.temporary_ability_times)
                    item.tapped, item.fresh = state.tapped, state.fresh
                    item.saddled, item.animated, item.counters = state.saddled, state.animated, state.counters
                    item.temporary_power,item.temporary_toughness,item.temporary_abilities=state.temporary_power,state.temporary_toughness,state.temporary_abilities

    def effective_card(self, item: Permanent, game=None) -> Card | None:
        game = game or self.event_game("combat")
        state = game.battlefield.get(item.card.id)
        if not state or not game.creature(state): return None
        power, toughness = game.stats(state)
        keywords = {ability for ability in state.definition.abilities if ability not in ("hexproof","flash") and game.has(state,ability)}
        for ability in ("haste", "indestructible", "flying", "first strike", "double strike",
                        "lifelink", "vigilance", "trample", "defender", "reach", "deathtouch", "menace",
                        "shroud", "fear", "plainswalk", "islandwalk", "swampwalk", "mountainwalk", "forestwalk"):
            if game.has(state, ability): keywords.add(ability)
        return replace(item.card, kind="creature", power=power, toughness=toughness,
                       traits=f"{power};{toughness};"+",".join(sorted(keywords)))

    def land_entry_tapped(self,card,seat,entry_logs):
        player=self.players[seat]
        if not card.basic_land and any(state.definition.land_type_effect[:2]==('nonbasic','replace')
               for state in self.event_game('main').battlefield.values()):
            return False
        if card.land_rule.startswith('reveal_types:'):
            required=set(card.land_rule.split(':',1)[1].split(','))
            chosen=next((c for c in player.hand if c.id!=card.id and required.intersection(c.land_subtypes)),None)
            # Deterministic legal choice: reveal the first matching card, if any.
            if chosen:entry_logs.append(('reveal_land_entry',f'Player {seat+1} reveals {chosen.name}.',dict(actor=seat,card=chosen.name,source=card.name)))
            return chosen is None
        if card.land_rule.startswith('pay_life:'):
            amount=int(card.land_rule.split(':',1)[1])
            # Decline when paying would leave zero life; payment is not damage.
            paid=player.life>amount
            if paid:player.life-=amount
            entry_logs.append(('land_entry_payment',f'Player {seat+1} '+('pays' if paid else 'declines to pay')+f' {amount} life.',dict(actor=seat,amount=amount,paid=paid,source=card.name)))
            return not paid
        game=self.event_game('main')
        lands=[replace(p.card,land_subtypes=tuple(game.battlefield[p.card.id].definition.subtypes))
               for p in player.battlefield if p.card.id in game.battlefield and
               'Land' in game.battlefield[p.card.id].definition.types]
        return land_enters_tapped(card,lands)

    def choose_creature_type(self, controller, definition, game):
        """Deterministic diagnostic choice; future agent policy may override it."""
        counts={}
        for creature in game.battlefield.values():
            if creature.controller!=controller or not game.creature(creature):continue
            for subtype in creature.definition.subtypes:
                counts[subtype]=counts.get(subtype,0)+1
        # Human is a valid creature type when no existing controlled creature offers a choice.
        return min(counts,key=lambda kind:(-counts[kind],kind)) if counts else 'Human'

    def enter_creature(self, card: Card, player: Player, attached_to=None, keyword_counter=None):
        return self.enter_creatures([card],player,attached_targets={card.id:attached_to} if attached_to else None,
                                    keyword_choices={card.id:keyword_counter} if keyword_counter else None)

    def enter_creatures(self, cards, player: Player, bestowed_targets=None, attached_targets=None, keyword_choices=None):
        game=self.event_game('main')
        game._next_token=self.token_sequence
        known=set(game.battlefield)
        controller=next(i for i,candidate in enumerate(self.players) if candidate is player)
        entrants=[];entry_logs=[];chosen_types={}
        keyword_choices=keyword_choices or {}
        bestowed_targets=bestowed_targets or {}
        attached_targets=dict(attached_targets or {},**bestowed_targets)
        for card in cards:
            definition=card.event_definition
            if definition is None:
                definition=EventDefinition(card.name,frozenset(card.printed_types or (('Land',) if card.kind=='land' else ('Creature',))),frozenset(card.land_subtypes),card.legendary,
                    card.power,card.toughness,frozenset(k for k in card.traits.split(';')[-1].split(',') if k),
                    colors=frozenset(card.colors))
            if card.id in bestowed_targets:definition=self.bestowed_definition(definition)
            if ('Land' in definition.types and not card.basic_land and
                    any(state.definition.land_type_effect[:2]==('nonbasic','replace')
                        for state in game.battlefield.values())):
                original=definition
                definition=EventDefinition(original.name,original.types,frozenset({'Mountain'}),
                    original.legendary,original.power,original.toughness,frozenset(),
                    colors=original.colors,mana_cost=original.mana_cost)
            enters_tapped=self.land_entry_tapped(card,controller,entry_logs) if card.kind=='land' else card.enters_tapped
            if definition.chosen_type_entry:
                chosen_types[card.id]=self.choose_creature_type(controller,definition,game)
            keyword_choice=keyword_choices.get(card.id)
            if definition.entry_keyword_choices:
                if keyword_choice is None:keyword_choice=definition.entry_keyword_choices[0]
                if keyword_choice not in definition.entry_keyword_choices:
                    raise ValueError('Illegal keyword counter choice')
            elif keyword_choice is not None:raise ValueError('Card has no keyword counter choice')
            entrants.append(EventPermanent(card.id,replace(definition,mana_cost=card.mana_cost),controller,tapped=enters_tapped,
                                           attached_to=attached_targets.get(card.id),chosen_subtype=chosen_types.get(card.id,''),
                                           keyword_counters=frozenset((keyword_choice,)) if keyword_choice else frozenset()))
        game.life_totals={seat:p.life for seat,p in enumerate(self.players)}
        game.enter_batch(entrants)
        self.entry_history.extend(dict(turn=self.turn,controller=controller,id=p.id,
            subtypes=sorted(p.definition.subtypes)) for p in entrants)
        player.battlefield.extend(Permanent(card,attached_to=attached_targets.get(card.id),bestowed=card.id in bestowed_targets,
                                           chosen_subtype=chosen_types.get(card.id,''),
                                           keyword_counters=next(p.keyword_counters for p in entrants if p.id==card.id)) for card in cards)
        for token_id in game.battlefield.keys()-known-{card.id for card in cards}:
            token_state=game.battlefield[token_id]
            if not token_state.token:raise RuntimeError('Unknown event-created permanent')
            d=token_state.definition
            token=Card(token_id,d.name,'creature',traits=f'{d.power};{d.toughness};'+','.join(sorted(d.abilities)),
                       power=d.power,toughness=d.toughness,event_definition=d,is_token=True)
            player.battlefield.append(Permanent(token))
        self.token_sequence=game._next_token
        self.sync_events(game)
        pending=[event for event in game.events if event['kind']=='trigger']
        # Lore is placed as the Saga enters. Chapter abilities are triggered,
        # not resolved during entry, and Chapter III needs the same stack.
        for entrant in entrants:
            item=next(item for item in player.battlefield if item.card.id==entrant.id)
            if item.card.event_definition and item.card.event_definition.saga_chapter_scale:
                item.lore_counters+=1
                trigger=self.saga_chapter_event(controller,item,item.lore_counters)
                if trigger:pending.append(trigger)
        # Constellation sees the entering enchantment including the source itself.
        # Each watcher/entrant pair produces its own targeted stack trigger.
        for entrant in entrants:
            if 'Enchantment' not in entrant.definition.types:continue
            for controller,owner in enumerate(self.players):
                if controller!=entrant.controller:continue
                for watcher in owner.battlefield:
                    definition=watcher.card.event_definition
                    if not definition or not definition.constellation_counter:continue
                    targets=self.creature_targets(controller,watcher.card)
                    if not targets:continue
                    chosen=min(targets,key=lambda pair:(pair[0]!=controller,pair[1].card.id))
                    pending.append(dict(operation='constellation_counter',effect='target creature gains +1/+1 counter',
                             source=watcher.card.id,controller=controller,name=watcher.card.name,
                             target=chosen[1].card.id,amount=1))
        for kind,message,details in entry_logs:self.log(kind,message,**details)
        return pending

    def saga_chapter_event(self,seat,permanent,chapter):
        program=permanent.card.event_definition.saga_chapter_scale
        if not program:return None
        if chapter>=3:
            return dict(operation='saga_transform',controller=seat,source=permanent.card.id,
                        name=permanent.card.name,chapter=chapter)
        if chapter not in (1,2):return None
        targets=self.creature_targets(seat,permanent.card)
        if not targets:return None
        chosen=min(targets,key=lambda target:(target[0]!=seat,target[1].card.id))
        return dict(operation='saga_chapter_bonus',controller=seat,source=permanent.card.id,
            name=permanent.card.name,chapter=chapter,target=chosen[1].card.id,
            power=program[0],toughness=program[1])

    def advance_sagas_after_draw(self,seat):
        """Sagas add one lore counter after the draw step of their controller."""
        pending=[]
        for item in list(self.players[seat].battlefield):
            if not item.card.event_definition or not item.card.event_definition.saga_chapter_scale:
                continue
            item.lore_counters+=1
            event=self.saga_chapter_event(seat,item,item.lore_counters)
            if event:pending.append((event,item.card))
            self.log('saga_lore','Saga gets a lore counter after its controller draw step.',
                actor=seat,source=item.card.id,lore=item.lore_counters)
        self._waiting_triggers.extend(pending)
        self.resolve_entry_triggers([],Card('saga-draw','Saga draw step','spell'))

    def state_based_actions(self):
        """Collect creature deaths in repeated simultaneous batches before priority."""
        pending=[]
        while True:
            game=self.event_game('main')
            dead=[]
            for owner,player in enumerate(self.players):
                for item in player.battlefield:
                    state=game.battlefield.get(item.card.id)
                    if state is None:continue
                    if 'Planeswalker' in state.definition.types and item.loyalty==0:
                        dead.append((owner,item));continue
                    if not game.creature(state):continue
                    toughness=game.stats(state)[1]
                    if toughness<=0 or (item.marked_damage>0 and item.marked_damage>=toughness
                                        and not game.has(state,'indestructible')):
                        dead.append((owner,item))
            replaced=[]
            for owner,item in dead:
                state=game.battlefield.get(item.card.id)
                if state and game.creature(state) and game.stats(state)[1]>0 and (
                        self.replace_umbra_destruction(owner,item,game) or self.replace_regeneration(owner,item,game)):
                    replaced.append((owner,item))
            if replaced:dead=[entry for entry in dead if entry not in replaced]
            invalid_auras=[];detached=[]
            for owner,player in enumerate(self.players):
                for item in player.battlefield:
                    if item.card.kind not in ('aura','equipment') and not item.bestowed:continue
                    target=game.battlefield.get(item.attached_to)
                    attachment=item.card.event_definition.attachment if item.card.event_definition else ()
                    restriction=attachment[5] if len(attachment)>5 else ''
                    if restriction.startswith('land:'):
                        host=next((h for pl in self.players for h in pl.battlefield
                                   if h.card.id==item.attached_to),None)
                        legal=bool(target and host and 'Land' in target.definition.types
                                   and target.controller==game.battlefield[item.card.id].controller
                                   and (restriction!='land:snow:controller' or host.card.snow)
                                   and (restriction!='land:mountain:controller' or 'Mountain' in target.definition.subtypes)
                                   and not game.protected(target,item.card.colors))
                    else:
                        legal=bool(target and game.creature(target) and not game.protected(target,item.card.colors)
                                   and (restriction!='controller' or
                                        target.controller==game.battlefield[item.card.id].controller))
                    if legal:continue
                    if item.bestowed:detached.append(item)
                    elif item.card.kind=='aura':invalid_auras.append((owner,item))
                    elif item.attached_to:detached.append(item)
            role_groups={}
            for owner,player in enumerate(self.players):
                for item in player.battlefield:
                    if item.attached_to and item.card.event_definition and item.card.event_definition.role:
                        role_groups.setdefault((owner,item.attached_to),[]).append(item)
            for (owner,_),roles in role_groups.items():
                newest=max(roles,key=lambda item:(item.attachment_at,item.entered_at,item.card.id))
                invalid_auras.extend((owner,item) for item in roles if item is not newest and (owner,item) not in invalid_auras)
            if not dead and not invalid_auras and not detached:
                if replaced:continue  # Recompute after the Aura and its bonuses leave.
                break
            for item in detached:item.attached_to=None;item.bestowed=False
            for owner,item in invalid_auras:
                if item in self.players[owner].battlefield:self.send_to_destination(self.players[owner],item,snapshot=game)
            if invalid_auras or detached:
                self.log('state_based_attachments','Illegal creature attachments are removed.',
                    auras=[item.card.id for _,item in invalid_auras],detached=[item.card.id for item in detached])
            # Every watcher sees the same pre-death snapshot, once per batch.
            pending.extend(game.death_triggers([item.card.id for _,item in dead if game.creature(game.battlefield[item.card.id])]))
            for owner,item in dead:
                if item in self.players[owner].battlefield:self.send_to_destination(self.players[owner],item,snapshot=game)
            self.log('state_based_deaths','Creature state-based actions happen simultaneously.',
                     deaths=[item.card.id for _,item in dead])
        return pending

    def resolve_entry_triggers(self, triggers: list[dict], card: Card, priority=None):
        self._waiting_triggers.extend((event,card) for event in triggers)
        if self._resolving_stack:return
        self._waiting_triggers.extend((event,card) for event in self.state_based_actions())
        if not self.finished:self.outcome()
        if self.finished:
            self._waiting_triggers.clear()
            return
        waiting,self._waiting_triggers=self._waiting_triggers,[]
        # All waiting triggers, including later death batches, use one APNAP placement.
        self.stack.active=self.active
        for controller in (self.active,1-self.active):
            for event,origin in reversed([(e,c) for e,c in waiting if e.get('controller',self.active)==controller]):
                if event.get('effect')=='create tapped Squirrels':
                    event=dict(event,operation='create_tokens',tokenSpec=dict(amount=event['amount'],power=1,toughness=1,
                        colors=['Green'],subtypes=['Squirrel'],keywords=[],tapped=True,land=False))
                if event.get('operation')=='return_graveyard':
                    subtype=event.get('libraryFilter',())
                    if len(subtype)!=2 or subtype[0]!='subtype':raise RuntimeError('Malformed graveyard trigger')
                    targets=self.graveyard_subtype_targets(controller,subtype[1])
                    if not targets:continue
                    event=dict(event,target=targets[0].id)
                if event.get('operation')=='damage_any_target':
                    options=self.damage_trigger_targets(event)
                    if not options:continue
                    kind,target=self.choose_damage_target(event,options)
                    if (kind,target) not in options:raise ValueError('Illegal damage trigger target')
                    event=dict(event,targetKind=kind,target=target)
                if event.get('operation')=='combat_target_boost':
                    game=self.event_game('main')
                    candidates=[item for owner,item in self.creature_targets(controller,origin)
                                if owner==controller and item.card.id in game.battlefield
                                and (game.enchanted(game.battlefield[item.card.id]) or
                                     'Enchantment' in game.battlefield[item.card.id].definition.types)]
                    if not candidates:
                        self.log('combat_boost_no_target','No legal enchanted or enchantment creature for combat trigger.',
                                 source=event['source'])
                        continue
                    chosen=max(candidates,key=lambda item:(self.effective_card(item).power,item.card.id))
                    event=dict(event,target=chosen.card.id)
                if event.get('operation')=='exile_until_aura_leaves':
                    # Target is chosen when the ETB trigger is put on the stack,
                    # not when it resolves. Opposing hexproof and protection apply.
                    candidates=[item for owner,item in self.creature_targets(controller,origin)
                                if owner!=controller]
                    if not candidates:continue
                    chosen=max(candidates,key=lambda item:(self.effective_card(item).power,item.card.id))
                    event=dict(event,target=chosen.card.id)
                if event.get('operation')=='linked_exile_entry':
                    candidates=[item for owner,item in self.creature_targets(controller,origin)
                                if event['targetRestriction']!='opponent' or owner!=controller]
                    if not candidates:continue
                    chosen=max(candidates,key=lambda item:(self.effective_card(item).power,item.card.id))
                    event=dict(event,target=chosen.card.id)
                if event.get('operation')=='create_chosen_role':
                    kind=self.choose_role_kind(event,event['roleOptions'])
                    if kind not in event['roleOptions']:
                        raise ValueError('Unknown modal Role choice')
                    event=dict(event,roleChoice=kind)
                if event.get('operation')=='create_role':
                    targets=self.role_targets(event)
                    chosen=next((p for p in targets if p.card.id==event.get('target')),None) if event.get('target') else max(targets,key=lambda p:(self.effective_card(p).power,p.card.id),default=None)
                    if chosen is None:
                        self.log('role_no_target','No legal other creature for the Role trigger.',source=event['source'])
                        continue
                    event=dict(event,target=chosen.card.id)
                item=self.stack.push(controller,(event,origin),event.get('name',origin.name))
                self.log('stack_push',f'{item.label} ability goes on the stack.',stackId=item.id,controller=controller)
                if event.get('operation')=='damage_any_target' and event.get('targetKind')=='permanent':
                    for ward in self.target_triggers(item,event['target']):
                        self.stack.push(ward['controller'],(ward,origin),ward['name'])
        self.stack.priority=self.active if priority is None else priority
        if not self.manual_priority:self.drain_priority()

    def drain_priority(self,empty_window=False):
        if self._draining_priority: return
        self._draining_priority=True
        try:
            while (self.stack.items or empty_window) and not self.finished:
                seat=self.stack.priority
                observation=self.priority_observation(seat)
                choice=self.policies[seat].choose(observation)
                if choice not in observation.legal_actions: raise RuntimeError('Illegal response decision')
                self.decisions.append({'seat':seat,'turn':self.turn,'phase':'priority',
                    'action':choice.kind,'cardId':choice.card_id,'targetStack':choice.target_stack,'targetPermanent':choice.target_permanent,
                    'features':list(choice.features)})
                self.log('priority_choice',choice.label,actor=seat,action=choice.kind,
                         cardId=choice.card_id,targetStack=choice.target_stack,targetPermanent=choice.target_permanent)
                status=self.act_priority(seat,choice)
                if status=='advance': break
        finally: self._draining_priority=False

    def pass_priority(self, actor):
        status,item=self.stack.pass_priority(actor)
        if item and item.payload[0].get('operation')=='spell' and not item.payload[0].get('copy'):
            self._current_spell=(item.controller,item.payload[1])
        self.log('priority_pass',f'Player {actor+1} passes priority.',actor=actor)
        if status=='resolve':
            self.log('stack_resolve',f'{item.label} resolves.',stackId=item.id)
            self._resolving_stack=True
            try:
                if item.payload[0].get('operation')=='spell': self.resolve_spell(item.payload[0],item.payload[1])
                else: self._resolve_entry_effects([item.payload[0]],item.payload[1])
            finally:
                self._resolving_stack=False
                self._current_spell=None
            self.resolve_entry_triggers([],item.payload[1])
            self.stack.priority=self.active
        return status

    def permitted_exile_cards(self,seat):
        result=[]
        for owner in self.players:
            for card in owner.exile:
                permission=self.exile_cast_permissions.get(card.id)
                if not permission or permission[0]!=seat or self.turn>permission[1]:continue
                if 'Creature' not in card.printed_types or permission[2] not in card.land_subtypes:continue
                if card.kind=='creature':result.append(card)
        return result

    def response_choices(self,seat):
        if seat!=self.stack.priority: return ()
        return tuple(c for c in self.players[seat].hand if c.instant and c.kind in ('spell','token_spell','counter_spell','removal_spell','modifier_spell','blink_spell',
            'creature','enchantment','artifact','equipment','vehicle','station','planeswalker')
                     and (not c.draw or c.draw<=len(self.players[seat].library))
                     and self.payment(c,seat=seat)['paid'])

    def color_draw_payment(self,seat,source):
        return self.payment(replace(source.card,mana_cost=source.card.color_draw_cost),seat=seat,
                            spell_cost=False,excluded_sources=(source.card.id,))

    def activate_color_draw(self,seat,source_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        if source is None or source.tapped or not source.card.color_draw_cost:raise ValueError('Illegal color draw')
        game=self.event_game('main');state=game.battlefield.get(source_id)
        if state is None or (game.creature(state) and source.fresh and not game.has(state,'haste')):
            raise ValueError('Tap ability is summoning sick')
        payment=self.color_draw_payment(seat,source)
        if not payment['paid']:raise ValueError('Cannot pay draw cost')
        for item in self.players[seat].battlefield:
            if item.card.id in payment['sources']:item.tapped=True
        self.players[seat].mana_pool=list(payment['pool']);source.tapped=True
        event=dict(operation='draw_by_permanent_colors',controller=seat,source=source_id,name=source.card.name)
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_color_draw','Activate draw per permanent color.',actor=seat,source=source_id,stackId=frame.id,manaSources=payment['sources'])
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def activate_graveyard_exile(self,seat,source_id,target_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        ability=source.card.event_definition.graveyard_exile_activation if source and source.card.event_definition else ()
        if not ability:raise ValueError('No graveyard exile ability')
        targets=[(owner,c) for owner,p in enumerate(self.players) if owner!=seat
                 for c in p.graveyard if c.id==target_id and not c.is_token]
        if len(targets)!=1:raise ValueError('Illegal opponent graveyard target')
        cost,spec=ability
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay activation')
        for item in self.players[seat].battlefield:
            if item.card.id in payment['sources']:item.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        owner,target=targets[0]
        event=dict(operation='exile_graveyard_conditional_token',controller=seat,source=source_id,
                   name=source.card.name,target=target_id,targetZoneOwner=owner,
                   tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords)))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_graveyard_exile','Target an opponent graveyard card.',actor=seat,
                 source=source_id,targetCard=target_id,targetZoneOwner=owner,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def token_ability_choices(self,seat):
        result=[]
        for source in self.players[seat].battlefield:
            ability=source.card.event_definition.graveyard_exile_activation if source.card.event_definition else ()
            if ability:
                cost,_=ability
                payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
                if payment['paid']:
                    for opponent,player in enumerate(self.players):
                        if opponent==seat:continue
                        for target in player.graveyard:
                            if not target.is_token:
                                result.append(Candidate(source.card.id+':exile:'+target.id,
                                    'activate_graveyard_exile',source.card.id,
                                    features=features(power=1,cost=len(payment['sources'])),
                                    label='Exile '+target.name,target_permanent=target.id))
            if source.card.color_draw_cost and not source.tapped:
                game=self.event_game('main');state=game.battlefield.get(source.card.id)
                if state and (not game.creature(state) or not source.fresh or game.has(state,'haste')):
                    payment=self.color_draw_payment(seat,source)
                    if payment['paid']:
                        result.append(Candidate(source.card.id+':color-draw','activate_color_draw',source.card.id,
                            features=features(draw=2,cost=len(payment['sources'])),label='Draw per controlled color'))
            definition=source.card.event_definition
            for index,(cost,spec) in enumerate(definition.activations if definition else ()):
                payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
                if payment['paid']:
                    result.append(Candidate(source.card.id+':activate:'+str(index),'activate_tokens',source.card.id,
                        features=features(power=spec.amount*spec.power,toughness=spec.amount*spec.toughness,
                                          cost=len(payment['sources'])),label='Activate '+source.card.name,activation_index=index))
            if definition and definition.tribal_tap_tokens and not source.tapped:
                game=self.event_game('main');state=game.battlefield.get(source.card.id)
                if state and (not source.fresh or not game.creature(state) or game.has(state,'haste')):
                    spec,subtype=definition.tribal_tap_tokens
                    count=sum(subtype in p.card.event_definition.subtypes for p in self.players[seat].battlefield
                              if p.card.event_definition)
                    result.append(Candidate(source.card.id+':tribal-tap','activate_tribal_tokens',source.card.id,
                        features=features(power=count*spec.power,cost=0),label='Activate '+source.card.name))
        return result

    def sacrifice_choices(self,seat):
        game=self.event_game('main');choices=[]
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            if not definition or not definition.sacrifice_ability:continue
            operation,subtype,*parameters=definition.sacrifice_ability
            for victim in self.players[seat].battlefield:
                state=game.battlefield.get(victim.card.id)
                if state is None or not game.creature(state) or subtype not in state.definition.subtypes:continue
                if operation=='mana':
                    choices.append(Candidate(source.card.id+':sacrifice:'+victim.card.id,'activate_sacrifice_mana',
                        source.card.id,features=features(power=.05,cost=1),label='Sacrifice '+victim.card.name+
                        ' for '+source.card.name,tap_ids=(victim.card.id,)))
                elif operation=='boost':
                    for _,target in self.creature_targets(seat,source.card):
                        choices.append(Candidate(source.card.id+':sacrifice:'+victim.card.id+':target:'+target.card.id,
                            'activate_sacrifice_boost',source.card.id,
                            features=features(power=.3,cost=1),label='Sacrifice '+victim.card.name+
                            ' to boost '+target.card.name,tap_ids=(victim.card.id,),
                            target_permanent=target.card.id))
        return choices

    def discard_token_choices(self,seat):
        """A discard is a paid cost; only cards in this player's own hand are choices."""
        choices=[];player=self.players[seat]
        for source in player.battlefield:
            ability=source.card.event_definition.discard_token_ability if source.card.event_definition else ()
            if not ability or not player.hand:continue
            cost,spec=ability
            payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
            if not payment['paid']:continue
            for discarded in player.hand:
                choices.append(Candidate(source.card.id+':discard:'+discarded.id,'activate_discard_tokens',
                    source.card.id,features=features(power=spec.amount*max(1,spec.power)/4,cost=1+len(payment['sources'])),
                    label='Discard '+discarded.name+' to activate '+source.card.name,discard_id=discarded.id))
        return choices

    def activate_discard_tokens(self,seat,source_id,discard_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        player=self.players[seat]
        source=next((p for p in player.battlefield if p.card.id==source_id),None)
        ability=source.card.event_definition.discard_token_ability if source and source.card.event_definition else ()
        discarded=next((c for c in player.hand if c.id==discard_id),None)
        if not ability or discarded is None:raise ValueError('Missing activation or discard-cost card')
        cost,spec=ability
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay mana for discard-token activation')
        for permanent in player.battlefield:
            if permanent.card.id in payment['sources']:permanent.tapped=True
        player.mana_pool=list(payment['pool'])
        player.hand.remove(discarded);player.graveyard.append(discarded)
        event=dict(operation='create_tokens',effect='discard-cost token creation',source=source_id,
                   controller=seat,name=source.card.name,tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords)))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_discard_tokens','Mana and one discarded card are paid before token creation.',
                 actor=seat,source=source_id,discarded=discarded.name,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def sacrifice_protection_choices(self,seat):
        game=self.event_game('main');choices=[]
        for source in self.players[seat].battlefield:
            ability=source.card.event_definition.sacrifice_protection if source.card.event_definition else ()
            if not ability or not self.payment(replace(source.card,mana_cost=ability[0]),seat=seat,spell_cost=False)['paid']:
                continue
            for target in game.battlefield.values():
                if target.controller!=seat or not set(ability[1]).intersection(target.definition.types):continue
                if game.has(target,'shroud') or game.protected(target,source.card.colors):continue
                for color in range(5):
                    choices.append(Candidate(source.card.id+':protect:'+target.id+':'+str(color),
                        'activate_sacrifice_protection',source.card.id,
                        features=features(power=.1,cost=1),label='Protect '+target.definition.name,
                        target_permanent=target.id,x_value=color))
        return choices

    def activate_sacrifice_protection(self,seat,source_id,target_id,color):
        if self.stack.priority!=seat or color not in ('White','Blue','Black','Red','Green'):
            raise ValueError('Illegal chosen protection color')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        ability=source.card.event_definition.sacrifice_protection if source and source.card.event_definition else ()
        if not ability:raise ValueError('No sacrifice-for-protection ability')
        game=self.event_game('main');target=game.battlefield.get(target_id)
        if not target or target.controller!=seat or not set(ability[1]).intersection(target.definition.types):
            raise ValueError('Illegal protection target')
        if game.has(target,'shroud') or game.protected(target,source.card.colors):
            raise ValueError('Protected or shrouded target')
        payment=self.payment(replace(source.card,mana_cost=ability[0]),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay protection activation')
        for permanent in self.players[seat].battlefield:
            if permanent.card.id in payment['sources']:permanent.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        triggers=game.death_triggers([source_id])
        if source.card.is_token:triggers.extend(game.token_action_events('sacrifice',seat,1))
        self.send_to_destination(self.players[seat],source,snapshot=game)
        event=dict(operation='sacrifice_protection',effect='grant protection from chosen color',
                   source=source_id,controller=seat,name=source.card.name,target=target_id,
                   color=color,targetTypes=ability[1],sourceColors=list(source.card.colors))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_sacrifice_protection','Mana and self-sacrifice costs are paid before resolution.',
                 actor=seat,source=source_id,targetPermanent=target_id,color=color,stackId=frame.id)
        self.resolve_entry_triggers(triggers,source.card)

    def sacrifice_team_choices(self,seat):
        return [Candidate(item.card.id+':sacrifice-team','activate_sacrifice_team',item.card.id,
                    features=features(power=.2,cost=1),label='Sacrifice '+item.card.name+' for a team boost')
                for item in self.players[seat].battlefield if item.card.event_definition
                and item.card.event_definition.sacrifice_team_boost]

    def activate_sacrifice_team_boost(self,seat,source_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((item for item in self.players[seat].battlefield if item.card.id==source_id),None)
        ability=source.card.event_definition.sacrifice_team_boost if source and source.card.event_definition else ()
        if not ability:raise ValueError('No self-sacrifice team ability')
        game=self.event_game('main');state=game.battlefield.get(source_id)
        if not state or 'Enchantment' not in state.definition.types:raise ValueError('Invalid sacrifice source')
        triggers=game.death_triggers([source_id]) if game.creature(state) else []
        if source.card.is_token:triggers.extend(game.token_action_events('sacrifice',seat,1))
        self.send_to_destination(self.players[seat],source,snapshot=game)
        event=dict(operation='sacrifice_team_boost',effect='team temporary power and toughness',
                   source=source_id,controller=seat,name=source.card.name,power=ability[0],toughness=ability[1])
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_sacrifice_team','Enchantment is sacrificed as the activation cost.',
                 actor=seat,source=source_id,stackId=frame.id)
        self.resolve_entry_triggers(triggers,source.card)

    def choose_forced_sacrifice(self, affected_seat, creatures):
        # The affected player chooses, not the controller of the spell.
        # This is a deterministic diagnostic policy over legally available creatures.
        return min(creatures,key=lambda item:(self.effective_card(item).power,item.card.id))

    def force_opponent_sacrifice(self, source_controller, affected_seat, source):
        game=self.event_game('main')
        if source_controller!=affected_seat and any(
                state.controller==affected_seat and state.definition.prevents_opponent_sacrifice
                for state in game.battlefield.values()):
            self.log('sacrifice_prevented','An opposing spell or ability cannot force a sacrifice.',
                     actor=affected_seat,source=source.name)
            return False
        options=[item for item in self.players[affected_seat].battlefield
                 if item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])]
        if not options:return False
        victim=self.choose_forced_sacrifice(affected_seat,options)
        if victim not in options:raise ValueError('Illegal forced-sacrifice choice')
        triggers=game.death_triggers([victim.card.id])
        if victim.card.is_token:triggers.extend(game.token_action_events('sacrifice',affected_seat,1))
        self.send_to_destination(self.players[affected_seat],victim,snapshot=game)
        self.log('forced_sacrifice','Affected player sacrifices one creature for an opposing effect.',
                 actor=affected_seat,source=source.name,permanent=victim.card.id)
        self.resolve_entry_triggers(triggers,source)
        return True

    def _pay_sacrifice_creature(self,seat,victim):
        # Cost is paid before the ability resolves, regardless of whether its
        # source survives. Indestructible does not prevent sacrifice.
        game=self.event_game('main');state=game.battlefield.get(victim.card.id)
        if state is None or state.controller!=seat or not game.creature(state):
            raise ValueError('Sacrifice cost requires a controlled creature')
        events=game.death_triggers([victim.card.id])
        if victim.card.is_token:events.extend(game.token_action_events('sacrifice',seat,1))
        self.send_to_destination(self.players[seat],victim,snapshot=game)
        self.log('sacrifice_cost','A creature is sacrificed as an activated ability cost.',
                 actor=seat,permanent=victim.card.id)
        return events

    def activate_sacrifice_mana(self,seat,source_id,victim_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        definition=source.card.event_definition if source else None
        ability=definition.sacrifice_ability if definition else ()
        if not ability or ability[0]!='mana':raise ValueError('Illegal sacrifice mana ability')
        victim=next((p for p in self.players[seat].battlefield if p.card.id==victim_id),None)
        game=self.event_game('main');state=game.battlefield.get(victim_id)
        if victim is None or state is None or not game.creature(state) or ability[1] not in state.definition.subtypes:
            raise ValueError('Sacrifice cost requires a matching creature')
        triggers=self._pay_sacrifice_creature(seat,victim)
        color=mana_pool.COLORS.index(ability[2]);self.players[seat].mana_pool[color]+=1
        self.log('sacrifice_mana','Sacrifice mana ability resolves without using the stack.',
                 actor=seat,source=source_id,color=ability[2],victim=victim_id)
        self.resolve_entry_triggers(triggers,source.card)

    def activate_sacrifice_boost(self,seat,source_id,victim_id,target_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        ability=source.card.event_definition.sacrifice_ability if source and source.card.event_definition else ()
        if not ability or ability[0]!='boost':raise ValueError('Illegal sacrifice boost ability')
        victim=next((p for p in self.players[seat].battlefield if p.card.id==victim_id),None)
        game=self.event_game('main');state=game.battlefield.get(victim_id)
        if victim is None or state is None or not game.creature(state) or ability[1] not in state.definition.subtypes:
            raise ValueError('Sacrifice cost requires a matching creature')
        if target_id not in {p.card.id for _,p in self.creature_targets(seat,source.card)}:
            raise ValueError('Illegal sacrifice boost target')
        triggers=self._pay_sacrifice_creature(seat,victim)
        event=dict(operation='sacrifice_target_boost',effect='temporary target creature boost',
                   source=source_id,controller=seat,name=source.card.name,target=target_id,
                   power=ability[2],toughness=ability[3],sourceColors=tuple(source.card.colors))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.log('activate_sacrifice_boost','Creature sacrificed to activate a targeted temporary boost.',
                 actor=seat,source=source_id,target=target_id,victim=victim_id,stackId=frame.id)
        for ward in self.target_triggers(frame,target_id):
            self.stack.push(ward['controller'],(ward,source.card),ward['name'])
        self.resolve_entry_triggers(triggers,source.card)

    def regeneration_targets(self,seat,source):
        subtype=source.card.event_definition.regenerate_subtype
        game=self.event_game('main')
        return tuple((owner,item) for owner,item in self.creature_targets(seat,source.card)
                     if item.card.id!=source.card.id and
                     subtype in game.battlefield[item.card.id].definition.subtypes)

    def regenerate_choices(self,seat):
        if self.stack.priority!=seat:return []
        game=self.event_game('main');choices=[]
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            if not definition or not definition.regenerate_subtype or source.tapped:continue
            state=game.battlefield.get(source.card.id)
            if source.fresh and not (state and game.has(state,'haste')):continue
            for owner,target in self.regeneration_targets(seat,source):
                choices.append(Candidate(source.card.id+':regen:'+target.card.id,
                    'activate_regenerate',source.card.id,features=features(power=.2),
                    label='Regenerate '+target.card.name,target_permanent=target.card.id))
        return choices

    def activate_regenerate(self,seat,source_id,target_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        if source is None or source.tapped or not source.card.event_definition or not source.card.event_definition.regenerate_subtype:
            raise ValueError('Illegal regeneration source')
        game=self.event_game('main');state=game.battlefield.get(source_id)
        if source.fresh and not (state and game.has(state,'haste')):raise ValueError('Summoning sick regeneration source')
        if target_id not in {p.card.id for _,p in self.regeneration_targets(seat,source)}:
            raise ValueError('Illegal regeneration target')
        source.tapped=True
        event=dict(operation='regenerate_shield',controller=seat,source=source_id,
                   target=target_id,name=source.card.name,subtype=source.card.event_definition.regenerate_subtype,
                   sourceColors=sorted(source.card.colors))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' regeneration ability')
        self.log('activate_regenerate','Regeneration tap cost paid; ability waits on stack.',
                 actor=seat,source=source_id,targetPermanent=target_id,stackId=frame.id)
        self.resolve_entry_triggers([],source.card)

    def replace_regeneration(self,owner,item,game):
        state=game.battlefield.get(item.card.id)
        if (item not in self.players[owner].battlefield or not state or
                not game.creature(state) or game.stats(state)[1]<=0 or
                game.has(state,'indestructible') or item.regeneration_shields<=0):return False
        item.regeneration_shields-=1;item.marked_damage=0;item.tapped=True
        if self.group_combat:
            combat=self.group_combat
            if item.card.id in combat['attackers']:
                combat['attackers'].remove(item.card.id)
            for blockers in combat['blocks'].values():
                if item.card.id in blockers:blockers.remove(item.card.id)
        if self.combat_context and item.card.id in (self.combat_context['attacker'],self.combat_context['blocker']):
            self.combat_context['blocked']=True
        self.log('regenerate','Regeneration replaces destruction, taps and removes creature from combat.',
                 targetPermanent=item.card.id,remainingShields=item.regeneration_shields)
        return True

    def land_counter_target(self,target,scope):
        if scope=='all':return True
        if not scope.startswith('entered:'):return False
        color=scope.split(':',1)[1]
        return color in target.definition.colors and any(
            e['turn']==self.turn and e.get('id')==target.id for e in self.entry_history)

    def land_counter_choices(self,seat):
        choices=[];player=self.players[seat]
        game=self.event_game('main')
        for source in player.battlefield:
            definition=source.card.event_definition
            if source.tapped or not definition or not definition.land_counter_ability or (
                    source.card.id in game.battlefield and getattr(game.battlefield[source.card.id],'land_overridden',False)):continue
            # The land's tap is a separate cost; it cannot also pay the mana.
            options=[entry for entry in self.mana_sources(seat) if entry[0]!=source.card.id]
            payment=mana_pool.plan(definition.land_counter_ability,player.mana_pool,options)
            if not payment['paid']:continue
            game=self.event_game('main')
            count=sum(p.controller==seat and game.creature(p) and
                      self.land_counter_target(p,definition.land_counter_scope) for p in game.battlefield.values())
            choices.append(Candidate(source.card.id+':team-counters','activate_land_counters',source.card.id,
                features=features(power=count,cost=len(payment['sources'])),
                label='Activate '+source.card.name+' to strengthen your creatures'))
        return choices

    def activate_land_counters(self,seat,source_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        player=self.players[seat]
        source=next((p for p in player.battlefield if p.card.id==source_id),None)
        definition=source.card.event_definition if source else None
        state=self.event_game('main').battlefield.get(source_id)
        if not definition or not definition.land_counter_ability or source.tapped or (
                state and getattr(state,'land_overridden',False)):
            raise ValueError('Illegal land counter activation')
        payment=mana_pool.plan(definition.land_counter_ability,player.mana_pool,
                               [entry for entry in self.mana_sources(seat) if entry[0]!=source_id])
        if not payment['paid']:raise ValueError('Cannot pay land counter activation')
        for permanent in player.battlefield:
            if permanent.card.id in payment['sources']:permanent.tapped=True
        player.mana_pool=list(payment['pool']);source.tapped=True
        event=dict(operation='land_team_counters',effect='put counters on controlled creatures',
                   source=source_id,controller=seat,name=source.card.name,
                   scope=definition.land_counter_scope)
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.log('activate_land_counters','Land activation pays mana and taps the source.',
                 actor=seat,source=source_id,manaSources=payment['sources'],stackId=frame.id)
        self.resolve_entry_triggers([],source.card)

    def land_animation_choices(self,seat):
        game=self.event_game('main')
        choices=[]
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            if not definition or not definition.animate_land_ability:continue
            cost,subtype,count_type=definition.animate_land_ability
            if not self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)['paid']:
                continue
            for land in self.players[seat].battlefield:
                state=game.battlefield.get(land.card.id)
                if not state or 'Land' not in state.definition.types or game.has(state,'shroud') or game.protected(state,source.card.colors):
                    continue
                choices.append(Candidate(source.card.id+':animate:'+land.card.id,'activate_land_animation',
                    source.card.id,features=features(power=2),label='Animate '+land.card.name,
                    target_permanent=land.card.id))
        return choices

    def activate_land_animation(self,seat,source_id,land_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        ability=source.card.event_definition.animate_land_ability if source and source.card.event_definition else ()
        if not ability:raise ValueError('No land-animation ability')
        game=self.event_game('main')
        target=game.battlefield.get(land_id)
        if not target or target.controller!=seat or 'Land' not in target.definition.types or game.has(target,'shroud') or game.protected(target,source.card.colors):
            raise ValueError('Land animation requires a legal controlled land')
        cost,subtype,count_type=ability
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay land-animation activation')
        for item in self.players[seat].battlefield:
            if item.card.id in payment['sources']:item.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        event=dict(operation='animate_land',source=source_id,name=source.card.name,controller=seat,
                   target=land_id,subtype=subtype,countType=count_type,
                   sourceColors=sorted(source.card.colors))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' land-animation ability')
        self.log('activate_land_animation','Mana paid; target chosen before stack resolution.',
                 actor=seat,source=source_id,target=land_id,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def scaled_mana_choices(self,seat):
        choices=[]
        game=self.event_game('main')
        sources=dict(self.mana_sources(seat))
        for item in self.players[seat].battlefield:
            definition=item.card.event_definition
            if not definition or not definition.scaled_mana_tap or item.card.id not in sources or (
                    item.card.id in game.battlefield and getattr(game.battlefield[item.card.id],'land_overridden',False)):continue
            for color in range(5):
                choices.append(Candidate(item.card.id+':mana:'+str(color),'activate_scaled_mana',item.card.id,
                    features=features(power=.1),label='Tap '+item.card.name+' for '+mana_pool.COLORS[color],x_value=color))
        return choices

    def activate_scaled_mana(self,seat,source_id,color):
        if self.stack.priority!=seat or type(color) is not int or not 0<=color<5:
            raise ValueError('Illegal mana ability choice')
        sources=dict(self.mana_sources(seat))
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        state=self.event_game('main').battlefield.get(source_id)
        if not source or not source.card.event_definition or not source.card.event_definition.scaled_mana_tap or source_id not in sources or (
                state and getattr(state,'land_overridden',False)):
            raise ValueError('Illegal mana ability source')
        amount=sources[source_id][color][color]
        source.tapped=True
        self.players[seat].mana_pool[color]+=amount
        self.log('activate_scaled_mana','Player taps a permanent for one chosen color of scaled mana.',
                 actor=seat,source=source_id,color=mana_pool.COLORS[color],amount=amount)

    def activate_tribal_tokens(self,seat,source_id):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        definition=source.card.event_definition if source else None
        if not definition or not definition.tribal_tap_tokens or source.tapped:
            raise ValueError('Illegal tribal token activation')
        game=self.event_game('main');state=game.battlefield.get(source_id)
        if state is None or (source.fresh and game.creature(state) and not game.has(state,'haste')):
            raise ValueError('Tap ability is summoning sick')
        spec,subtype=definition.tribal_tap_tokens
        source.tapped=True
        event=dict(operation='tribal_tap_tokens',effect='create counted tokens',source=source_id,
                   controller=seat,name=source.card.name,subtype=subtype,
                   tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords)))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_tribal_tokens','Player activates a tap-for-tribal-tokens ability.',
                 actor=seat,source=source_id,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def activate_tokens(self,seat,source_id,index=0):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        activations=source.card.event_definition.activations if source and source.card.event_definition else ()
        if not 0<=index<len(activations):raise ValueError('Illegal activated ability')
        cost,spec=activations[index]
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay activated ability')
        for permanent in self.players[seat].battlefield:
            if permanent.card.id in payment['sources']:permanent.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        event=dict(operation='create_tokens',effect='create tokens',source=source_id,controller=seat,
                   name=source.card.name,tokenSpec=dict(asdict(spec),keywords=sorted(spec.keywords)))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_tokens',f'Player {seat+1} activates {source.card.name}.',actor=seat,stackId=frame.id,
                 manaSources=payment['sources'],manaPool=list(self.players[seat].mana_pool))
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def strip_ability_choices(self,seat):
        game=self.event_game('main');choices=[]
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            for index,(cost,abilities) in enumerate(definition.ability_removals if definition else ()):
                payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
                if not payment['paid']:continue
                count=sum(p.controller!=seat and any(game.has(p,a) for a in abilities) for p in game.battlefield.values())
                queued=any(frame.controller==seat and frame.payload[0].get('operation')=='lose_abilities'
                           and set(frame.payload[0]['abilities'])>=abilities for frame in self.stack.items)
                choices.append(Candidate(source.card.id+':strip:'+str(index),'activate_strip',source.card.id,
                    features=features(power=count if count and not queued else -100,cost=len(payment['sources'])),
                    label='Activate '+source.card.name+' ability removal',activation_index=index))
        return choices

    def activate_strip(self,seat,source_id,index=0):
        if self.stack.priority!=seat:raise ValueError('Player lacks priority')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id),None)
        removals=source.card.event_definition.ability_removals if source and source.card.event_definition else ()
        if not 0<=index<len(removals):raise ValueError('Illegal ability removal')
        cost,abilities=removals[index];payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay ability removal')
        for permanent in self.players[seat].battlefield:
            if permanent.card.id in payment['sources']:permanent.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        event=dict(operation='lose_abilities',effect='temporary opposing ability loss',source=source_id,
                   controller=seat,name=source.card.name,abilities=sorted(abilities))
        frame=self.stack.push(seat,(event,source.card),source.card.name+' activated ability')
        self.stack.priority=seat
        self.log('activate_strip',f'Player {seat+1} activates {source.card.name}.',actor=seat,
                 stackId=frame.id,manaSources=payment['sources'],manaPool=list(self.players[seat].mana_pool))
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def choose_optional_enchantment_copy(self,event,enchantment):
        return True

    def choose_optional_combat_reattach(self,event):
        return True

    def combat_reattach_triggers(self):
        """Optional beginning-of-each-combat attach targeting, once per source."""
        game=self.event_game('combat');result=[]
        for controller,player in enumerate(self.players):
            for source in player.battlefield:
                if not source.card.event_definition or not source.card.event_definition.combat_reattach:
                    continue
                attachments=sorted((item for item in player.battlefield
                    if item.card.kind in ('aura','equipment') and item.attached_to
                    and item.card.id in game.battlefield and item.attached_to in game.battlefield
                    and game.creature(game.battlefield[item.attached_to])
                    and game.battlefield[item.attached_to].controller==controller),
                    key=lambda item:item.card.id)
                for attachment in attachments:
                    available=(self.aura_targets(controller,attachment.card)
                        if attachment.card.kind=='aura' else
                        self.creature_targets(controller,attachment.card))
                    choices=sorted(p.card.id for seat,p in available if seat==controller
                                   and p.card.id!=attachment.attached_to)
                    if choices:
                        result.append((dict(operation='combat_reattach',
                            source=source.card.id,controller=controller,name=source.card.name,
                            attachment=attachment.card.id,target=choices[0],
                            effect='may reattach Aura or Equipment'),source.card))
                        break
        return result

    def enchantment_copy_targets(self,seat):
        """Target nonmana abilities from enchantment sources controlled on the stack."""
        targets=[]
        for frame in self.stack.items:
            event,origin=frame.payload
            if frame.controller!=seat or event.get('operation') in (
                    'spell','add_mana','mana','produce_mana','copy_enchantment_ability'):
                continue
            source_id=event.get('source')
            source=next((permanent for player in self.players for permanent in player.battlefield
                         if permanent.card.id==source_id),None)
            is_enchantment=(source is not None and source.card.event_definition is not None
                             and 'Enchantment' in source.card.event_definition.types)
            if not is_enchantment and origin.id==source_id:
                is_enchantment=bool(origin.event_definition and
                                    'Enchantment' in origin.event_definition.types)
            if is_enchantment:targets.append(frame)
        return tuple(targets)

    def enchantment_copy_choices(self,seat):
        if seat!=self.stack.priority:return []
        targets=self.enchantment_copy_targets(seat)
        if not targets:return []
        choices=[]
        for item in self.players[seat].battlefield:
            program=item.card.event_definition
            if item.tapped or not program or not program.enchantment_copy_cost:continue
            cost=program.enchantment_copy_cost
            if not self.payment(replace(item.card,mana_cost=cost),seat=seat,
                                spell_cost=False,excluded_sources=(item.card.id,))['paid']:continue
            for target in targets:
                choices.append(Candidate(item.card.id+':copy:'+str(target.id),
                         'copy_enchantment_ability',item.card.id,
                         features=features(power=.3,cost=1),
                         label='Copy '+target.label,target_stack=target.id))
        return choices

    def activate_enchantment_copy(self,seat,source_id,target_stack):
        if seat!=self.stack.priority:raise ValueError('Player lacks priority')
        source=next((item for item in self.players[seat].battlefield
                     if item.card.id==source_id),None)
        if not source or source.tapped or not source.card.event_definition or (
                not source.card.event_definition.enchantment_copy_cost):
            raise ValueError('Source has no ready ability copier')
        if target_stack not in {frame.id for frame in self.enchantment_copy_targets(seat)}:
            raise ValueError('Target must be your enchantment-sourced stack ability')
        cost=source.card.event_definition.enchantment_copy_cost
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,
                             spell_cost=False,excluded_sources=(source_id,))
        if not payment['paid']:raise ValueError('Cannot pay ability-copy cost')
        for item in self.players[seat].battlefield:
            if item.card.id in payment['sources']:item.tapped=True
        source.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        ability=dict(operation='copy_enchantment_ability',controller=seat,
                     source=source_id,name=source.card.name,targetStack=target_stack)
        frame=self.stack.push(seat,(ability,source.card),source.card.name+' ability copy')
        self.stack.priority=seat
        self.log('copy_activate','Paid and tapped to target an enchantment ability.',
                 actor=seat,source=source_id,targetStack=target_stack,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def class_level_choices(self,seat):
        if seat!=self.active or self.stack.items or self.stack.priority!=seat or (
                self.phase not in ('main','second_main')):return []
        result=[]
        for item in self.players[seat].battlefield:
            program=item.card.event_definition.class_program if item.card.event_definition else ()
            if not program or item.class_level>=3:continue
            cost=program[1] if item.class_level==1 else program[4]
            if self.payment(replace(item.card,mana_cost=cost),seat=seat,spell_cost=False)['paid']:
                result.append(Candidate(item.card.id+':level'+str(item.class_level+1),
                    'activate_class_level',item.card.id,
                    features=features(power=1,cost=len(self.payment(replace(item.card,mana_cost=cost),
                                             seat=seat,spell_cost=False)['sources'])),
                    label='Level '+str(item.class_level+1)+' '+item.card.name))
        return result

    def activate_class_level(self,seat,source_id):
        if seat!=self.active or self.phase not in ('main','second_main') or (
                self.stack.items or self.stack.priority!=seat):
            raise ValueError('Class level ability only as a sorcery')
        source=next((item for item in self.players[seat].battlefield
                    if item.card.id==source_id),None)
        program=source.card.event_definition.class_program if source and source.card.event_definition else ()
        if not program or source.class_level>=3:raise ValueError('Class cannot advance')
        cost=program[1] if source.class_level==1 else program[4]
        paid=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not paid['paid']:raise ValueError('Cannot pay class level cost')
        for item in self.players[seat].battlefield:
            if item.card.id in paid['sources']:item.tapped=True
        self.players[seat].mana_pool=list(paid['pool'])
        next_level=source.class_level+1
        ability=dict(operation='class_level_up',source=source_id,controller=seat,
                     name=source.card.name,expected=source.class_level,nextLevel=next_level)
        frame=self.stack.push(seat,(ability,source.card),source.card.name+' level '+str(next_level))
        self.stack.priority=seat
        self.log('activate_class','Class level ability was paid and put on stack.',
                 actor=seat,source=source_id,nextLevel=next_level,stackId=frame.id)
        if not self.manual_priority and not self._resolving_stack:self.drain_priority()

    def equip_choices(self,seat):
        choices=[]
        game=self.event_game('main')
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            if source.card.kind!='equipment' or not definition or not definition.attachment:continue
            cost=definition.attachment[1]
            if self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)['paid']:
                for owner,target in self.creature_targets(seat,source.card):
                    if owner==seat and source.attached_to!=target.card.id:
                        choices.append(Candidate(source.card.id+':equip:'+target.card.id,'equip',source.card.id,
                            features=features(power=.5),label='Equip '+source.card.name,target_permanent=target.card.id))
            alternate=definition.equipment_planeswalker_cost
            if not alternate or not self.payment(replace(source.card,mana_cost=alternate),
                                                 seat=seat,spell_cost=False)['paid']:continue
            for target in self.players[seat].battlefield:
                state=game.battlefield.get(target.card.id)
                if state and 'Planeswalker' in state.definition.types and (
                        target.card.id!=source.attached_to and not game.has(state,'shroud')
                        and not game.protected(state,source.card.colors)):
                    choices.append(Candidate(source.card.id+':equip-pw:'+target.card.id,
                        'equip_planeswalker',source.card.id,features=features(power=.5),
                        label='Equip planeswalker '+source.card.name,target_permanent=target.card.id))
        return choices

    def activate_equip(self,seat,source_id,target,planeswalker=False):
        if self.stack.items or self.stack.priority!=seat or seat!=self.active or self.phase not in ('main','second_main'):
            raise ValueError('Illegal equip timing')
        source=next((p for p in self.players[seat].battlefield
                     if p.card.id==source_id and p.card.kind=='equipment'),None)
        if source is None or not source.card.event_definition:raise ValueError('Illegal equip source')
        game=self.event_game('main')
        if planeswalker:
            candidate=game.battlefield.get(target)
            eligible=bool(candidate and candidate.controller==seat and
                          'Planeswalker' in candidate.definition.types and
                          not game.has(candidate,'shroud') and
                          not game.protected(candidate,source.card.colors))
            cost=source.card.event_definition.equipment_planeswalker_cost
        else:
            eligible=target in {p.card.id for owner,p in self.creature_targets(seat,source.card) if owner==seat}
            cost=source.card.event_definition.attachment[1]
        if not eligible or not cost or source.attached_to==target:raise ValueError('Illegal equip target')
        payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay equip')
        for p in self.players[seat].battlefield:
            if p.card.id in payment['sources']:p.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        self.resolve_entry_triggers([dict(operation='attach',source=source_id,target=target,
                              controller=seat,name=source.card.name,
                              equipTargetType='planeswalker' if planeswalker else 'creature')],source.card)

    def creature_targets(self,controller=None,source=None):
        game=self.event_game('main')
        return tuple((seat,item) for seat,player in enumerate(self.players) for item in player.battlefield
                     if item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])
                     and not game.has(game.battlefield[item.card.id],'shroud')
                     and (controller is None or seat==controller or not game.has(game.battlefield[item.card.id],'hexproof'))
                     and (source is None or not game.protected(game.battlefield[item.card.id],source.colors))
                     and (source is None or source.kind!='aura' or not source.event_definition
                          or len(source.event_definition.attachment)<6
                          or source.event_definition.attachment[5]!='controller'
                          or game.battlefield[item.card.id].controller==controller))

    def aura_targets(self,controller,source):
        """Land Auras target eligible lands; shroud and hexproof only affect targeting."""
        attachment=source.event_definition.attachment if source.event_definition else ()
        restriction=attachment[5] if len(attachment)>5 else ''
        if not restriction.startswith('land:'):
            return self.creature_targets(controller,source)
        game=self.event_game('main')
        return tuple((seat,item) for seat,player in enumerate(self.players)
                     for item in player.battlefield
                     if item.card.id in game.battlefield
                     and 'Land' in game.battlefield[item.card.id].definition.types
                     and seat==controller
                     and (restriction!='land:snow:controller' or item.card.snow)
                     and (restriction!='land:mountain:controller'
                          or 'Mountain' in game.battlefield[item.card.id].definition.subtypes)
                     and not game.has(game.battlefield[item.card.id],'shroud')
                     and not game.protected(game.battlefield[item.card.id],source.colors))

    def damage_trigger_targets(self,event):
        """Legal any-target choices: players, creatures and planeswalkers in this sandbox."""
        game=self.event_game('main')
        options=[('player',seat) for seat in range(len(self.players))]
        for seat,player in enumerate(self.players):
            for item in player.battlefield:
                state=game.battlefield.get(item.card.id)
                if not state or not (game.creature(state) or 'Planeswalker' in state.definition.types):continue
                if game.has(state,'shroud') or seat!=event['controller'] and game.has(state,'hexproof'):continue
                if game.protected(state,event.get('sourceColors',())):continue
                options.append(('permanent',item.card.id))
        return tuple(options)

    def choose_damage_target(self,event,options):
        """Deterministic diagnostic policy, overridable by a future agent."""
        opponent=('player',1-event['controller'])
        return opponent if opponent in options else options[0]

    def choose_optional_damage(self,event):
        return True

    def graveyard_subtype_targets(self,seat,subtype):
        """Target the owner's public graveyard; never peek at other hidden zones."""
        return tuple(c for c in self.players[seat].graveyard
                     if subtype in (c.event_definition.subtypes if c.event_definition else c.land_subtypes))

    def choose_optional_self_counter(self,event):
        """Optional choice made at resolution, never by treating 'may' as mandatory."""
        return True

    def choose_optional_graveyard_return(self,seat,subtype,targets):
        """Deterministic acceptance at resolution; can be replaced by a policy."""
        return bool(targets)

    def controlled_land_count(self, seat):
        return sum(item.card.kind=='land' or
                   (item.card.event_definition is not None and
                    'Land' in item.card.event_definition.types)
                   for item in self.players[seat].battlefield)

    def choose_modal_attack_mode(self, source_id, specs, declared_attackers):
        # A deterministic legal policy chooses at trigger placement. Both
        # modes stay available even if their eventual X would be zero.
        return 1 if len(declared_attackers)>2 else 0

    def life_counter_targets(self, controller, source_id, source_colors):
        game=self.event_game('main')
        return [target for target in game.battlefield.values()
                if target.id!=source_id and game.creature(target)
                and not game.has(target,'shroud')
                and (target.controller==controller or not game.has(target,'hexproof'))
                and not game.protected(target,source_colors)]

    def choose_life_counter_distribution(self, event, targets):
        # Human/AI may override this deterministic heuristic at trigger placement.
        own=[target for target in targets if target.controller==event['controller']]
        if not own:return {}
        best=max(own,key=lambda target:(self.event_game('main').stats(target)[0],target.id))
        return {best.id:event['maximum']}

    def queue_life_counter_triggers(self, game):
        waiting=[]
        for source in game.battlefield.values():
            if not source.definition.end_step_life_distribution:continue
            maximum=self.life_gained_turn[source.controller]
            if maximum<=0:continue
            event=dict(operation='end_step_life_counters',source=source.id,
                name=source.definition.name,controller=source.controller,
                maximum=maximum,sourceColors=sorted(source.definition.colors))
            candidates=self.life_counter_targets(source.controller,source.id,source.definition.colors)
            allocations=self.choose_life_counter_distribution(event,candidates)
            valid={target.id for target in candidates}
            if (not isinstance(allocations,dict) or
                    any(target not in valid or type(amount) is not int or amount<1
                        for target,amount in allocations.items()) or
                    sum(allocations.values())>maximum):
                raise ValueError('Illegal end-step life-counter target distribution')
            event['distribution']=dict(allocations)
            card=next(item.card for player in self.players for item in player.battlefield
                      if item.card.id==source.id)
            waiting.append((event,card))
        return waiting

    def choose_optional_token_creation(self, event):
        """Diagnostic deterministic accept policy for a legal may-create clause.

        Gameplay agents may later provide a per-trigger policy. The choice is
        made when the triggered ability resolves, never at parse time.
        """
        return True

    def choose_optional_basic_search(self, seat, source):
        """Deterministic diagnostic decision: take the optional search when useful.

        This is a player choice, not a compulsory effect. Future agents may
        supply their own hidden-information-safe decision policy.
        """
        return any(card.kind=='land' and card.basic_land for card in self.players[seat].library)

    def search_basic_land_tapped(self, seat, source):
        """Search the affected player's own private library and shuffle it.

        For Path-style instructions, a player may decline. If they accept,
        searching and shuffling happens even if no matching basic exists.
        A searched land enters tapped without consuming the land play.
        """
        if not self.choose_optional_basic_search(seat,source):
            self.log('search_declined','Player declines an optional basic-land search.',actor=seat,source=source.name)
            return
        player=self.players[seat]
        basic=next((card for card in player.library if card.kind=='land' and card.basic_land),None)
        if basic is not None:
            player.library.remove(basic)
            player.battlefield.append(Permanent(basic,tapped=True))
        self.library_random_sequence+=1
        random.Random(str(self.seed)+':library:'+str(self.library_random_sequence)).shuffle(player.library)
        self.log('search_basic','Player searches their library for a basic land and shuffles.',
                 actor=seat,source=source.name,found=bool(basic),land=basic.name if basic else None)

    def choose_optional_subtype_search(self, seat, subtype):
        """Default diagnostic player policy; not knowledge available to foe."""
        return any(subtype in card.land_subtypes or
                   (card.event_definition and subtype in card.event_definition.subtypes)
                   for card in self.players[seat].library)

    def legal_hand_put_cards(self,seat,subtype,kind):
        """Filter the controller's private hand, never the opponent's hand."""
        if kind not in ('creature','permanent'):raise ValueError('Unknown hand-put type')
        result=[]
        for card in self.players[seat].hand:
            definition=card.event_definition
            subtypes=set(card.land_subtypes)
            if definition:subtypes.update(definition.subtypes)
            if subtype not in subtypes or card.kind=='unsupported':continue
            types=set(card.printed_types)
            if definition:types.update(definition.types)
            if kind=='creature' and 'Creature' not in types:continue
            if kind=='permanent' and (types.intersection({'Instant','Sorcery'}) or card.kind not in
                    ('creature','vehicle','enchantment','mana_artifact','equipment','planeswalker','station','artifact','land','aura')):
                continue
            result.append(card)
        return tuple(result)

    def choose_optional_hand_permanent(self,seat,subtype,kind,options):
        """Diagnostic policy accepts the first legal matching card when available.

        This is a decision at trigger resolution. No private candidate identities
        are exposed through legal actions or the opponent's observation.
        """
        return options[0] if options else None

    def search_subtype_card_to_hand(self, seat, source, subtype):
        """Optional subtype-filtered search. The chosen card is revealed.

        The identity is public only AFTER successful selection. A player can
        decline and preserve library order, or legally fail to find after
        choosing to search a hidden zone (still shuffle).
        """
        if not self.choose_optional_subtype_search(seat,subtype):
            self.log('search_declined','Player declines an optional subtype-card search.',
                     actor=seat,source=source.name,subtype=subtype)
            return
        player=self.players[seat]
        found=next((candidate for candidate in player.library
                    if subtype in candidate.land_subtypes or
                       (candidate.event_definition and subtype in candidate.event_definition.subtypes)),None)
        if found is not None:
            player.library.remove(found)
            player.hand.append(found)
        self.library_random_sequence+=1
        random.Random(str(self.seed)+':library:'+str(self.library_random_sequence)).shuffle(player.library)
        self.log('search_reveal','Player reveals a searched subtype card and shuffles.',
                 actor=seat,source=source.name,subtype=subtype,
                 revealed=found.name if found else None)

    def record_player_damage(self,seat,source_id,amount):
        """Remember damage sources for turn-scoped target legality, not life loss.

        A source can leave the battlefield later; only a still-present creature
        can be targeted by a spell requiring a creature that dealt damage.
        """
        if amount>0 and source_id:
            self.damage_to_players[seat].add(source_id)

    def removal_targets(self,controller,source):
        """Only legal targets for an explicitly parsed targeted removal spell."""
        if source.removal=='exile_creature_damaged_you':
            return tuple((seat,item) for seat,item in self.creature_targets(controller,source)
                         if item.card.id in self.damage_to_players[controller])
        if source.removal in ('destroy','exile_creature_life','exile_creature_basic_land'):return self.creature_targets(controller,source)
        if source.removal not in ('destroy_artifact_enchantment','destroy_artifact_creature_token','destroy_artifact'):return ()
        game=self.event_game('main')
        targets=[]
        for seat,player in enumerate(self.players):
            for item in player.battlefield:
                types=set(item.card.printed_types)
                if item.card.event_definition:types.update(item.card.event_definition.types)
                allowed=({'Artifact','Enchantment'} if source.removal=='destroy_artifact_enchantment' else
                         {'Artifact'} if source.removal=='destroy_artifact' else {'Artifact','Creature'})
                if not types.intersection(allowed) and not (source.removal=='destroy_artifact_creature_token' and
                        item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])):continue
                state=game.battlefield.get(item.card.id)
                if state and game.has(state,'shroud'):continue
                if state and seat!=controller and game.has(state,'hexproof'):continue
                if state and game.protected(state,source.colors):continue
                targets.append((seat,item))
        return tuple(targets)

    def removal_choices(self,seat,card,kind):
        if card.removal=='modal_sweep':
            return tuple(Candidate(card.id+':modes='+str(i)+','+str(j),kind,card.id,
                features=features(power=len(self.modal_sweep_targets(card,(i,j))),
                                  cost=len(self.payment(card,seat=seat).get('sources',[]))),
                label='Cast '+card.name+' choosing modes '+str(i+1)+' and '+str(j+1),
                modal_modes=(i,j))
                for i,j in itertools.combinations(range(len(card.modal_sweeps)),2))
        if card.removal in ('opponent_nonlands','destroy_all_creatures','destroy_toughness_min','destroy_creatures_reward'):
            count=(len(self.nonland_destruction_set(seat))
                   if card.removal=='opponent_nonlands'
                   else len(self.creature_board_destruction_set(
                       card.removal_min_toughness if card.removal=='destroy_toughness_min' else 0)))
            return (Candidate(card.id,kind,card.id,features=features(power=count,cost=len(self.payment(card,seat=seat).get('sources',[]))),label='Cast '+card.name),)
        game=self.event_game('main')
        choices=[]
        for owner,item in self.removal_targets(seat,card):
            state=game.battlefield.get(item.card.id)
            wards=game.ward_costs(state) if state and owner!=seat else ()
            projected=self.payment(replace(card,mana_cost=card.mana_cost+''.join(wards)),seat=seat)
            useful=owner!=seat and (card.removal in ('exile_creature_life','exile_creature_basic_land') or not (state and game.has(state,'indestructible'))) and projected['paid']
            choices.append(Candidate(card.id+':target='+item.card.id,kind,card.id,
                features=features(power=2 if useful else -100,cost=len(projected.get('sources',[]))),
                label='Cast '+card.name+' targeting '+item.card.name,target_permanent=item.card.id))
        return tuple(choices)

    def creature_board_destruction_set(self, minimum_toughness=0):
        """Determine a simultaneous, non-targeted creature destruction set.

        Use current toughness including counters/anthems; indestructible
        survives, while hexproof and protection do not prevent destruction.
        """
        game=self.event_game('main')
        return tuple((seat,item) for seat,player in enumerate(self.players)
            for item in player.battlefield if item.card.id in game.battlefield
            and game.creature(game.battlefield[item.card.id])
            and game.stats(game.battlefield[item.card.id])[1]>=minimum_toughness
            and not game.has(game.battlefield[item.card.id],'indestructible'))

    def modal_sweep_targets(self,card,modes):
        game=self.event_game('main')
        targets=[]
        for index in modes:
            kind,threshold=card.modal_sweeps[index]
            for owner,player in enumerate(self.players):
                for item in player.battlefield:
                    state=game.battlefield.get(item.card.id)
                    if state is None or game.has(state,'indestructible'):continue
                    types=state.definition.types
                    matches=(kind=='artifact' and 'Artifact' in types or
                             kind=='enchantment' and 'Enchantment' in types or
                             kind=='creature_mana_le' and game.creature(state) and
                                 (0 if item.card.is_token else item.card.printed_mana_value or 0)<=threshold or
                             kind=='creature_mana_ge' and game.creature(state) and
                                 (0 if item.card.is_token else item.card.printed_mana_value or 0)>=threshold)
                    if matches and all(item is not old for _,old in targets):
                        targets.append((owner,item))
        return tuple(targets)

    def nonland_destruction_set(self,controller):
        game=self.event_game('main')
        return tuple((owner,item) for owner,player in enumerate(self.players) if owner!=controller
                     for item in player.battlefield if item.card.kind!='land'
                     and not (item.card.event_definition and 'Land' in item.card.event_definition.types)
                     and not (item.card.id in game.battlefield and game.has(game.battlefield[item.card.id],'indestructible')))

    def replace_umbra_destruction(self,owner,item,game):
        """Replace one actual destruction event; not sacrifice, exile or zero toughness.

        Choose the oldest eligible attached Aura deterministically in this
        diagnostic. The creature stays in combat, remains untapped and loses
        all marked damage; only the Aura is destroyed.
        """
        state=game.battlefield.get(item.card.id)
        if (item not in self.players[owner].battlefield or not state
                or not game.creature(state) or game.stats(state)[1]<=0
                or game.has(state,'indestructible')):
            return False
        candidates=[(seat,aura) for seat,player in enumerate(self.players)
                    for aura in player.battlefield
                    if aura.attached_to==item.card.id and aura.card.event_definition
                    and aura.card.event_definition.umbra_armor
                    and aura.card.id in game.battlefield
                    and not game.protected(state,aura.card.colors)]
        if not candidates:return False
        aura_owner,aura=min(candidates,key=lambda pair:(pair[1].attachment_at,pair[1].card.id))
        item.marked_damage=0
        self.send_to_destination(self.players[aura_owner],aura,snapshot=game)
        self.log('umbra_armor','Umbra armor replaces destruction, clearing damage and destroying the Aura.',
                 protected=item.card.id,aura=aura.card.id,controller=aura_owner)
        return True

    def destroy_batch(self,targets,card,reason="destroy",defer_triggers=False,return_destroyed=False):
        game=self.event_game('main')
        targets=[(owner,item) for owner,item in targets
                 if not self.replace_umbra_destruction(owner,item,game)
                 and (card.removal_no_regenerate or not self.replace_regeneration(owner,item,game))]
        creatures=[item.card.id for _,item in targets if item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])]
        triggers=game.death_triggers(creatures)
        for owner,item in targets:
            if item in self.players[owner].battlefield:self.send_to_destination(self.players[owner],item,snapshot=game)
        self.log(reason,f'{card.name}: {len(targets)} permanents leave simultaneously.',destroyed=[item.card.id for _,item in targets])
        self.outcome()
        if self.finished:return
        for trigger in triggers:
            if trigger['effect']=='create tapped Squirrels':
                trigger.update(operation='create_tokens',tokenSpec=dict(amount=trigger['amount'],power=1,toughness=1,
                    colors=['Green'],subtypes=['Squirrel'],keywords=[],tapped=True,land=False))
        if defer_triggers:return (triggers,tuple(targets)) if return_destroyed else triggers
        self.resolve_entry_triggers(triggers,card)

    def counter_stack_item(self,frame):
        event,spell=frame.payload
        if event.get('operation')=='spell':
            types=set(spell.printed_types)
            if spell.event_definition:types.update(spell.event_definition.types)
            if spell.kind in ('creature','vehicle'):types.add('Creature')
            if spell.kind in ('aura','enchantment'):types.add('Enchantment')
            if spell.kind in ('equipment','artifact','mana_artifact'):types.add('Artifact')
            if event.get('bestow'):types={'Enchantment'}
            game=self.event_game('main')
            if any(source.controller==frame.controller and source.definition.protected_spell_types
                   and {word.title() for word in source.definition.protected_spell_types}.intersection(types)
                   for source in game.battlefield.values()):
                return None
        removed=self.stack.counter(frame.id)
        if removed and removed.payload[0].get('operation')=='spell' and not removed.payload[0].get('copy'):
            countered=removed.payload[1]
            owner=self.players[self.card_owners.get(root(countered),removed.controller)]
            if root(countered)==owner.commander_id:owner.command_zone=countered
            elif removed.payload[0].get('flashback'):owner.exile.append(countered)
            else:owner.graveyard.append(countered)
        return removed

    def target_triggers(self,frame,target_id):
        game=self.event_game('main');target=game.battlefield.get(target_id)
        if target is None or target.controller==frame.controller:return []
        return [dict(operation='ward',effect='ward',controller=target.controller,source=target.id,
                     name=target.definition.name+' ward',targetStack=frame.id,payer=frame.controller,cost=cost)
                for cost in game.ward_costs(target)]

    def counter_targets(self,card):
        if card.kind!='counter_spell': return ()
        return tuple(frame for frame in self.stack.items if frame.payload[0].get('operation')=='spell'
                     and (card.counter_filter=='any' or
                          (frame.payload[1].kind=='creature' and not frame.payload[0].get('bestow') and card.counter_filter=='creature') or
                          ((frame.payload[1].kind!='creature' or frame.payload[0].get('bestow')) and card.counter_filter=='noncreature')))

    def priority_observation(self,seat):
        if seat!=self.stack.priority: raise ValueError('Player lacks priority')
        actions=[Candidate('priority-pass','priority_pass',features=features(),label='Pass priority')]
        crews=self.activation_choices(seat,{'crew'})
        if self.group_combat is not None and self.phase=='block' and seat!=self.active:
            game=self.event_game('combat')
            for choice in crews:
                state=game.battlefield[choice.card_id];state.animated=True
                useful=not state.tapped and any(identifier in game.battlefield and game.creature(game.battlefield[identifier])
                    and (not game.has(game.battlefield[identifier],'flying') or game.has(state,'flying') or game.has(state,'reach'))
                    and not game.protected(game.battlefield[identifier],state.definition.colors) for identifier in self.group_combat['attackers'])
                actions.append(replace(choice,features=features(power=.5 if useful else -100)))
        else:actions.extend(crews)
        actions.extend(self.special_choices(seat))
        actions.extend(self.enchantment_copy_choices(seat))
        actions.extend(self.token_ability_choices(seat))
        actions.extend(self.scaled_mana_choices(seat))
        actions.extend(self.sacrifice_choices(seat))
        actions.extend(self.discard_token_choices(seat))
        actions.extend(self.sacrifice_team_choices(seat))
        actions.extend(self.sacrifice_protection_choices(seat))
        actions.extend(self.land_counter_choices(seat))
        actions.extend(self.land_animation_choices(seat))
        actions.extend(self.regenerate_choices(seat))
        actions.extend(self.strip_ability_choices(seat))
        for card in self.permitted_exile_cards(seat):
            if card.instant and self.payment(card,seat=seat)['paid']:
                actions.append(Candidate(card.id+':exile','cast_exile',card.id,
                    features=features(power=card.power),label='Cast exiled '+card.name))
        for card in self.response_choices(seat):
            if card.blink:
                actions.extend(self.blink_choices(seat,card))
            elif card.kind=='removal_spell':
                actions.extend(self.removal_choices(seat,card,'respond'))
            elif card.kind=='counter_spell':
                actions.extend(Candidate(card.id+':target='+str(frame.id),'respond',card.id,
                    features=features(power=2 if frame.controller!=seat else -100,
                                      cost=len(self.payment(card,seat=seat).get('sources',[]))),
                    label='Cast '+card.name+' targeting '+frame.label,target_stack=frame.id)
                    for frame in self.counter_targets(card))
            else: actions.append(Candidate(card.id,'respond',card.id,features(draw=card.draw,life=card.life,
                    power=card.token_count,cost=len(self.payment(card,seat=seat).get('sources',[]))),label='Respond with '+card.name))
        return Observation(seat,self.turn,self.phase,tuple(self.players[seat].hand),
                           json.dumps(self.state(),sort_keys=True),tuple(actions))

    def act_priority(self,seat,choice):
        if choice not in self.priority_observation(seat).legal_actions: raise ValueError('Illegal priority choice')
        if choice.kind=='priority_pass': return self.pass_priority(seat)
        if choice.kind in ('crew','saddle'):
            self.activate_transport(seat,choice.kind,choice.card_id,choice.tap_ids);return 'activate'
        if choice.kind=='history_tokens':
            self.activate_history(seat,choice.card_id);return 'activate'
        if choice.kind=='copy_enchantment_ability':
            self.activate_enchantment_copy(seat,choice.card_id,choice.target_stack)
            return 'activate'
        if choice.kind=='activate_strip':
            self.activate_strip(seat,choice.card_id,choice.activation_index)
            return 'activate'
        if choice.kind=='activate_graveyard_exile':
            self.activate_graveyard_exile(seat,choice.card_id,choice.target_permanent)
            return 'activate'
        if choice.kind=='activate_color_draw':
            self.activate_color_draw(seat,choice.card_id)
            return 'activate'
        if choice.kind=='activate_tokens':
            self.activate_tokens(seat,choice.card_id,choice.activation_index)
            return 'activate'
        if choice.kind=='activate_tribal_tokens':
            self.activate_tribal_tokens(seat,choice.card_id)
            return 'activate'
        if choice.kind=='activate_scaled_mana':
            self.activate_scaled_mana(seat,choice.card_id,choice.x_value)
            return 'activate'
        if choice.kind=='activate_discard_tokens':
            self.activate_discard_tokens(seat,choice.card_id,choice.discard_id)
            return 'activate'
        if choice.kind=='activate_sacrifice_mana':
            self.activate_sacrifice_mana(seat,choice.card_id,choice.tap_ids[0])
            return 'activate'
        if choice.kind=='activate_sacrifice_boost':
            self.activate_sacrifice_boost(seat,choice.card_id,choice.tap_ids[0],choice.target_permanent)
            return 'activate'
        if choice.kind=='activate_regenerate':
            self.activate_regenerate(seat,choice.card_id,choice.target_permanent)
            return 'activate'
        if choice.kind=='activate_land_counters':
            self.activate_land_counters(seat,choice.card_id)
            return 'activate'
        if choice.kind=='activate_land_animation':
            self.activate_land_animation(seat,choice.card_id,choice.target_permanent)
            return 'activate'
        if choice.kind=='activate_sacrifice_team':
            self.activate_sacrifice_team_boost(seat,choice.card_id)
            return 'activate'
        if choice.kind=='activate_sacrifice_protection':
            self.activate_sacrifice_protection(seat,choice.card_id,choice.target_permanent,
                                              ('White','Blue','Black','Red','Green')[choice.x_value])
            return 'activate'
        if choice.kind=='cast_exile':
            card=next(c for c in self.permitted_exile_cards(seat) if c.id==choice.card_id)
            self.cast_spell(seat,card,exile_permission=True)
            return 'cast'
        card=next(c for c in self.players[seat].hand if c.id==choice.card_id)
        self.cast_spell(seat,card,target=choice.target_permanent or choice.target_stack,modal_modes=choice.modal_modes)
        return 'cast'

    def cast_spell(self,seat,card,x=None,commander=False,target=None,bestow=False,rebound=False,flashback=False,keyword_choice=None,modal_modes=(),exile_permission=False,zone_card=None):
        player=self.players[seat]
        if not card.instant and seat!=self.stack.priority: raise ValueError('Player lacks priority')
        if self.stack.items:
            if seat!=self.stack.priority or not card.instant: raise ValueError('Spell timing or priority invalid')
        elif seat!=self.active or self.phase not in ('main','second_main'):
            if not card.instant or seat!=self.stack.priority: raise ValueError('Spell timing invalid')
        if rebound and self._rebound_permission!=(seat,root(card)):raise ValueError('No rebound casting permission')
        if flashback and (commander or rebound or bestow or not card.flashback_cost):
            raise ValueError('No supported flashback permission')
        if exile_permission:
            if commander or rebound or flashback or bestow or card not in self.permitted_exile_cards(seat):
                raise ValueError('No valid exile casting permission')
            casting_zone=next(p.exile for p in self.players if card in p.exile)
        else:casting_zone=player.exile if rebound else player.graveyard if flashback else player.hand
        if not commander and (zone_card or card) not in casting_zone: raise ValueError('Card not in casting zone')
        if bestow and (not card.event_definition or not card.event_definition.bestow):raise ValueError('Card has no supported bestow ability')
        if (card.kind=='aura' or bestow) and target not in {p.card.id for _,p in
                (self.aura_targets(seat,card) if card.kind=='aura' and not bestow else self.creature_targets(seat,card))}:
            raise ValueError('Illegal Aura target')
        if card.kind=='modifier_spell' and target not in {item.card.id for _,item in self.creature_targets(seat,card)}:
            raise ValueError('Temporary modifier requires a legal creature target')
        if card.kind=='modifier_spell' and keyword_choice is not None and keyword_choice not in card.target_modifier[2]:
            raise ValueError('Unknown keyword choice')
        if card.kind=='removal_spell' and card.removal not in ('opponent_nonlands','destroy_all_creatures','destroy_toughness_min','destroy_creatures_reward','modal_sweep') and target not in {item.card.id for _,item in self.removal_targets(seat,card)}:
            raise ValueError('Removal requires a legal permanent target')
        if card.modal_sweeps:
            if len(modal_modes)!=2 or tuple(sorted(set(modal_modes)))!=tuple(modal_modes) or any(
                    not isinstance(i,int) or i<0 or i>=len(card.modal_sweeps) for i in modal_modes):
                raise ValueError('Choose two distinct legal modes on casting')
        elif modal_modes:
            raise ValueError('Spell has no modal destruction choices')
        if card.kind=='graveyard_return_spell' and target not in {c.id for c in self.graveyard_subtype_targets(seat,card.graveyard_return_subtype)}:
            raise ValueError('Graveyard return requires legal target')
        if card.kind=='counter_spell' and target not in {f.id for f in self.counter_targets(card)}:
            raise ValueError('Counterspell requires a legal spell target')
        if card.blink and target not in {p.card.id for owner,p in self.creature_targets(seat,card) if owner==seat}:raise ValueError('Blink requires own legal creature')
        payment_card=replace(card,mana_cost=card.event_definition.bestow[0]) if bestow else card
        if rebound:payment_card=replace(payment_card,mana_cost='{0}')
        elif flashback:payment_card=replace(payment_card,mana_cost=card.flashback_cost)
        payment=self.payment(payment_card,player.commander_casts if commander else 0,x=x,seat=seat)
        if not payment['paid']: raise ValueError('Cannot pay spell cost')
        for source in player.battlefield:
            if source.card.id in payment['sources']:source.tapped=True
        player.mana_pool=list(payment['pool'])
        if commander:player.command_zone=None;player.commander_casts+=1
        else:casting_zone.remove(zone_card or card)
        if exile_permission:self.exile_cast_permissions.pop(card.id,None)
        prior=sum(e['kind']=='cast' and e['turn']==self.turn for e in self.events)
        self.stack.active=self.active
        frame=self.stack.push(seat,({'operation':'spell','controller':seat,'x':x,'target':target,'bestow':bestow,'flashback':flashback,'keywordChoice':keyword_choice or (card.target_modifier[2][0] if card.target_modifier and card.target_modifier[2] else None),'modalModes':tuple(modal_modes),'fromHand':not rebound and not flashback and not commander and not exile_permission},card),card.name)
        self.log('cast',f'Player {seat+1} casts {card.name}.',actor=seat,card=card.name,
                 manaSources=payment['sources'],manaPool=list(player.mana_pool),commander=commander,xValue=x,bestow=bestow,rebound=rebound,flashback=flashback,exilePermission=exile_permission,targetStack=target if card.kind=='counter_spell' else None,
                 targetPermanent=target if card.kind in ('removal_spell','modifier_spell') else None)
        self.stack.priority=seat
        self.log('stack_push',f'{card.name} goes on the stack.',stackId=frame.id,controller=seat)
        if card.storm:
            self.log('storm',f'{card.name} creates {prior} spell copies.',copies=prior)
            for _ in range(prior):self.stack.push(seat,({'operation':'spell','controller':seat,'copy':True,'x':x},card),card.name+' copy')
        # Casting is the event: place its abilities above the spell itself.
        # Countering the spell later cannot undo a triggered ability.
        cast_triggers=self.event_game('main').cast_triggers(card,seat)
        wards=self.target_triggers(frame,target)
        if cast_triggers or wards:
            self.resolve_entry_triggers(cast_triggers+wards,card,priority=seat)
        elif not self.manual_priority and not self._resolving_stack:
            self.drain_priority()

    def resolve_spell(self,event,original):
        controller=event['controller'];p=self.players[controller];card=original
        if event.get('copy'): self.log('spell_copy',f'A copy of {card.name} resolves.',card=card.name)
        if card.blink:
            target=next(((owner,item) for owner,item in self.creature_targets(controller,card) if owner==controller and item.card.id==event['target']),None)
            if target is None:
                if not event.get('copy'):p.graveyard.append(original)
                self.log('illegal_target',f'{card.name} has no legal blink target.')
                return
            if not event.get('copy'):
                if card.rebound and event.get('fromHand'):
                    p.exile.append(original);self.rebound_pending.append(dict(controller=controller,card=root(original),afterTurn=self.turn))
                else:p.graveyard.append(original)
            self.blink_permanent(*target,return_controller=controller if card.blink_to_controller else None)
            return
        if event.get('bestow'):
            if event['target'] in {target.card.id for _,target in self.creature_targets(controller,card)}:
                pending=self.enter_creatures([card],p,{card.id:event['target']})
                self.log('bestow',f'{card.name} enters as an Aura.',targetPermanent=event['target'])
                self.resolve_entry_triggers(pending,card)
            else:
                pending=self.enter_creature(card,p)
                self.log('bestow_creature',f'{card.name} resolves as a creature after its target became illegal.')
                self.resolve_entry_triggers(pending,card)
            return
        if card.kind=='aura':
            if event['target'] not in {p.card.id for _,p in self.aura_targets(controller,card)}:
                if not event.get('copy'):p.graveyard.append(card)
                self.log('illegal_target',f'{card.name} has no legal Aura target.')
                return
            pending=self.enter_creature(card,p,attached_to=event['target'])
            self.resolve_entry_triggers(pending,card)
            self.log('attach',f'{card.name} enchants a creature.',targetPermanent=event['target'])
            return
        if card.kind=='equipment':
            pending=self.enter_creature(card,p)
            self.resolve_entry_triggers(pending,card)
            return
        if card.kind in ('creature','vehicle','enchantment','planeswalker','station','artifact'):
            triggers=self.enter_creature(card,p)
            self.resolve_entry_triggers(triggers,card)
        elif card.kind=='mana_artifact': p.battlefield.append(Permanent(card))
        elif not event.get('copy'):
            (p.exile if event.get('flashback') else p.graveyard).append(original)
        if card.kind=='sacrifice_spell':
            scope,count=card.forced_sacrifice
            for affected in range(len(self.players)):
                if scope=='opponent' and affected==controller:continue
                for _ in range(count):
                    self.force_opponent_sacrifice(controller,affected,card)
                    if self.finished:return
            return
        if card.kind=='graveyard_return_spell':
            target=next((c for c in self.graveyard_subtype_targets(controller,card.graveyard_return_subtype)
                         if c.id==event.get('target')),None)
            if target:
                p.graveyard.remove(target);p.hand.append(target)
                self.log('graveyard_return','A subtype card is returned from graveyard to hand.',
                         actor=controller,card=target.name,source=card.name)
            else:self.log('illegal_target','Graveyard-return target no longer exists.',actor=controller,source=card.name)
            return
        if card.kind=='modifier_spell':
            target=next((item for _,item in self.creature_targets(controller,card)
                         if item.card.id==event.get('target')),None)
            if target is None:
                self.log('modifier_fizzle','Targeted temporary modifier has no legal target.',
                         actor=controller,source=card.name,targetPermanent=event.get('target'))
                return
            power,toughness,choices,draw_subtype=card.target_modifier
            game=self.event_game('main')
            state=game.battlefield[target.card.id]
            state.temporary_power+=power
            state.temporary_toughness+=toughness
            chosen=event.get('keywordChoice')
            if choices:
                if chosen not in choices:raise RuntimeError('Unrecognized spell keyword choice')
                game.grant_temporary(state,chosen)
            self.sync_events(game)
            if draw_subtype and any(draw_subtype in x.definition.subtypes and x.controller==controller
                                    for x in game.battlefield.values()):
                self.draw(controller)
                self.outcome()
            self.log('modifier_resolve','Targeted temporary modifier resolves.',
                     actor=controller,source=card.name,targetPermanent=target.card.id,
                     power=power,toughness=toughness,keyword=chosen,drawCondition=draw_subtype)
            self.resolve_entry_triggers(self.state_based_actions(),card)
            return
        if card.kind=='removal_spell':
            if card.removal=='modal_sweep':
                pending=[]
                for mode in event['modalModes']:
                    pending.extend(self.destroy_batch(self.modal_sweep_targets(card,(mode,)),card,
                        reason='modal_destroy',defer_triggers=True) or [])
                    if self.finished:break
                if not self.finished:self.resolve_entry_triggers(pending,card)
                return
            if card.removal in ('destroy_all_creatures','destroy_toughness_min','destroy_creatures_reward'):
                threshold=card.removal_min_toughness if card.removal=='destroy_toughness_min' else 0
                if card.removal=='destroy_creatures_reward':
                    result=self.destroy_batch(self.creature_board_destruction_set(),card,
                                              defer_triggers=True,return_destroyed=True)
                    if result is None:return
                    triggers,destroyed=result
                    nontoken,per_creature,tapped=card.sweep_reward
                    count=sum(not nontoken or not item.card.is_token for _,item in destroyed)
                    self.create_treasures(controller,count*per_creature,tapped,card,triggers)
                else:self.destroy_batch(self.creature_board_destruction_set(threshold),card)
                return
            if card.removal=='opponent_nonlands':
                self.destroy_batch(self.nonland_destruction_set(controller),card)
                return
            target=next(((seat,item) for seat,item in self.removal_targets(controller,card) if item.card.id==event['target']),None)
            if target is None:
                self.log('illegal_target',f'{card.name} has no legal permanent target.',targetPermanent=event['target'])
                return
            owner,item=target;game=self.event_game('main')
            state=game.battlefield.get(item.card.id)
            if card.removal=='destroy_artifact_creature_token':
                indestructible=bool(state and game.has(state,'indestructible'))
                if indestructible:
                    self.log('indestructible','Target cannot be destroyed, but the remaining spell instruction still resolves.',
                             targetPermanent=item.card.id)
                else:
                    self.destroy_batch(((owner,item),),card)
                if card.token_definition is None or card.token_count<1:
                    raise RuntimeError('Missing replacement token characteristics')
                d=card.token_definition
                spec=dict(amount=card.token_count,power=d.power,toughness=d.toughness,
                          subtypes=sorted(d.subtypes),colors=sorted(d.colors),
                          keywords=sorted(d.abilities),tapped=card.token_tapped)
                self._resolve_entry_effects([dict(operation='create_tokens',
                    effect='the target controller creates creature tokens',
                    source=card.id,controller=owner,name=card.name,tokenSpec=spec)],card)
                return
            if card.removal=='exile_creature_damaged_you':
                self.send_to_destination(self.players[owner],item,snapshot=game,to_exile=True)
                self.log('exile',f'{card.name} exiles a creature that damaged its caster this turn.',
                         actor=controller,targetPermanent=item.card.id)
                self.resolve_entry_triggers([],card)
                return
            if card.removal=='exile_creature_basic_land':
                self.send_to_destination(self.players[owner],item,snapshot=game,to_exile=True)
                self.log('exile',f'{card.name} exiles {item.card.name}.',
                         actor=controller,targetPermanent=item.card.id,gainController=owner)
                self.search_basic_land_tapped(owner,card)
                self.resolve_entry_triggers([],card)
                return
            if card.removal=='exile_creature_life':
                power=max(0,game.stats(state)[0])
                self.send_to_destination(self.players[owner],item,snapshot=game,to_exile=True)
                self.gain_life(owner,power)
                self.log('exile',f'{card.name} exiles {item.card.name}; its controller gains {power} life.',
                         actor=controller,targetPermanent=item.card.id,gained=power,gainController=owner)
                self.resolve_entry_triggers([],card)
                return
            if state and game.has(state,'indestructible'):
                self.log('indestructible',f'{item.card.name} cannot be destroyed.',targetPermanent=item.card.id)
                return
            self.destroy_batch(((owner,item),),card)
            return
        if card.kind=='counter_spell':
            frame=next((f for f in self.counter_targets(card) if f.id==event['target']),None)
            if frame is None:
                self.log('illegal_target',f'{card.name} has no legal target and does not resolve.',targetStack=event['target'])
                return
            removed=self.counter_stack_item(frame)
            self.log('counter' if removed else 'counter_prevented',
                     f'{card.name} counters {frame.label}.' if removed
                     else 'The spell cannot be countered.',
                     targetStack=frame.id)
            return
        if card.kind=='x_spell':
            x=event['x']
            card=replace(card,kind='token_spell' if card.x_effect=='tokens' else 'spell',
                         token_count=x if card.x_effect=='tokens' else 0,
                         draw=x if card.x_effect=='draw' else 0,life=x if card.x_effect=='life' else 0)
        if card.kind == "token_spell":
            for resolution in range(1):
                token_triggers = []
                game=self.event_game('main')
                created=game.token_amount(controller,card.token_count)
                template=card.token_definition
                if template is None: raise RuntimeError("Missing parsed token characteristics")
                spec=game.replace_creature_token_spec(controller,dict(
                    power=template.power,toughness=template.toughness,
                    colors=tuple(template.colors),subtypes=tuple(template.subtypes),
                    keywords=tuple(template.abilities),
                    land='Land' in template.types,enchantment='Enchantment' in template.types))
                definition=replace(template,name=' '.join(spec['subtypes']),
                    types=frozenset({'Creature'}|({'Land'} if spec.get('land') else set())|
                                    ({'Enchantment'} if spec.get('enchantment') else set())),
                    subtypes=frozenset(spec['subtypes']),power=spec['power'],
                    toughness=spec['toughness'],abilities=frozenset(spec['keywords']),
                    colors=frozenset(spec['colors']))
                for _ in range(created):
                    self.token_sequence += 1
                    token = Card(f"token-{self.token_sequence}",definition.name,"creature",
                                 traits=f"{definition.power};{definition.toughness};"+",".join(sorted(definition.abilities)),
                                 power=definition.power,toughness=definition.toughness,
                                 event_definition=definition,is_token=True)
                    token_triggers.extend(self.enter_creature(token,p))
                    next(x for x in p.battlefield if x.card.id==token.id).tapped = card.token_tapped
                    self.log("token", f"Creates a {definition.power}/{definition.toughness} {definition.name} creature token.",
                             card=definition.name, token=token.id)
                # Tokens created by a spell are one event for replacements,
                # but each token creates its own triggered ability.
                token_triggers.extend(self.event_game('main').token_action_events('create',controller,created))
                self.resolve_entry_triggers(token_triggers, card)
                if self.finished: return False
        if card.kind == "spell":
            for _ in range(card.draw): self.draw(controller)
            self.gain_life(controller,card.life)
            self.log("resolve", f"{card.name} resolves.", lifeGain=card.life, drawn=card.draw)
            self.outcome()

    def _resolve_entry_effects(self, triggers: list[dict], card: Card):
        for event in triggers:
            if event.get('operation')=='saga_chapter_bonus':
                game=self.event_game('main');target=game.battlefield.get(event['target'])
                legal=bool(target and game.creature(target) and not game.has(target,'shroud') and
                           (target.controller==event['controller'] or not game.has(target,'hexproof')))
                if legal:
                    count=sum(p.controller==event['controller'] and bool(
                        {'Artifact','Enchantment'}&p.definition.types)
                        for p in game.battlefield.values())
                    item=next(p for owner in self.players for p in owner.battlefield
                              if p.card.id==event['target'])
                    item.temporary_power+=count*event['power']
                    item.temporary_toughness+=count*event['toughness']
                self.log('saga_bonus' if legal else 'saga_bonus_fizzle',
                    'Saga chapter grants counted temporary power and toughness.' if legal else
                    'Saga chapter target is no longer legal.',actor=event['controller'],
                    source=event['source'],target=event['target'],
                    chapter=event['chapter'],count=count if legal else 0)
                if legal:self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='saga_transform':
                controller=event['controller'];owner=self.players[controller]
                saga=next((p for p in owner.battlefield if p.card.id==event['source']),None)
                if saga is None or saga.lore_counters<3 or not saga.card.transform_back_face:
                    self.log('saga_transform_fizzle','Saga chapter III has no surviving source.',
                        actor=controller,source=event['source'])
                    continue
                front=saga.card
                self.send_to_destination(owner,saga,to_exile=True)
                # Tokens cease existing after exile and cannot return.
                if front.is_token:
                    self.log('saga_token_exiled','Token Saga does not return transformed.',
                        actor=controller,source=event['source'])
                    continue
                physical_owner=self.players[self.card_owners.get(root(front),controller)]
                exiled=next((c for c in physical_owner.exile if c.id==front.id),None)
                if not exiled:raise RuntimeError('Saga exile zone lost physical card')
                physical_owner.exile.remove(exiled)
                back=replace(front.transform_back_face,modal_front_face=front,
                    physical_id=root(front),printed_mana_value=front.printed_mana_value)
                pending=self.enter_creature(back,owner)
                self.log('saga_transformed','Saga exiles and returns on its transformed face.',
                    actor=controller,source=front.id,backFace=back.name)
                self.resolve_entry_triggers(pending,back)
                continue
            if event.get('operation')=='constellation_counter':
                game=self.event_game('main');identifier=event['target']
                state=game.battlefield.get(identifier)
                legal=bool(state and game.creature(state) and not game.has(state,'shroud')
                          and (state.controller==event['controller'] or not game.has(state,'hexproof')))
                if legal:
                    item=next(item for p in self.players for item in p.battlefield
                              if item.card.id==identifier)
                    item.counters+=game.counter_amount(identifier,1)
                self.log('constellation_counter' if legal else 'constellation_fizzle',
                    'Constellation puts a counter on target creature.' if legal else
                    'Constellation target left or became illegal.',
                    actor=event['controller'],source=event['source'],target=identifier)
                if legal:self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='enchantment_combat_copy':
                key=(event['source'],event['sourceEntry'])
                used=getattr(self,'enchantment_copy_used',{})
                if used.get(key)==self.turn:
                    self.log('enchantment_copy_limit','Once-per-turn copy already created.',
                        actor=event['controller'],source=event['source'])
                    continue
                owner=self.players[event['controller']]
                options=[item for item in owner.battlefield
                    if item.card.event_definition
                    and 'Enchantment' in item.card.event_definition.types
                    and not item.card.legendary]
                options.sort(key=lambda item:(item.card.kind=='aura',item.card.id))
                chosen=None;target_id=None
                for candidate in options:
                    if candidate.card.kind=='aura':
                        targets=self.aura_targets(event['controller'],candidate.card)
                        if not targets:continue
                        target_id=min(targets,key=lambda value:(value[0]!=event['controller'],value[1].card.id))[1].card.id
                    chosen=candidate;break
                if not chosen or not self.choose_optional_enchantment_copy(event,chosen):
                    self.log('enchantment_copy_declined','No eligible enchantment or copy declined.',
                        actor=event['controller'],source=event['source'])
                    continue
                self.token_sequence+=1
                base=chosen.card
                token=replace(base,id='token-'+str(self.token_sequence),is_token=True,
                              physical_id='',modal_front_face=None,modal_spell_face=None,
                              modal_land_face=None,legendary=False)
                pending=self.enter_creature(token,owner,attached_to=target_id)
                used[key]=self.turn;self.enchantment_copy_used=used
                self.log('enchantment_copied','Creates a nonlegendary enchantment token copy.',
                    actor=event['controller'],source=event['source'],
                    copiedFrom=base.id,token=token.id,attachedTo=target_id)
                self.resolve_entry_triggers(pending,token)
                continue
            if event.get('operation')=='return_dead_equipped':
                owner=self.players[event['victimOwner']]
                victim=next((card for card in owner.graveyard
                             if card.id==event['victim']),None)
                if victim:
                    owner.graveyard.remove(victim)
                    owner.hand.append(victim.modal_front_face or victim)
                self.log('return_equipped' if victim else 'return_equipped_fizzle',
                    'Equipped creature returns to owner hand.' if victim else
                    'Creature card is no longer in its owner graveyard.',
                    actor=event['controller'],source=event['source'],
                    victim=event['victim'])
                continue
            if event.get('operation')=='combat_reattach':
                controller=event['controller'];game=self.event_game('combat')
                src=next((item for item in self.players[controller].battlefield
                          if item.card.id==event['attachment']),None)
                attached=game.battlefield.get(src.attached_to) if src else None
                target=game.battlefield.get(event['target'])
                valid=(src is not None and attached is not None and target is not None
                       and attached.controller==controller and game.creature(attached)
                       and target.controller==controller and game.creature(target)
                       and target.id!=attached.id and not game.has(target,'shroud')
                       and not game.protected(target,src.card.colors))
                if valid and src.card.kind=='aura':
                    valid=event['target'] in {p.card.id for seat,p in
                        self.aura_targets(controller,src.card) if seat==controller}
                if valid and self.choose_optional_combat_reattach(event):
                    src.attached_to=event['target'];self.effect_clock+=1
                    src.attachment_at=self.effect_clock
                    self.log('combat_reattach','Combat source moves an attachment.',
                        actor=controller,source=event['source'],attachment=src.card.id,
                        target=event['target'])
                else:
                    self.log('combat_reattach_fizzle','Attachment move declined or illegal.',
                             actor=controller,source=event['source'])
                continue
            if event.get('operation')=='class_level_up':
                source=next((item for item in self.players[event['controller']].battlefield
                             if item.card.id==event['source']),None)
                if source and source.class_level==event['expected']:
                    source.class_level=event['nextLevel']
                    self.log('class_level','Class gains its next level.',
                             actor=event['controller'],source=event['source'],
                             level=source.class_level)
                else:
                    self.log('class_level_fizzle','Class left play or no longer at expected level.',
                             actor=event['controller'],source=event['source'])
                continue
            if event.get('operation')=='class_attack_boost':
                game=self.event_game('combat');identifier=event['target']
                valid=self.group_combat is not None and identifier in self.group_combat['attackers']
                state=game.battlefield.get(identifier)
                valid=valid and state is not None and state.controller==event['controller'] and game.creature(state)
                if not valid:
                    self.log('class_attack_fizzle','Target attacker no longer legal.',
                             actor=event['controller'],target=identifier)
                    continue
                target=next(item for item in self.players[event['controller']].battlefield
                            if item.card.id==identifier)
                other=sum(i!=identifier for i in self.group_combat['attackers']
                          if i in game.battlefield and game.creature(game.battlefield[i]))
                target.temporary_power+=other*event['powerPerOther']
                target.temporary_toughness+=other*event['toughnessPerOther']
                target.temporary_abilities=frozenset(set(target.temporary_abilities)|{event['keyword']})
                self.effect_clock+=1
                target.temporary_ability_times[event['keyword']]=self.effect_clock
                self.log('class_attack_boost','Class grants combat bonus and keyword.',
                         actor=event['controller'],source=event['source'],target=identifier,
                         otherAttackers=other,keyword=event['keyword'])
                continue
            if event.get('operation')=='copy_enchantment_ability':
                # The target ability must still be on the stack when this resolves.
                # Both objects are independent and no spell is cast.
                source=next((frame for frame in self.stack.items
                             if frame.id==event['targetStack']),None)
                if source is None or source.controller!=event['controller'] or (
                        source.payload[0].get('operation')=='spell'):
                    self.log('ability_copy_fizzle','Targeted ability left the stack.',
                             actor=event['controller'],targetStack=event['targetStack'])
                    continue
                original,origin=source.payload
                duplicate=dict(original,copied=True)
                copied=self.stack.push(event['controller'],(duplicate,origin),
                                       source.label+' copy')
                self.stack.priority=self.active
                self.log('ability_copy','An enchantment ability is copied on the stack.',
                         actor=event['controller'],targetStack=source.id,stackId=copied.id)
                continue
            if event.get('operation')=='exile_top_cast_permission':
                seat=event['controller'];player=self.players[seat]
                if not player.library:
                    self.log('exile_top_empty','No card remains on top of the library.',actor=seat,source=event['source'])
                    continue
                card_top=player.library.pop()
                owner=self.card_owners.get(root(card_top),seat)
                self.players[owner].exile.append(card_top)
                restriction=event['libraryFilter']
                if len(restriction)!=3 or restriction[0]!='subtype' or restriction[2]!='creature':
                    raise RuntimeError('Unknown exiled card cast restriction')
                eligible='Creature' in card_top.printed_types and restriction[1] in card_top.land_subtypes
                expiry=self.turn+(2 if self.active==seat else 1)
                if eligible:self.exile_cast_permissions[card_top.id]=(seat,expiry,restriction[1])
                self.log('exile_top','Exile the real top card, then reveal it.',actor=seat,
                         source=event['source'],card=card_top.name,cardId=card_top.id,
                         cardOwner=owner,controller=seat,eligible=eligible,
                         permissionExpiresTurn=expiry if eligible else None)
                continue
            if event.get('operation')=='exile_graveyard_conditional_token':
                seat=event['controller'];zone=event['targetZoneOwner']
                target=next((c for c in self.players[zone].graveyard if c.id==event['target'] and not c.is_token),None)
                if target is None or zone==seat:
                    self.log('graveyard_exile_fizzle','Target no longer legal.',actor=seat,
                             source=event['source'],targetCard=event['target'])
                    continue
                self.players[zone].graveyard.remove(target)
                physical_owner=self.card_owners.get(root(target),zone)
                self.players[physical_owner].exile.append(target)
                creature=('Creature' in target.printed_types or target.kind=='creature' or
                          bool(target.event_definition and 'Creature' in target.event_definition.types))
                self.log('graveyard_exile','Exile targeted graveyard card.',actor=seat,
                         source=event['source'],targetCard=target.id,targetName=target.name,
                         zoneOwner=zone,cardOwner=physical_owner,wasCreature=creature)
                if creature:
                    self._resolve_entry_effects([dict(operation='create_tokens',controller=seat,
                        source=event['source'],name=event['name'],tokenSpec=event['tokenSpec'])],card)
                continue
            if event.get('operation')=='draw_by_permanent_colors':
                seat=event['controller'];game=self.event_game('main')
                colors={'White','Blue','Black','Red','Green'}
                present=set().union(*(set(p.definition.colors)&colors for p in game.battlefield.values() if p.controller==seat))
                self.log('color_draw_resolution','Count distinct controlled permanent colors at resolution.',actor=seat,source=event['source'],colorCount=len(present))
                for _ in present:self.draw(seat)
                self.outcome()
                continue
            if event.get('operation')=='animate_land':
                game=self.event_game('main')
                target=game.battlefield.get(event['target'])
                legal=bool(target and target.controller==event['controller'] and
                           'Land' in target.definition.types and
                           not game.has(target,'shroud') and
                           not game.protected(target,event['sourceColors']))
                if legal:
                    amount=sum(state.controller==event['controller'] and event['countType'] in state.definition.types
                               for state in game.battlefield.values())
                    item=next(item for item in self.players[event['controller']].battlefield
                              if item.card.id==event['target'])
                    item.temporary_land_power=amount
                    item.temporary_land_subtype=event['subtype']
                    item.temporary_abilities=frozenset(set(item.temporary_abilities)|{'trample','haste'})
                    self.effect_clock+=1
                    item.temporary_ability_times.update({'trample':self.effect_clock,'haste':self.effect_clock})
                    self.log('animate_land','Land becomes a temporary Elemental creature with fixed X/X.',
                             actor=event['controller'],target=event['target'],power=amount,subtype=event['subtype'])
                    self.resolve_entry_triggers(self.state_based_actions(),card)
                else:
                    self.log('animate_land_fizzle','Land-animation target is no longer legal.',
                             actor=event['controller'],target=event['target'])
                continue
            if event.get('operation')=='end_step_life_counters':
                game=self.event_game('main')
                legal={target.id for target in self.life_counter_targets(
                    event['controller'],event['source'],event['sourceColors'])}
                delivered={}
                for identifier,amount in event['distribution'].items():
                    if identifier not in legal:continue
                    state=game.battlefield[identifier]
                    added=game.counter_amount(identifier,amount)
                    state.counters+=added
                    delivered[identifier]=added
                self.sync_events(game)
                self.log('end_step_life_counters','Targeted life-gain counters resolve with original distribution.',
                         actor=event['controller'],source=event['source'],maximum=event['maximum'],
                         distribution=event['distribution'],delivered=delivered)
                self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='sacrifice_protection':
                game=self.event_game('main');target=game.battlefield.get(event['target'])
                legal=bool(target and target.controller==event['controller']
                           and set(event['targetTypes']).intersection(target.definition.types)
                           and not game.has(target,'shroud')
                           and not game.protected(target,event.get('sourceColors',())))
                if legal:
                    game.grant_temporary(target,'protection from '+event['color'].lower())
                    self.sync_events(game)
                self.log('sacrifice_protection' if legal else 'sacrifice_protection_fizzle',
                         'Chosen-color protection resolves.' if legal else 'Protection target is no longer legal.',
                         actor=event['controller'],source=event['source'],targetPermanent=event['target'],color=event['color'])
                continue
            if event.get('operation')=='sacrifice_team_boost':
                game=self.event_game('main');affected=[]
                for target in game.battlefield.values():
                    if target.controller==event['controller'] and game.creature(target):
                        target.temporary_power+=event['power']
                        target.temporary_toughness+=event['toughness']
                        affected.append(target.id)
                self.sync_events(game)
                self.log('sacrifice_team_boost','Sacrificed enchantment boosts creatures controlled at resolution.',
                         actor=event['controller'],source=event['source'],affected=affected)
                continue
            if event.get('operation')=='mentor_counter':
                game=self.event_game('combat')
                source=game.battlefield.get(event['source'])
                target=game.battlefield.get(event['target'])
                power=game.stats(source)[0] if source and game.creature(source) else event['sourcePower']
                attacking=set(self.group_combat['attackers']) if self.group_combat else set()
                legal=bool(target and target.id in attacking and target.controller==event['controller']
                           and game.creature(target) and game.stats(target)[0]<power
                           and not game.has(target,'shroud')
                           and not game.protected(target,event.get('sourceColors',())))
                if legal:
                    target.counters+=game.counter_amount(target.id,1)
                    self.sync_events(game)
                self.log('mentor_counter' if legal else 'mentor_fizzle',
                         'Mentor places a counter on a lesser-power attacker.' if legal else 'Mentor target is no longer legal.',
                         source=event['source'],targetPermanent=event['target'],actor=event['controller'])
                continue
            if event.get('operation')=='regenerate_shield':
                game=self.event_game('main');target=game.battlefield.get(event['target'])
                legal=bool(target and game.creature(target) and
                           event['subtype'] in target.definition.subtypes and
                           target.id!=event['source'] and not game.has(target,'shroud') and
                           (target.controller==event['controller'] or not game.has(target,'hexproof')) and
                           not game.protected(target,event.get('sourceColors',())))
                if legal:
                    item=next(p for player in self.players for p in player.battlefield if p.card.id==target.id)
                    item.regeneration_shields+=1
                self.log('regeneration_shield' if legal else 'regeneration_fizzle',
                         'Regeneration shield created.' if legal else 'Regeneration target is illegal.',
                         actor=event['controller'],targetPermanent=event['target'])
                continue
            if event.get('operation')=='land_team_counters':
                game=self.event_game('main');seat=event['controller'];affected=[]
                for target in game.battlefield.values():
                    if (target.controller==seat and game.creature(target)
                            and self.land_counter_target(target,event.get('scope','all'))):
                        amount=game.counter_amount(target.id,1)
                        target.counters+=amount;affected.append((target.id,amount))
                self.sync_events(game)
                self.log('land_team_counters','Counters placed on all creatures controlled at resolution.',
                         actor=seat,source=event['source'],affected=affected)
                self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='sacrifice_target_boost':
                game=self.event_game('main');target=game.battlefield.get(event['target'])
                legal=bool(target and game.creature(target) and not game.has(target,'shroud')
                           and (target.controller==event['controller'] or not game.has(target,'hexproof'))
                           and not game.protected(target,event.get('sourceColors',())))
                if legal:
                    target.temporary_power+=event['power']
                    target.temporary_toughness+=event['toughness']
                    self.sync_events(game)
                self.log('sacrifice_boost' if legal else 'sacrifice_boost_fizzle',
                         'Sacrifice boost resolves.' if legal else 'Sacrifice boost target is illegal.',
                         actor=event['controller'],target=event['target'],source=event['source'])
                continue
            if event.get('operation')=='living_weapon':
                # Create tokens first, attach one while state-based actions
                # are not checked, then let any unattached 0/0 Germs die.
                controller=event['controller'];owner=self.players[controller]
                source=next((p for p in owner.battlefield
                             if p.card.id==event['source'] and p.card.kind=='equipment'
                             and p.entered_at==event['sourceEntry']),None)
                created=self.event_game('main').token_amount(controller,1)
                pending=[];germs=[]
                for _ in range(created):
                    self.token_sequence+=1
                    definition=EventDefinition('Phyrexian Germ',frozenset({'Creature'}),
                        frozenset({'Phyrexian','Germ'}),False,0,0,frozenset(),
                        colors=frozenset({'Black'}))
                    token=Card('token-'+str(self.token_sequence),'Phyrexian Germ','creature',
                               traits='0;0;',power=0,toughness=0,
                               event_definition=definition,is_token=True,colors=('Black',))
                    pending.extend(self.enter_creature(token,owner))
                    germs.append(token)
                if source and germs:
                    source.attached_to=germs[0].id
                    self.effect_clock+=1;source.attachment_at=self.effect_clock
                pending.extend(self.event_game('main').token_action_events('create',controller,created))
                self.log('living_weapon','Living weapon creates Germ tokens and attaches Equipment when present.',
                         actor=controller,source=event['source'],created=created,
                         attachedTo=germs[0].id if source and germs else None)
                self.resolve_entry_triggers(pending,card)
                continue
            if event.get('operation')=='exile_until_aura_leaves':
                # The delayed return belongs to this specific Aura instance.
                # If it left before the ETB trigger resolved, nothing is exiled.
                game=self.event_game('main')
                source=game.battlefield.get(event['source'])
                legal=next(((owner,item) for owner,item in self.creature_targets(event['controller'],card)
                            if owner!=event['controller'] and item.card.id==event.get('target')),None)
                if not source or source.entered_at!=event['sourceEntry'] or legal is None:
                    self.log('aura_exile_fizzle','Aura exile trigger has no legal source or target.',
                             source=event['source'],targetPermanent=event.get('target'))
                    continue
                owner,item=legal
                self.send_to_destination(self.players[owner],item,snapshot=game,to_exile=True)
                physical_owner=self.card_owners.get(root(item.card),owner)
                if item.card in self.players[physical_owner].exile:
                    self.aura_exiles.setdefault(event['source'],[]).append((physical_owner,item.card))
                self.log('aura_exile','Aura temporarily exiles its chosen creature.',
                         actor=event['controller'],source=event['source'],targetPermanent=item.card.id)
                self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='linked_exile_entry':
                game=self.event_game('main')
                legal=next(((owner,item) for owner,item in self.creature_targets(event['controller'],card)
                            if item.card.id==event.get('target')
                            and (event['targetRestriction']!='opponent' or owner!=event['controller'])),None)
                if legal is None:
                    self.log('linked_exile_fizzle','Linked exile trigger has no legal target.',
                             source=event['source'],targetPermanent=event.get('target'))
                    continue
                owner,item=legal
                self.send_to_destination(self.players[owner],item,snapshot=game,to_exile=True)
                physical_owner=self.card_owners.get(root(item.card),owner)
                if item.card in self.players[physical_owner].exile:
                    key=(event['source'],event['sourceEntry'])
                    self.linked_exiles.setdefault(key,[]).append((physical_owner,item.card))
                self.log('linked_exile','ETB trigger exiles a creature.',
                         actor=event['controller'],source=event['source'],targetPermanent=item.card.id)
                self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='linked_exile_return':
                key=(event['source'],event['sourceEntry'])
                for owner_seat,exiled_card in self.linked_exiles.pop(key,()):
                    owner=self.players[owner_seat]
                    if exiled_card in owner.exile:
                        owner.exile.remove(exiled_card)
                        pending=self.enter_creature(exiled_card,owner)
                        self.resolve_entry_triggers(pending,exiled_card)
                self.log('linked_exile_return','Linked leave trigger returns any exiled card.',
                         source=event['source'])
                continue
            if event.get('operation')=='damage_any_target':
                if event.get('optional') and not self.choose_optional_damage(event):
                    self.log('damage_declined','Controller declines optional triggered damage.',
                             actor=event['controller'],source=event['source'])
                    continue
                game=self.event_game('main');kind=event.get('targetKind');target=event.get('target')
                amount=event['amount'];legal=False
                if kind=='player' and isinstance(target,int) and 0<=target<len(self.players):
                    self.players[target].life-=amount;legal=True
                elif kind=='permanent':
                    state=game.battlefield.get(target)
                    item=next((p for player in self.players for p in player.battlefield if p.card.id==target),None)
                    if (state and item and (game.creature(state) or 'Planeswalker' in state.definition.types)
                            and not game.has(state,'shroud')
                            and (state.controller==event['controller'] or not game.has(state,'hexproof'))
                            and not game.protected(state,event.get('sourceColors',()))):
                        legal=True
                        if game.creature(state):
                            item.marked_damage+=amount
                            if event.get('lastDeathtouch') and amount>0:
                                item.marked_damage=max(item.marked_damage,game.stats(state)[1])
                        elif item.loyalty is not None:item.loyalty=max(0,item.loyalty-amount)
                        else:raise RuntimeError('Planeswalker target has no loyalty')
                if legal and event.get('lastLifelink') and amount>0:self.gain_life(event['controller'],amount)
                self.log('damage_any_target' if legal else 'damage_any_target_fizzle',
                         'Optional damage trigger '+('resolves.' if legal else 'has no legal target.'),
                         actor=event['controller'],source=event['source'],target=target,targetKind=kind,
                         amount=amount if legal else 0)
                if legal:
                    self.resolve_entry_triggers(self.state_based_actions(),card)
                    self.outcome()
                    if self.finished:return
                continue
            if event.get('operation')=='combat_target_boost':
                game=self.event_game('combat');target=game.battlefield.get(event.get('target'))
                legal=bool(target and target.controller==event['controller'] and game.creature(target)
                           and (game.enchanted(target) or 'Enchantment' in target.definition.types)
                           and not game.has(target,'shroud')
                           and not game.protected(target,event.get('sourceColors',())))
                if legal:
                    target.temporary_power+=event['amount']
                    target.temporary_toughness+=event['boostToughness']
                    game.grant_temporary(target,event['boostKeyword'])
                    self.sync_events(game)
                self.log('combat_boost' if legal else 'combat_boost_fizzle',
                         'Beginning-of-combat target bonus '+('resolves.' if legal else 'has no legal target.'),
                         actor=event['controller'],source=event['source'],targetPermanent=event.get('target'),
                         power=event['amount'],toughness=event['boostToughness'],keyword=event['boostKeyword'])
                continue
            if event.get('operation')=='grant_target_keywords':
                from oracle_abilities import KEYWORDS
                keywords=event.get('keywords',[])
                if not keywords or any(ability not in KEYWORDS for ability in keywords):
                    raise RuntimeError('Malformed target keyword grant')
                game=self.event_game('combat');target=game.battlefield.get(event.get('target'))
                legal=bool(target and target.controller==event['controller']
                           and game.creature(target) and target.definition.legendary==event['legendary']
                           and not game.has(target,'shroud')
                           and not game.protected(target,event.get('sourceColors',())))
                if legal:
                    for ability in keywords:game.grant_temporary(target,ability)
                    self.sync_events(game)
                self.log('target_keywords' if legal else 'target_keywords_fizzle',
                         'Attack-triggered keyword grant '+('resolves.' if legal else 'has no legal target.'),
                         actor=event['controller'],source=event['source'],targetPermanent=event.get('target'),
                         keywords=keywords)
                continue
            if event.get('operation')=='grant_team_keywords':
                keywords=event.get('keywords',[])
                from oracle_abilities import KEYWORDS
                if not keywords or any(k not in KEYWORDS for k in keywords):
                    raise RuntimeError('Malformed team keyword grant')
                game=self.event_game('combat')
                for member in game.battlefield.values():
                    if member.controller==event['controller'] and game.creature(member):
                        for ability in keywords:game.grant_temporary(member,ability)
                self.sync_events(game)
                self.log('team_keywords','Attack grants keywords to controlled creatures.',
                         actor=event['controller'],source=event['source'],keywords=keywords)
                continue
            if event.get('operation')=='attacker_loses_flying':
                game=self.event_game('combat');target=game.battlefield.get(event.get('target'))
                if target:
                    target.lost_abilities['flying']=game.timestamp()
                    self.sync_events(game)
                self.log('flying_removed','A flying attacker loses flying until end of turn.',
                         actor=event['controller'],targetPermanent=event.get('target'),source=event['source'])
                continue
            if event.get('operation')=='attacker_damage':
                game=self.event_game('combat');target=game.battlefield.get(event.get('target'))
                amount=event['amount'];dealt=0
                if target and not game.protected(target,event.get('sourceColors',())):
                    item=next((p for player in self.players for p in player.battlefield
                               if p.card.id==target.id),None)
                    if item:
                        item.marked_damage+=amount;dealt=amount
                self.log('attacker_damage','An enchantment damages a flying attacker.',
                         actor=event['controller'],targetPermanent=event.get('target'),
                         amount=dealt,source=event['source'])
                self.resolve_entry_triggers(self.state_based_actions(),card)
                continue
            if event.get('operation')=='return_controlled_land':
                player=self.players[event['controller']]
                lands=[p for p in player.battlefield if p.card.kind=='land' or p.card.event_definition and 'Land' in p.card.event_definition.types]
                # This instruction does not target. Choose only on resolution,
                # preferring another tapped land over the returning source.
                chosen=min(lands,key=lambda p:(p.card.id==event['source'],not p.tapped,p.card.id),default=None)
                if chosen:
                    self.send_to_destination(player,chosen,to_hand=True)
                    self.log('return_land',f'{chosen.card.name} returns to its owner hand.',actor=event['controller'],card=chosen.card.name)
                continue
            minimum=event.get('minLands',0)
            if minimum and self.controlled_land_count(event['controller'])<minimum:
                self.log('condition_failed','Intervening upkeep land threshold no longer holds.',
                         actor=event['controller'],source=event['source'],minimumLands=minimum)
                continue
            if event.get('operation')=='create_chosen_role':
                self.resolve_chosen_role(event)
                continue
            if event.get('operation')=='create_role':
                self.resolve_role(event)
                continue
            if event.get('operation')=='ordered_effects':
                for part in event['steps']:
                    self._resolve_entry_effects([{**event,**part}],card)
                    if self.finished:return
                continue
            if event.get('operation')=='scry':
                seat=event['controller'];owner=self.players[seat]
                count=min(max(0,int(event.get('amount',1))),len(owner.library))
                # A single scry N looks at N *distinct* top cards before choosing.
                # The library uses its last element as its top. Never put card
                # identities or chosen order into the public replay.
                looked=list(owner.library[-count:]) if count else []
                to_bottom=[];kept=[]
                for top in looked:
                    (to_bottom if self.choose_scry_bottom(seat,top) else kept).append(top)
                if to_bottom:
                    del owner.library[-count:]
                    owner.library[:0]=to_bottom
                    owner.library.extend(kept)
                self.log('scry',f"Player {seat+1} scries {count}, keeping {len(kept)} on top.",
                         actor=seat,source=event['source'],operation='scry',
                         amount=count,movedToBottom=len(to_bottom))
                continue
            if event.get('operation')=='surveil':
                seat=event['controller'];owner=self.players[seat]
                count=min(max(0,int(event.get('amount',1))),len(owner.library))
                looked=list(owner.library[-count:]) if count else []
                sent=[];kept=[]
                # All choices are made over the same N cards. A single card
                # cannot be inspected repeatedly after another one is kept.
                for top in looked:
                    (sent if self.choose_surveil_graveyard(seat,top) else kept).append(top)
                if sent:
                    del owner.library[-count:]
                    owner.library.extend(kept)
                    owner.graveyard.extend(sent)
                self.log('surveil',f"Player {seat+1} surveils {count}, keeping {len(kept)} on top.",
                         actor=seat,source=event['source'],operation='surveil',
                         amount=count,movedToGraveyard=len(sent))
                continue
            if event.get('operation')=='mill_cards':
                controller=event['controller'];scope=event.get('recipient','controller')
                seats=([controller] if scope=='controller' else
                       [seat for seat in range(len(self.players)) if seat!=controller] if scope=='each opponent'
                       else list(range(len(self.players))) if scope=='each player' else None)
                if seats is None:raise ValueError('Unsupported mill recipient; cannot execute incomplete Oracle instruction.')
                counts={}
                for seat in seats:
                    owner=self.players[seat];cards=min(max(0,int(event['amount'])),len(owner.library))
                    for _ in range(cards):owner.graveyard.append(owner.library.pop())
                    counts[str(seat)]=cards
                self.log('mill',f"Players mill cards from the top of their libraries.",
                         actor=controller,source=event['source'],operation='mill_cards',
                         amount=event['amount'],recipient=scope,milledCounts=counts)
                continue
            if event.get('operation')=='draw_cards':
                if event.get('optional') and not self.choose_optional_draw(event):continue
                for _ in range(event['amount']):self.draw(event['controller'])
                self.log('draw_trigger',f"{event['name']}: its controller draws {event['amount']} card(s).",actor=event['controller'],source=event['source'],amount=event['amount'])
                self.outcome()
                if self.finished:return
                continue
            if event.get('operation')=='opponent_loss_tapped_creatures':
                game=self.event_game('main')
                controller=event['controller']
                amount=sum(item.tapped and item.card.id in game.battlefield and
                           game.creature(game.battlefield[item.card.id])
                           for item in self.players[controller].battlefield)
                for opponent in range(len(self.players)):
                    if opponent!=controller:self.players[opponent].life-=amount
                self.log('end_step_life_loss','Tapped creatures determine end-step life loss.',
                         actor=controller,source=event['source'],amount=amount)
                self.outcome()
                if self.finished:return
                continue
            if event.get('operation')=='return_graveyard':
                subtype=event.get('libraryFilter',())
                if len(subtype)!=2 or subtype[0]!='subtype':raise RuntimeError('Malformed graveyard return trigger')
                targets=self.graveyard_subtype_targets(event['controller'],subtype[1])
                chosen=next((c for c in targets if c.id==event.get('target')),None)
                if chosen and self.choose_optional_graveyard_return(event['controller'],subtype[1],targets):
                    player=self.players[event['controller']]
                    player.graveyard.remove(chosen);player.hand.append(chosen)
                    self.log('graveyard_return','Upkeep returns a target subtype card from graveyard to hand.',
                             actor=event['controller'],card=chosen.name,source=event['source'])
                else:
                    self.log('return_declined','Graveyard return declined or target illegal.',
                             actor=event['controller'],source=event['source'])
                continue
            if event.get('operation')=='optional_put_hand_permanent':
                payload=event.get('libraryFilter',())
                if len(payload)!=3 or payload[0]!='subtype':
                    raise RuntimeError('Unknown hand-to-battlefield permission')
                controller=event['controller'];subtype,kind=payload[1:]
                options=self.legal_hand_put_cards(controller,subtype,kind)
                selected=self.choose_optional_hand_permanent(controller,subtype,kind,options)
                if selected is None:
                    self.log('hand_put_declined','Player declines the optional hand-to-battlefield ability.',
                             actor=controller,source=event['source'],subtype=subtype)
                    continue
                if selected not in options:raise ValueError('Illegal hand-to-battlefield choice')
                player=self.players[controller]
                player.hand.remove(selected)
                pending=self.enter_creature(selected,player)
                self.log('put_from_hand','A matching permanent enters from hand without being cast.',
                         actor=controller,card=selected.name,source=event['source'],
                         subtype=subtype,restriction=kind,permanent=selected.id)
                self.resolve_entry_triggers(pending,selected)
                continue
            if event.get('operation')=='optional_subtype_search_hand':
                search=event.get('libraryFilter',())
                if len(search)!=2 or search[0]!='subtype':
                    raise RuntimeError('Unsupported subtype library-search filter')
                self.search_subtype_card_to_hand(event['controller'],card,search[1])
                continue
            if event.get('operation')=='equipment_basic_search':
                self.search_basic_land_tapped(event['controller'],
                    Card(event['source'],event['name'],'equipment'))
                continue
            if event.get('operation')=='opponent_optional_basic_search':
                # Ability controller does not search; only opponents do.
                # Under the current two-seat diagnostic model this is one
                # opponent, but the rule is represented independently of its
                # source's name or whether the source survives resolution.
                for opponent in range(len(self.players)):
                    if opponent!=event['controller']:
                        self.search_basic_land_tapped(opponent,card)
                continue
            if event.get('operation')=='transport':
                source=next((p for player in self.players for p in player.battlefield if p.card.id==event['source']),None)
                if source:
                    if event['kind']=='crew':source.animated=True
                    else:source.saddled=True
                self.log('transport_resolve','Transport activation resolves.',source=event['source'],ability=event['kind'])
                continue
            if event.get('operation')=='station':
                game=self.event_game('main');station=game.battlefield.get(event['source']);helper=game.battlefield.get(event['helper'])
                amount=max(0,(game.stats(helper)[0] if game.creature(helper) else 0) if helper else event['lastPower'])
                if station:
                    added=game.counter_amount(station.id,amount,counter_type='charge')
                    station.charge_counters+=added
                    self.sync_events(game)
                else:added=0
                self.log('station','Station adds charge counters.',source=event['source'],amount=added)
                continue
            if event.get('operation')=='combat_block_limit':
                if self.group_combat is not None and self.phase=='block':
                    current=self.group_combat.get('block_limit')
                    cap=event['maximum']
                    self.group_combat['block_limit']=min(current,cap) if current is not None else cap
                    self.log('combat_block_limit','Attack trigger restricts the defending player to a maximum number of blockers.',
                             source=event['source'],maximum=self.group_combat['block_limit'])
                continue
            if event.get('operation')=='history_tokens':
                amount=self.history_count(event['controller'],event['watch'])
                event=dict(event,operation='create_tokens',tokenSpec=dict(event['tokenSpec'],amount=amount))
            if event.get('operation')=='rebound':
                owner=event['controller'];p=self.players[owner];rebound_card=next((c for c in p.exile if root(c)==event['card']),None)
                if rebound_card:
                    choices=self.blink_choices(owner,rebound_card,'rebound_cast')
                    # A legal deterministic policy accepts a non-token target; otherwise declines.
                    usable=[c for c in choices if not next(item for item in p.battlefield if item.card.id==c.target_permanent).card.is_token]
                    if usable:
                        choice=max(usable,key=lambda c:sum(w*f for w,f in zip(self.policies[owner].weights,c.features)))
                        self._rebound_permission=(owner,root(rebound_card))
                        try:self.cast_spell(owner,rebound_card,target=choice.target_permanent,rebound=True)
                        finally:self._rebound_permission=None
                    else:self.log('rebound_declined','No chosen legal non-token target; the spell remains exiled.',actor=owner)
                continue
            if event.get('operation')=='saddled_boost':
                game=self.event_game('combat');source=game.battlefield.get(event['source'])
                if source:source.temporary_power+=event['power'];source.temporary_toughness+=event['toughness'];game.grant_temporary(source,event['keyword']);self.sync_events(game)
                continue
            if event.get('operation')=='lose_abilities':
                game=self.event_game('main')
                affected=game.lose_opposing_abilities(event['controller'],event['abilities'])
                self.sync_events(game)
                self.log('lose_abilities',f"{event['name']} removes opposing abilities until end of turn.",
                         actor=event['controller'],affected=affected,abilities=event['abilities'])
                continue
            if event.get('operation')=='ward':
                frame=next((frame for frame in self.stack.items if frame.id==event['targetStack']),None)
                if frame is None:
                    self.log('ward_no_target',f"{event['name']}: the targeted object has already left the stack.")
                    continue
                payer=event['payer'];payment=self.payment(replace(card,mana_cost=event['cost']),seat=payer,spell_cost=False)
                if payment['paid']:
                    for permanent in self.players[payer].battlefield:
                        if permanent.card.id in payment['sources']:permanent.tapped=True
                    self.players[payer].mana_pool=list(payment['pool'])
                    self.log('ward_paid',f"Player {payer+1} pays {event['cost']} for ward.",actor=payer,
                             cost=event['cost'],targetStack=frame.id,manaSources=payment['sources'],manaPool=list(payment['pool']))
                else:
                    removed=self.counter_stack_item(frame)
                    self.log('ward_counter' if removed else 'ward_counter_prevented',
                             f"{event['name']} counters {frame.label} because ward was not paid."
                             if removed else 'Spell cannot be countered by ward.',
                             actor=event['controller'],cost=event['cost'],targetStack=frame.id)
                continue
            if event.get('operation')=='reveal_creatures':
                owner=self.players[event['controller']]
                count,subtype,maximum=event['libraryFilter']
                revealed=list(reversed(owner.library[-count:]))
                self.log('reveal',f"{event['name']} reveals {len(revealed)} cards.",actor=event['controller'],
                         revealed=[dict(id=c.id,name=c.name) for c in revealed])
                selected=[]
                for candidate in revealed:
                    if 'Creature' not in candidate.printed_types or subtype not in candidate.land_subtypes:continue
                    if candidate.printed_mana_value is None:
                        self.pause('Cannot determine revealed creature mana value',candidate);return
                    if candidate.printed_mana_value<=maximum:
                        if candidate.kind!='creature' or (candidate.event_definition and not candidate.event_definition.supported):
                            self.pause('Revealed matching creature needs rules before it can enter',candidate);return
                        selected.append(candidate)
                for candidate in revealed:owner.library.remove(candidate)
                bottom=[candidate for candidate in revealed if candidate not in selected]
                self.library_random_sequence+=1
                random.Random(str(self.seed)+':library:'+str(self.library_random_sequence)).shuffle(bottom)
                owner.library[0:0]=bottom
                pending=self.enter_creatures(selected,owner)
                self.log('library_to_battlefield',f"{event['name']} puts {len(selected)} matching creatures onto the battlefield together.",
                         actor=event['controller'],entered=[c.id for c in selected],bottomedCount=len(bottom))
                self.resolve_entry_triggers(pending,card)
                if self.finished:return
                continue
            if event.get('operation')=='greatest_power_boost':
                game=self.event_game('combat');source=game.battlefield.get(event['source'])
                if source:
                    amount=max((game.stats(other)[0] for other in game.battlefield.values()
                                if other.controller==source.controller and game.creature(other)),default=0)
                    source.temporary_power+=event['power']*amount
                    source.temporary_toughness+=event['toughness']*amount
                    self.sync_events(game)
                self.log('greatest_power_boost',f"{event['name']} resolves its greatest-power attack bonus.",
                         source=event['source'],amount=amount if source else 0)
                continue
            if event.get('operation')=='subtype_count_boost':
                game=self.event_game('combat');source=game.battlefield.get(event['source'])
                if source:
                    count=sum(other.id!=source.id and other.controller==source.controller and event['subtype'] in other.definition.subtypes
                              for other in game.battlefield.values())
                    source.temporary_power+=event['power']*count;source.temporary_toughness+=event['toughness']*count
                    self.sync_events(game)
                self.log('subtype_count_boost',f"{event['name']} resolves its temporary attack bonus.",source=event['source'])
                continue
            if event.get('operation')=='attacking_subtype_boost':
                game=self.event_game('combat');source=game.battlefield.get(event['source'])
                count=0
                if source:
                    # The simulator's combat membership is authoritative; its
                    # EventGame adapter does not persist the attacking field.
                    attackers=set(self.group_combat['attackers']) if self.group_combat else (
                        {self.pending} if self.pending else set())
                    count=sum(other.id!=source.id and other.id in attackers and
                              game.creature(other) and event['subtype'] in other.definition.subtypes
                              for other in game.battlefield.values())
                    source.temporary_power+=event['power']*count
                    source.temporary_toughness+=event['toughness']*count
                    self.sync_events(game)
                self.log('attacking_subtype_boost','Attack bonus resolves using other attacking creatures.',
                         source=event['source'],count=count,subtype=event['subtype'])
                continue
            if event.get('operation')=='counter_power_tokens':
                game=self.event_game('main')
                source=game.battlefield.get(event['source'])
                if source is not None:
                    source.counters+=game.counter_amount(source.id,event['counterAmount'])
                    amount=max(0,game.stats(source)[0])
                    self.sync_events(game)
                else: amount=max(0,event['lastPower'])
                event=dict(event,operation='create_tokens',tokenSpec=dict(event['tokenSpec'],amount=amount))
            if event.get('operation')=='modal_attack_tokens':
                game=self.event_game('combat')
                attacking=(self.group_combat['attackers'] if self.group_combat else ())
                others=[game.battlefield[identifier] for identifier in attacking
                        if identifier!=event['source'] and identifier in game.battlefield
                        and game.creature(game.battlefield[identifier])]
                mode=event['mode']
                if mode not in (0,1):raise RuntimeError('Invalid attack mode')
                spec=dict(event['tokenSpec'])
                if mode==0:
                    amount=max((game.stats(creature)[0] for creature in others),default=0)
                    spec.update(power=max(0,amount),toughness=max(0,amount),amount=1)
                else:spec['amount']=len(others)
                event=dict(event,operation='create_tokens',tokenSpec=spec)
            if event.get('operation')=='tribal_tap_tokens':
                game=self.event_game('main')
                amount=sum(state.controller==event['controller'] and event['subtype'] in state.definition.subtypes
                           for state in game.battlefield.values())
                event=dict(event,operation='create_tokens',tokenSpec=dict(event['tokenSpec'],amount=amount))
            if event.get('operation')=='upkeep_token_rule':
                game=self.event_game('main')
                source=game.battlefield.get(event['source'])
                if event['condition']=='enchanted' and (source is None or not game.enchanted(source)):
                    self.log('upkeep_condition_failed','Intervening-if enchanted condition failed at resolution.',
                             actor=event['controller'],source=event['source'])
                    continue
                amount=event['tokenSpec']['amount']
                if event['countSubtype']:
                    count=sum(permanent.controller==event['controller'] and game.creature(permanent)
                              and event['countSubtype'] in permanent.definition.subtypes
                              for permanent in game.battlefield.values())
                    amount=count//event['divisor']
                event=dict(event,operation='create_tokens',tokenSpec=dict(event['tokenSpec'],amount=amount))
            if event.get("operation") == "create_tokens":
                if event.get('requiresBuffedCreature') and not self.event_game('main').controlled_creature_above_base(event['controller']):
                    self.log('end_step_condition_failed','Intervening-if condition no longer holds at resolution.',
                             actor=event['controller'],source=event['source'])
                    continue
                if event.get('optional') and not self.choose_optional_token_creation(event):
                    self.log('token_creation_declined','Optional token creation declined.',
                             actor=event['controller'],source=event['source'])
                    continue
                game=self.event_game('main')
                spec=game.replace_creature_token_spec(event['controller'],event["tokenSpec"])
                owner=self.players[event["controller"]]
                pending=[]
                owner.life -= event.get("controllerLoss",0)
                created=game.token_amount(event['controller'],spec['amount'])
                event=dict(event,tokenSpec=dict(spec,amount=created))
                for _ in range(created):
                    self.token_sequence+=1
                    definition=EventDefinition(" ".join(spec["subtypes"]),frozenset({"Creature"}|({"Land"} if spec.get("land") else set())|({"Enchantment"} if spec.get("enchantment") else set())),frozenset(spec["subtypes"]),
                        False,spec["power"],spec["toughness"],frozenset(spec["keywords"]),colors=frozenset(spec["colors"]),pilot_bonus=spec.get("contribution_bonus",0))
                    token=Card(f"token-{self.token_sequence}",definition.name,"creature",
                        traits=f"{definition.power};{definition.toughness};"+",".join(sorted(definition.abilities)),
                        power=definition.power,toughness=definition.toughness,event_definition=definition,is_token=True)
                    pending.extend(self.enter_creature(token,owner))
                    created_permanent=next(p for p in owner.battlefield if p.card.id==token.id)
                    created_permanent.tapped=spec["tapped"]
                    if spec.get('temporary_haste') or spec.get('must_attack_this_combat'):
                        grants=set(created_permanent.temporary_abilities)
                        if spec.get('temporary_haste'):grants.add('haste')
                        if spec.get('must_attack_this_combat'):grants.add('must_attack')
                        created_permanent.temporary_abilities=frozenset(grants)
                    if spec.get('attacking') and event['controller']==self.active and self.group_combat is not None:
                        self.group_combat['attackers'].append(token.id)
                self.log("upkeep" if event.get("event")=="upkeep" else "trigger",
                         f"{event['name']}: controller loses {event.get('controllerLoss',0)} life and creates {spec['amount']} creature tokens.",actor=event["controller"],
                         **{k:v for k,v in event.items() if k!="kind"})
                self.outcome()
                if self.finished: return
                pending.extend(self.event_game('main').token_action_events('create',event['controller'],created))
                self.resolve_entry_triggers(pending,card)
                if self.finished: return
                continue
            elif event.get('operation')=='attach':
                source=next((p for p in self.players[event['controller']].battlefield if p.card.id==event['source']),None)
                game=self.event_game('main')
                target=game.battlefield.get(event['target'])
                if event.get('equipTargetType')=='planeswalker':
                    valid=bool(source and target and target.controller==event['controller']
                               and 'Planeswalker' in target.definition.types
                               and not game.has(target,'shroud')
                               and not game.protected(target,source.card.colors))
                else:
                    valid=bool(source and event['target'] in {p.card.id for owner,p in
                                 self.creature_targets(event['controller'],source.card)
                                 if owner==event['controller']})
                if valid and source.attached_to!=event['target']:
                    source.attached_to=event['target']
                    self.effect_clock+=1;source.attachment_at=self.effect_clock
                message=f"{event['name']}: equip ability resolves."
            elif event.get('operation') in ('enchanted_counters','enchanted_double_counters'):
                aura=next((item for player in self.players for item in player.battlefield
                           if item.card.id==event['source']),None)
                game=self.event_game('main')
                target_id=aura.attached_to if aura else None
                if target_id and target_id in game.battlefield and game.creature(game.battlefield[target_id]):
                    target=next(item for player in self.players for item in player.battlefield if item.card.id==target_id)
                    amount=(target.counters if event['operation']=='enchanted_double_counters'
                            else event['amount'])
                    target.counters+=game.counter_amount(target_id,amount)
                    message=f"{event['name']}: enchanted creature receives counters."
                else:
                    message=f"{event['name']}: no currently enchanted creature."
            elif event.get('operation')=='self_counter':
                if event.get('optional') and not self.choose_optional_self_counter(event):
                    message=f"{event['name']}: its controller declines the counter."
                    self.log('counter_declined',message,actor=event['controller'],source=event['source'])
                    continue
                amount=(event.get('alternateAmount') or event['amount']) if set(event.get('counterSubtypes',())).intersection(event.get('deadSubtypes',())) else event['amount']
                source=next((item for player in self.players for item in player.battlefield if item.card.id==event['source']),None)
                if source:
                    game=self.event_game('main')
                    source.counters+=game.counter_amount(source.card.id,amount)
                message=f"{event['name']}: its surviving source receives {amount} counter(s)."
            elif event.get('operation')=='discard':
                target=self.players[event['target']]
                if target.hand:
                    discarded=target.hand.pop()
                    target.graveyard.append(discarded)
                    message=f"{event['name']}: Player {event['target']+1} discards {discarded.name}."
                else: message=f"{event['name']}: damaged player has no cards to discard."
            elif event.get("operation") == "add_counters":
                game = self.event_game("main")
                affected = []
                for identifier,permanent in game.battlefield.items():
                    if permanent.controller == event["controller"] and (event["counterSubtype"] in permanent.definition.subtypes if event.get("counterSubtype") else game.creature(permanent)):
                        permanent.counters += game.counter_amount(identifier,event["amount"])
                        affected.append(identifier)
                self.sync_events(game)
                message = f"{event['name']} puts {event['amount']} +1/+1 counters on each of {len(affected)} creatures."
            elif event.get('operation')=='damage_board':
                game=self.event_game('main');source=game.battlefield.get(event['source'])
                lifelink=game.has(source,'lifelink') if source else event.get('lastLifelink',False)
                touch=game.has(source,'deathtouch') if source else event.get('lastDeathtouch',False)
                targets=[(owner,item) for owner,player in enumerate(self.players) if owner!=event['controller']
                         for item in player.battlefield if item.card.id in game.battlefield
                         and (game.creature(game.battlefield[item.card.id]) or 'Planeswalker' in game.battlefield[item.card.id].definition.types)]
                if any('Planeswalker' in game.battlefield[item.card.id].definition.types and item.loyalty is None for _,item in targets):
                    self.pause('Cannot apply board damage without planeswalker loyalty',card);return
                opponent=1-event['controller'];amount=event['amount']
                self.players[opponent].life-=amount
                self.record_player_damage(opponent,event.get('source'),amount)
                prevented={item.card.id for _,item in targets if game.protected(game.battlefield[item.card.id],event.get('sourceColors',card.colors))}
                for _,item in targets:
                    if item.card.id in prevented:continue
                    state=game.battlefield[item.card.id]
                    if game.creature(state):item.marked_damage+=amount
                    if 'Planeswalker' in state.definition.types:item.loyalty=max(0,item.loyalty-amount)
                if lifelink:self.gain_life(event['controller'],amount*(len(targets)-len(prevented)+1))
                dead=[]
                for owner,item in targets:
                    state=game.battlefield[item.card.id]
                    zero_loyalty='Planeswalker' in state.definition.types and item.loyalty==0
                    lethal=game.creature(state) and not game.has(state,'indestructible') and (touch and item.card.id not in prevented or item.marked_damage>=game.stats(state)[1])
                    if zero_loyalty or lethal:dead.append((owner,item))
                self.log('damage_board',f"{event['name']} deals {amount} damage to the opposing player and their creatures and planeswalkers.",
                         actor=event['controller'],damaged=[item.card.id for _,item in targets],amount=amount,
                         prevented=sorted(prevented),loyaltyAfter={item.card.id:item.loyalty for _,item in targets if 'Planeswalker' in game.battlefield[item.card.id].definition.types})
                aura_damage=[dict(source=event['source'],target=None,amount=amount)]
                aura_damage.extend(dict(source=event['source'],target=item.card.id,amount=amount)
                                   for _,item in targets if item.card.id not in prevented)
                pending_aura=game.aura_damage_triggers(aura_damage,opponent)
                self.destroy_batch(dead,card,reason='damage_deaths')
                if pending_aura:self.resolve_entry_triggers(pending_aura,card)
                self.outcome()
                if self.finished:return
                continue
            elif event.get("operation") == "damage":
                target = 1-event["controller"]
                self.players[target].life -= event["amount"]
                self.record_player_damage(target,event.get("source"),event["amount"])
                if event["amount"]>0:
                    game=self.event_game('main')
                    aura_events=game.aura_damage_triggers([dict(source=event['source'],target=None,amount=event['amount'])],target)
                    if aura_events:self.resolve_entry_triggers(aura_events,card)
                # Noncombat damage: never contributes to commander combat damage.
                message = f"{event['name']} deals {event['amount']} damage to Player {target+1}."
            elif event.get("operation") == "gain_life":
                source = event["controller"]
                self.gain_life(source,event["amount"])
                message = f"{event['name']} triggers: Player {source+1} gains {event['amount']} life."
            elif event.get("operation") == "lose_life":
                source = event["controller"]
                target = 1-source  # This diagnostic is explicitly two-player.
                self.players[target].life -= event["amount"]
                self.gain_life(source,event.get("gain",0))
                message = f"{event['name']} triggers: Player {target+1} loses {event['amount']} life."
            elif event.get("effect") == "scry":
                source = event["controller"]
                count = min(event["amount"],len(self.players[source].library))
                # A valid conservative choice: leave all viewed cards on top in
                # their current order. Never expose their identities to opponent.
                message = f"Player {source+1} scries {count}, keeping all on top."
            else:
                message = (f"{event['source']} makes {card.name} {event['effect']}."
                           if event.get("target") else f"{card.name}: {event['effect']}.")
            self.log("trigger", message, actor=event.get("controller",self.active),
                     **{k:v for k,v in event.items() if k != "kind"})
            self.outcome()
            if self.finished: return

    def strike_damage_step(self,first):
        context=self.combat_context
        def find(identifier):
            return next((p for player in self.players for p in player.battlefield if p.card.id==identifier),None)
        attacker=find(context['attacker']);blocker=find(context['blocker'])
        a=self.effective_card(attacker) if attacker else None
        b=self.effective_card(blocker) if blocker else None
        def has(card,keyword):return card is not None and keyword in card.traits.split(';')[-1].split(',')
        def eligible(card,identifier):
            return card is not None and (identifier in context['early'] if first else identifier not in context['early'] or has(card,'double strike'))
        hit_a=eligible(a,context['attacker']);hit_b=eligible(b,context['blocker'])
        to_blocker=to_attacker=to_player=0
        if hit_a:
            power=max(0,a.power)
            if b:
                lethal=max(0,b.toughness-blocker.marked_damage)
                if has(a,'deathtouch') and lethal>0:lethal=1
                to_blocker=min(power,lethal) if has(a,'trample') else power
                if has(a,'trample'):to_player=power-to_blocker
            elif not context['blocked'] or has(a,'trample'):to_player=power
        if hit_b and a:to_attacker=max(0,b.power)
        if attacker:attacker.marked_damage+=to_attacker
        if blocker:blocker.marked_damage+=to_blocker
        active=self.players[self.active];defender=self.players[1-self.active]
        if has(a,'lifelink'):self.gain_life(self.active,to_blocker+to_player)
        if has(b,'lifelink'):self.gain_life(1-self.active,to_attacker)
        defender.life-=to_player
        if attacker:self.record_player_damage(1-self.active,attacker.card.id,to_player)
        if attacker and root(attacker.card)==active.commander_id and to_player:
            defender.commander_damage[root(attacker.card)]=defender.commander_damage.get(root(attacker.card),0)+to_player
        game=self.event_game('combat');dead=[]
        for player in self.players:
            for item in player.battlefield:
                effective=self.effective_card(item)
                if effective is None:continue
                touch=(item is attacker and to_attacker>0 and has(b,'deathtouch')) or (item is blocker and to_blocker>0 and has(a,'deathtouch'))
                if effective.toughness<=0 or ((item.marked_damage>=effective.toughness or touch) and not game.has(game.battlefield[item.card.id],'indestructible')):
                    dead.append(item)
        dealt=[]
        if attacker and to_player:dealt.append(dict(source=attacker.card.id,target=None,amount=to_player))
        if attacker and blocker and to_blocker:dealt.append(dict(source=attacker.card.id,target=blocker.card.id,amount=to_blocker))
        if blocker and attacker and to_attacker:dealt.append(dict(source=blocker.card.id,target=attacker.card.id,amount=to_attacker))
        dead=[item for item in dead if not (
            self.replace_umbra_destruction(next(seat for seat,p in enumerate(self.players) if item in p.battlefield),item,game)
            or self.replace_regeneration(next(seat for seat,p in enumerate(self.players) if item in p.battlefield),item,game))]
        triggers=game.death_triggers([item.card.id for item in dead])
        triggers.extend(game.aura_damage_triggers(dealt,1-self.active))
        if to_player and attacker:
            triggers.extend(game.combat_draw_triggers(attacker.card.id))
            from oracle_abilities import matches, event_data
            for watcher in game.battlefield.values():
                for trigger in watcher.definition.triggers:
                    if trigger.event=='combat_damage' and matches(trigger.subject,watcher,game.battlefield[attacker.card.id],True):
                        ability=event_data(trigger,watcher,game.battlefield[attacker.card.id])
                        triggers.append(dict(ability,target=1-self.active))
        if attacker and attacker.card.name=='Zurgo Helmsmasher' and blocker in dead and to_blocker>0:
            triggers.append(dict(operation='self_counter',effect='add +1/+1 counter',amount=1,
                                 source=attacker.card.id,name=attacker.card.name,controller=self.active))
        for item in dead:
            owner=next(player for player in self.players if item in player.battlefield)
            self.send_to_destination(owner,item)
        self.log('combat_damage_step','First-strike damage resolves.' if first else 'Regular damage resolves.',
                 firstStrike=first,playerDamage=to_player,attackerDamage=to_attacker,blockerDamage=to_blocker,deaths=[item.card.id for item in dead])
        self.outcome()
        if not self.finished:
            for trigger in triggers:
                if trigger['effect']=='create tapped Squirrels':
                    trigger.update(operation='create_tokens',tokenSpec=dict(amount=trigger['amount'],power=1,toughness=1,colors=['Green'],subtypes=['Squirrel'],keywords=[],tapped=True,land=False))
            self.resolve_entry_triggers(triggers,attacker.card if attacker else Card('combat','Combat','spell'))
        if not self.finished and not self.manual_priority:
            self.stack.active=self.active;self.stack.priority=self.active
            self.drain_priority(empty_window=True)
        if first:self.phase='regular_damage'
        else:self.phase='second_main';self.pending=None;self.combat_context=None

    def create_treasures(self,seat,amount,tapped,source,triggers=()):
        """One noncreature-token event, with replacement count and token-action triggers."""
        game=self.event_game('main')
        created=game.token_amount(seat,amount)
        pending=list(triggers)
        for _ in range(created):
            self.token_sequence+=1
            definition=EventDefinition('Treasure',frozenset({'Artifact'}),
                frozenset({'Treasure'}),False,0,0,frozenset())
            token=Card(f'token-{self.token_sequence}','Treasure','artifact',
                       event_definition=definition,is_token=True)
            pending.extend(self.enter_creature(token,self.players[seat]))
            next(p for p in self.players[seat].battlefield if p.card.id==token.id).tapped=tapped
        pending.extend(self.event_game('main').token_action_events('create',seat,created))
        self.log('treasure_creation','Create Treasure artifact tokens after destruction.',
                 actor=seat,source=source.name,created=created,tapped=tapped)
        self.resolve_entry_triggers(pending,source)

    def activate_treasure_mana(self,seat,token_id,color):
        """Sacrifice an untapped Treasure as a mana ability, without using the stack."""
        if self.stack.priority!=seat or type(color) is not int or not 0<=color<5:
            raise ValueError('Illegal Treasure mana activation')
        token=next((p for p in self.players[seat].battlefield if p.card.id==token_id),None)
        if not token or token.tapped or not token.card.is_token or not token.card.event_definition or (
                'Artifact' not in token.card.event_definition.types or
                'Treasure' not in token.card.event_definition.subtypes):
            raise ValueError('Illegal Treasure mana source')
        self.sacrifice_token(seat,token_id)
        self.players[seat].mana_pool[color]+=1
        self.log('treasure_mana','Sacrificed a Treasure for one mana of the chosen color.',
                 actor=seat,source=token_id,color=mana_pool.COLORS[color])

    def sacrifice_token(self, seat: int, token_id: str):
        """Execute a token sacrifice AFTER a legal ability has paid its cost.

        This is an internal event helper, not a free legal player action:
        future sacrifice-cost grammars must validate permission and cost first.
        Sacrificed creature tokens also die, so death triggers are collected.
        """
        token=next((p for p in self.players[seat].battlefield if p.card.id==token_id),None)
        if token is None or not token.card.is_token:
            raise ValueError('Token sacrifice requires a controlled token')
        game=self.event_game('main')
        events=game.token_action_events('sacrifice',seat,1)
        state=game.battlefield.get(token_id)
        if state and game.creature(state):events.extend(game.death_triggers([token_id]))
        self.send_to_destination(self.players[seat],token,snapshot=game)
        self.log('token_sacrifice','A token is sacrificed as an ability cost.',actor=seat,token=token_id)
        self.resolve_entry_triggers(events,token.card)

    def send_to_destination(self, player: Player, item: Permanent, snapshot=None, to_exile=False, to_hand=False):
        # A card enters the graveyard only if its zone move actually says so.
        # Damage, blink/exile, return-to-hand, and the command-zone option
        # must never be confused with one another.
        destination=self.players[self.card_owners.get(root(item.card),
            next(i for i,p in enumerate(self.players) if p is player))]
        to_graveyard=not (to_exile or to_hand or root(item.card)==destination.commander_id)
        if to_graveyard:
            # The Equipment's leave/death trigger sees its predeath attachment.
            for controller,owner in enumerate(self.players):
                for equip in owner.battlefield:
                    definition=equip.card.event_definition
                    if equip.attached_to==item.card.id and definition and definition.equipment_return_dying:
                        victim_owner=self.card_owners.get(root(item.card),
                            next(i for i,p in enumerate(self.players) if p is player))
                        self._waiting_triggers.append((dict(
                            operation='return_dead_equipped',source=equip.card.id,
                            controller=controller,name=equip.card.name,
                            victim=item.card.id,victimOwner=victim_owner),equip.card))
            if item.card.event_definition and item.card.event_definition.aura_graveyard_draw:
                controller=next(seat for seat,owner in enumerate(self.players) if owner is player)
                self._waiting_triggers.append((dict(operation='draw_cards',effect='draw a card',
                    source=item.card.id,name=item.card.name,controller=controller,amount=1),item.card))
            from oracle_abilities import matches,event_data
            before=snapshot or self.event_game('main')
            moved=before.battlefield.get(item.card.id)
            if moved:
                for watcher in before.battlefield.values():
                    for trigger in watcher.definition.triggers:
                        if trigger.event=='graveyard' and matches(trigger.subject,watcher,moved,before.creature(moved)):
                            self._waiting_triggers.append((event_data(trigger,watcher,moved),item.card))
        if item.card.event_definition and item.card.event_definition.linked_exile:
            controller=next(seat for seat,owner in enumerate(self.players) if owner is player)
            self._waiting_triggers.append((dict(operation='linked_exile_return',
                source=item.card.id,sourceEntry=item.entered_at,controller=controller,
                name=item.card.name),item.card))
        if item.card.is_token:
            game=snapshot or self.event_game('main')
            controller=next(i for i,p in enumerate(self.players) if item in p.battlefield)
            # Leaves-the-battlefield abilities are queued from the state
            # immediately BEFORE the token exits, independent of the cause.
            self._waiting_triggers.extend((event,item.card) for event in game.token_leave_events(controller,1))
        for event,_ in [frame.payload for frame in self.stack.items]+self._waiting_triggers:
            if event.get('operation')=='station' and event.get('helper')==item.card.id:
                game=snapshot or self.event_game('main')
                if item.card.id in game.battlefield:event['lastPower']=game.stats(game.battlefield[item.card.id])[0] if game.creature(game.battlefield[item.card.id]) else 0
            if event.get('operation')=='damage_board' and event.get('source')==item.card.id:
                game=snapshot or self.event_game('main');state=game.battlefield.get(item.card.id)
                if state:
                    event['lastLifelink']=game.has(state,'lifelink');event['lastDeathtouch']=game.has(state,'deathtouch')
            if event.get('operation')=='mentor_counter' and event.get('source')==item.card.id:
                # Mentor uses the source's last-known power if it leaves
                # before the attack trigger resolves.
                game=snapshot or self.event_game('main')
                state=game.battlefield.get(item.card.id)
                if state and game.creature(state):event['sourcePower']=game.stats(state)[0]
            if event.get('operation')=='counter_power_tokens'  and event.get('source')==item.card.id:
                if snapshot and item.card.id in snapshot.battlefield:
                    event['lastPower']=snapshot.stats(snapshot.battlefield[item.card.id])[0]
                else:
                    effective=self.effective_card(item)
                    if effective:event['lastPower']=effective.power
        for owner_index,owner in enumerate(self.players):
            for attached in list(owner.battlefield):
                if attached.attached_to==item.card.id:
                    attached.attached_to=None
                    attached.bestowed=False
                    if attached.card.kind=='aura':
                        # Move the attached Aura through the same zone-change
                        # machinery so all graveyard and token-leave watchers
                        # see its departure exactly once.
                        self.send_to_destination(owner,attached,snapshot=snapshot)
        player.battlefield.remove(item)
        # The return is a linked zone change, not a death or a recast.
        # It happens immediately when the specific Aura leaves the battlefield.
        for owner_seat,exiled_card in self.aura_exiles.pop(item.card.id,()):
            owner=self.players[owner_seat]
            if exiled_card in owner.exile:
                owner.exile.remove(exiled_card)
                pending=self.enter_creature(exiled_card,owner)
                self._waiting_triggers.extend((trigger,exiled_card) for trigger in pending)
        if item.card.is_token:
            return  # Tokens cease to exist after leaving the battlefield.
        if root(item.card) == destination.commander_id:
            destination.command_zone = item.card  # This prototype chooses the command-zone option.
        elif to_hand:
            destination.hand.append(item.card.modal_front_face or item.card)
        elif to_exile:
            destination.exile.append(item.card.modal_front_face or item.card)
        else:
            destination.graveyard.append(item.card.modal_front_face or item.card)

    def log(self, kind: str, message: str, **details):
        self.invariant()
        event={"index": len(self.events), "turn": self.turn,
               "phase": self.phase, "actor": details.pop("actor", self.active),
               "kind": kind, "message": message, "details": details, "state": self.state()}
        if self.diagnostic:
            # Spectator-only recording, NEVER returned by state(), policy
            # observation, or legal-action generation. It intentionally
            # reveals BOTH hands in a saved diagnostic replay, not libraries.
            event["spectatorHands"]=[
                [{"id":card.id,"name":card.name} for card in p.hand]
                for p in self.players]
        self.events.append(event)

    def pause(self, reason: str, card: Card | None = None):
        self.questions.append({"id": f"runtime-{self.turn}-{len(self.questions)}", "status": "open",
                               "blocking": True, "card": card.name if card else "",
                               "reason": reason, "question": "How should the engine resolve: " + reason + "?",
                               "answer": None})
        self.finished, self.result = True, "blocked"
        self.log("question", "Paused for human rules review: " + reason)

    def draw(self, seat: int):
        p = self.players[seat]
        if not p.library:
            p.failed_draw = True
            self.log("failed_draw", f"Player {seat + 1} cannot draw from an empty library.", actor=seat)
            return
        p.hand.append(p.library.pop())
        # The card's identity is private; observers and the other AI get only the count.
        self.log("draw", f"Player {seat + 1} draws one card.", actor=seat)

    def outcome(self):
        dead = [p.life <= 0 or p.failed_draw or any(value >= 21 for value in p.commander_damage.values())
                for p in self.players]
        if any(dead):
            self.finished = True
            self.winner = None if all(dead) else (1 if dead[0] else 0)
            self.result = "draw" if self.winner is None else "win"
            reasons = [["zero life" if p.life <= 0 else None, "failed draw" if p.failed_draw else None,
                        "21 commander damage" if any(v >= 21 for v in p.commander_damage.values()) else None]
                       for p in self.players]
            self.log("result", "Draw." if self.winner is None else f"Player {self.winner + 1} wins.",
                     lossReasons=[[r for r in row if r] for row in reasons])

    def land_play_limit(self, seat: int) -> int:
        # A land-play permission is continuous and cumulative. Losing its
        # source does not undo land plays already performed this turn.
        game=self.event_game('main')
        return 1+sum(state.definition.additional_land_plays
                     for state in game.battlefield.values() if state.controller==seat)

    def mana_sources(self, seat: int):
        sources=[]
        game=self.event_game('main')
        for item in self.players[seat].battlefield:
            if item.tapped: continue
            definition=item.card.event_definition
            state=game.battlefield.get(item.card.id)
            effective=state.definition if state else definition
            overridden=bool(state and getattr(state,'land_overridden',False))
            mask=(0 if overridden else item.card.mask) if item.card.kind=='land' else 0
            if effective and 'Land' in effective.types:
                mask|=sum(bit for subtype,bit in {'Plains':1,'Island':2,'Swamp':4,'Mountain':8,'Forest':16}.items()
                         if subtype in effective.subtypes)
                if 'Creature' in effective.types and item.fresh:
                    creature=self.effective_card(item,game)
                    if creature is None or 'haste' not in creature.traits.split(';')[-1].split(','): continue
            if item.card.kind=='land' and (mask or item.card.mana_production and not overridden):
                options=((item.card.mana_production,) if item.card.mana_production and not overridden else ()) + tuple(
                    tuple(int(i==color) for i in range(6)) for color in range(6) if mask&(1<<color))
            elif mask:
                options=tuple(tuple(int(i==color) for i in range(6)) for color in range(6) if mask&(1<<color))
            elif item.card.kind=='mana_artifact': options=(item.card.mana_production,)
            elif definition and definition.scaled_mana_tap:
                game=self.event_game('main');state=game.battlefield.get(item.card.id)
                if state is None or (game.creature(state) and item.fresh and not game.has(state,'haste')):continue
                count=sum(permanent.controller==seat and definition.scaled_mana_tap in permanent.definition.types
                          for permanent in game.battlefield.values())
                if not count:continue
                options=tuple(tuple(count if index==color else 0 for index in range(6)) for color in range(5))
            else: continue
            sources.append((item.card.id,options))
        return sources

    def payment(self, card: Card, tax: int = 0, x: int | None = None, seat: int | None = None,
                spell_cost: bool = True, excluded_sources: tuple[str, ...] = ()) -> dict:
        cost=card.mana_cost+(("{2}"*tax) if tax else "")
        seat=self.active if seat is None else seat
        player=self.players[seat]
        if spell_cost:
            types={word.lower() for word in card.printed_types}
            if card.event_definition:types.update(word.lower() for word in card.event_definition.types)
            # Printed subtypes live on Card even when the Java rules bridge
            # understands an otherwise plain spell without an EventDefinition.
            subtypes={word.lower() for word in card.land_subtypes}
            if card.event_definition:subtypes.update(word.lower() for word in card.event_definition.subtypes)
            if card.kind=='aura':subtypes.add('aura')
            colors={word.lower() for word in card.colors}
            categories=types|subtypes|{'subtype:'+word for word in subtypes}|colors|({'colorless'} if not colors else set())
            reduction=sum(amount for permanent in player.battlefield
                          if permanent.card.event_definition
                          for names,amount in permanent.card.event_definition.cost_reductions
                          if any(name in categories for name in names))
            cost=mana_pool.reduce_generic_cost(cost,reduction,x)
            # Class level 1 taxes opponents' spells only while the Class owner is active.
            if seat!=self.active:
                imposed=sum(item.card.event_definition.class_program[0]
                    for item in self.players[self.active].battlefield
                    if item.card.event_definition and item.card.event_definition.class_program)
                cost+=''.join('{1}' for _ in range(imposed))
        sources=[s for s in self.mana_sources(seat) if s[0] not in excluded_sources]
        any_color=any(p.card.mana_as_any_color for p in player.battlefield)
        return mana_pool.plan(cost,player.mana_pool,sources,x,spend_as_any_color=any_color)

    def damage(self, a: Card, b: Card | None) -> dict:
        return self.rules.query("combat", a.traits, b.traits if b else "",
                                self.players[self.active].life, self.players[1 - self.active].life)

    def activation_choices(self, seat: int, kinds: set[str]) -> list[Candidate]:
        """Offer a minimally costly legal crew/saddle activation without hiding card effects."""
        player = self.players[seat]
        result = []
        for permanent in player.battlefield:
            definition = permanent.card.event_definition
            if definition is None: continue
            for kind, threshold, already in (("crew",definition.crew,permanent.animated),
                                               ("saddle",definition.saddle,permanent.saddled)):
                if kind not in kinds or threshold is None or already: continue
                helpers = []
                for other in player.battlefield:
                    effective = self.effective_card(other)
                    if other.card.id != permanent.card.id and not other.tapped and effective:
                        helpers.append((other.card.id, effective.power+(other.card.event_definition.pilot_bonus if other.card.event_definition else 0)))
                options = []
                for n in range(1, min(len(helpers), 4)+1):
                    for group in itertools.combinations(helpers,n):
                        power = sum(entry[1] for entry in group)
                        if power >= threshold: options.append((n,power,tuple(entry[0] for entry in group)))
                    if options: break
                if not options: continue
                ids = min(options)[2]
                # Low base value: activate when useful; a defender may then choose to block.
                result.append(Candidate(f"{kind}:{permanent.card.id}",kind,permanent.card.id,
                    features(power=.2, **{"pass":.1}),kind.title()+" "+permanent.card.name,ids))
        return result

    def legal(self, seat: int) -> tuple[Candidate, ...]:
        p = self.players[seat]
        if self.diagnostic and self.phase=='attack':return self.group_attack_choices(seat)
        if self.group_combat is not None and self.phase=='block':return self.group_block_choices(seat)
        actions = []
        if self.phase == "land":
            if self.land_plays_this_turn < self.land_play_limit(seat):
                for c in p.hand:
                    if c.kind == "land":
                        actions.append(Candidate(c.id, "land", c.id, features(power=1), "Play " + c.name))
                    if c.modal_land_face is not None:
                        actions.append(Candidate(c.id+":back", "land_back", c.id,
                                                 features(power=1), "Play " + c.modal_land_face.name))
        elif self.phase in ("main", "second_main"):
            if self.land_plays_this_turn < self.land_play_limit(seat):
                actions.extend(Candidate(card.id,'land',card.id,features(power=1),label='Play '+card.name)
                               for card in p.hand if card.kind=='land')
                actions.extend(Candidate(card.id+':back','land_back',card.id,features(power=1),
                                         label='Play '+card.modal_land_face.name)
                               for card in p.hand if card.modal_land_face is not None)
            if self.diagnostic: actions.extend(self.activation_choices(seat, {"crew","saddle"}))
            actions.extend(self.special_choices(seat))
            actions.extend(self.enchantment_copy_choices(seat))
            actions.extend(self.class_level_choices(seat))
            actions.extend(self.equip_choices(seat))
            actions.extend(self.token_ability_choices(seat))
            actions.extend(self.scaled_mana_choices(seat))
            actions.extend(self.sacrifice_choices(seat))
            actions.extend(self.discard_token_choices(seat))
            actions.extend(self.sacrifice_team_choices(seat))
            actions.extend(self.sacrifice_protection_choices(seat))
            actions.extend(self.land_counter_choices(seat))
            actions.extend(self.land_animation_choices(seat))
            actions.extend(self.regenerate_choices(seat))
            actions.extend(self.strip_ability_choices(seat))
            if (self.diagnostic and p.command_zone and p.command_zone.kind == "creature"
                    and self.payment(p.command_zone, p.commander_casts)["paid"]):
                c = p.command_zone
                actions.append(Candidate(c.id, "cast_commander", c.id,
                    features(power=c.power, toughness=c.toughness, haste=int(c.name == "Zurgo Helmsmasher"),
                             cost=len(self.payment(c, p.commander_casts).get("sources", []))),
                    "Cast commander " + c.name))
            for c in p.graveyard:
                if c.flashback_cost and c.kind=='token_spell':
                    payment=self.payment(replace(c,mana_cost=c.flashback_cost),seat=seat)
                    if payment['paid']:
                        actions.append(Candidate(c.id+':flashback','cast_flashback',c.id,
                            features(power=c.token_count*(c.token_definition.power if c.token_definition else 1),
                                      cost=len(payment.get('sources',[]))),
                            label='Flashback '+c.name))
            for c in self.permitted_exile_cards(seat):
                if self.payment(c,seat=seat)['paid']:
                    actions.append(Candidate(c.id+':exile','cast_exile',c.id,
                        features=features(power=c.power,toughness=c.toughness,
                                          cost=len(self.payment(c,seat=seat).get('sources',[]))),
                        label='Cast exiled '+c.name))
            for c in p.hand:
                if c.kind=='graveyard_return_spell' and self.payment(c)['paid']:
                    actions.extend(Candidate(c.id+':graveyard:'+target.id,'cast',c.id,
                        features=features(power=1),label='Return '+target.name,
                        target_permanent=target.id)
                        for target in self.graveyard_subtype_targets(seat,c.graveyard_return_subtype))
                    continue
                if c.blink and self.payment(c)['paid']:
                    actions.extend(self.blink_choices(seat,c,'cast'));continue
                if c.event_definition and c.event_definition.bestow:
                    payment=self.payment(replace(c,mana_cost=c.event_definition.bestow[0]))
                    if payment['paid']:
                        actions.extend(Candidate(c.id+':bestow:'+target.card.id,'bestow',c.id,
                            features=features(power=2 if owner==seat else -100,cost=len(payment['sources'])),
                            label='Bestow '+c.name,target_permanent=target.card.id)
                            for owner,target in self.creature_targets(seat,c))
                if c.kind=='aura' and self.payment(c)['paid']:
                    actions.extend(Candidate(c.id+':aura:'+target.card.id,'cast',c.id,
                        features=features(power=1 if owner==seat else -100),label='Cast '+c.name,target_permanent=target.card.id)
                        for owner,target in self.aura_targets(seat,c))
                    continue
                if c.kind=='removal_spell' and self.payment(c)['paid']:
                    actions.extend(self.removal_choices(seat,c,'cast'))
                    continue
                if c.kind=='modifier_spell' and self.payment(c)['paid']:
                    actions.extend(Candidate(c.id+':target='+target.card.id,'cast',c.id,
                        features=features(power=1 if ((owner==seat)==
                            (c.target_modifier[0]+c.target_modifier[1]>=0)) else -1),
                        label='Cast '+c.name+' targeting '+target.card.name,
                        target_permanent=target.card.id)
                        for owner,target in self.creature_targets(seat,c))
                    continue
                if c.kind == "x_spell":
                    budget=sum(p.mana_pool)+sum(max(map(sum,options)) for _,options in self.mana_sources(seat))
                    for x in range(budget//c.mana_cost.count('{X}')+1):
                        payment=self.payment(c,x=x)
                        if not payment['paid']: continue
                        if c.x_effect=='draw' and x>len(p.library): continue
                        actions.append(Candidate(c.id+':x='+str(x),'cast',c.id,
                            features(power=x*c.token_definition.power if c.x_effect=='tokens' else 0,
                                     draw=x if c.x_effect=='draw' else 0,life=x if c.x_effect=='life' else 0,
                                     cost=len(payment['sources'])), 'Cast '+c.name+' with X='+str(x),x_value=x))
                    continue
                if c.modal_spell_face is not None and self.payment(c.modal_spell_face,seat=seat)['paid']:
                    back=c.modal_spell_face
                    actions.append(Candidate(c.id+':spellback','cast_modal_back',c.id,
                        features=features(power=back.power,toughness=back.toughness),
                        label='Cast '+back.name))
                if c.kind in ("creature", "vehicle", "enchantment", "spell", "token_spell", "mana_artifact", "equipment", "planeswalker", "station", "artifact") and self.payment(c)["paid"]:
                    if c.draw and len(p.library) < c.draw:
                        continue  # never choose a known self-decking draw spell
                    keywords = c.traits.split(";")[-1].split(",") if c.traits else []
                    actions.append(Candidate(c.id, "cast", c.id,
                        features(power=c.power+c.token_count, toughness=c.toughness,
                                 evasion=int(any(k in keywords for k in ("flying", "shadow", "horsemanship", "skulk"))),
                                 haste=int("haste" in keywords), life=c.life, draw=c.draw,
                                 cost=len(self.payment(c).get("sources", []))), "Cast " + c.name))
        elif self.phase == "attack":
            for x in p.battlefield:
                c = self.effective_card(x)
                if c is None or x.tapped: continue
                keywords = c.traits.split(";")[-1].split(",")
                if "defender" in keywords or x.fresh and "haste" not in keywords: continue
                responses = [self.damage(c, None)]
                for b in self.players[1-seat].battlefield:
                    blocker = self.effective_card(b)
                    if blocker and not b.tapped:
                        d = self.damage(c, blocker)
                        if d["legal"]: responses.append(d)
                minimum = min(max(0, d["damage"]-d["gainB"]) for d in responses)
                enemy = self.players[1-seat]
                commander_total = enemy.commander_damage.get(c.id, 0)
                lethal = all(enemy.life + d["gainB"] - d["damage"] <= 0
                             or c.id == p.commander_id and commander_total + d["damage"] >= 21
                             for d in responses)
                actions.append(Candidate(c.id, "attack", c.id,
                    features(power=c.power / 10, damage=minimum, lethal=int(lethal),
                             survive=int(not any(d["attackerDies"] for d in responses))),
                    "Attack with " + c.name))
        elif self.phase == "block":
            if self.diagnostic: actions.extend(self.activation_choices(seat, {"crew"}))
            attacker = next(x for x in self.players[self.active].battlefield if x.card.id == self.pending)
            a = self.effective_card(attacker)
            if a is None: raise RuntimeError("Attacker is no longer a creature")
            responses = [(None, self.damage(a, None))]
            for b in p.battlefield:
                blocker = self.effective_card(b)
                if blocker and not b.tapped:
                    d = self.damage(a, blocker)
                    if d["legal"]: responses.append((blocker, d))
            for c, d in responses:
                lethal = (p.life + d["gainB"] - d["damage"] <= 0 or
                          a.id == self.players[self.active].commander_id and
                          p.commander_damage.get(a.id, 0) + d["damage"] >= 21)
                actions.append(Candidate(c.id if c else "take", "block", c.id if c else "",
                    features(lethal=-int(lethal), damage=d["gainB"]-d["damage"],
                             power=(a.power if d["attackerDies"] else 0) - (c.power if c and d["blockerDies"] else 0),
                             survive=int(not d["blockerDies"])), "Block with " + c.name if c else "Take damage"))
        if self.phase == "attack":
            required = [a for a in actions if any(x.card.id == a.card_id and x.card.name == "Zurgo Helmsmasher"
                                                   for x in p.battlefield)]
            if required: return tuple(required)
        if self.phase != "block":
            actions.append(Candidate("pass", "pass", features=features(**{"pass": 1}), label="Pass"))
        return tuple(actions)

    def observe(self, seat: int) -> Observation:
        return Observation(seat,self.turn,self.phase,tuple(self.players[seat].hand),
                           json.dumps(self.state(),sort_keys=True),self.legal(seat),
                           self.turn_development[seat])

    def decide(self, seat: int) -> Candidate:
        observation = self.observe(seat)
        choice = self.policies[seat].choose(observation)
        if choice not in observation.legal_actions:
            raise RuntimeError("Agent attempted an illegal action")
        self.decisions.append({"seat": seat, "turn": self.turn, "phase": self.phase,
                               "action": choice.kind, "xValue": choice.x_value, "features": list(choice.features)})
        if choice.kind in ("cast","cast_commander","cast_flashback","bestow","equip","station",
                           "history_tokens","activate_tokens","activate_strip","activate_tribal_tokens","activate_scaled_mana","activate_sacrifice_mana","activate_sacrifice_boost","activate_land_counters","activate_land_animation","activate_regenerate","activate_sacrifice_team","activate_sacrifice_protection","activate_discard_tokens"):
            self.turn_development[seat]=True
        return choice

    def step(self) -> bool:
        if self.manual_priority and self.stack.items:
            raise RuntimeError('Pending stack objects require priority actions before advancing the turn')
        previous=(self.active,"main" if self.phase=="land" else self.phase)
        result=self._step()
        if previous!=(self.active,"main" if self.phase=="land" else self.phase):
            for seat,player in enumerate(self.players):
                if any(player.mana_pool):
                    expired=list(player.mana_pool)
                    player.mana_pool=[0]*6
                    self.log("mana_empty","Unused mana empties at the step or phase boundary.",actor=seat,mana=expired)
        return result

    def _step(self) -> bool:
        """Advance exactly one stage or decision for step-by-step human review."""
        if self.finished: return False
        p = self.players[self.active]
        if self.phase in ("setup", "end"):
            if self.turn >= self.max_turns:
                self.finished, self.result = True, "timeout"
                self.log("timeout", "Turn limit reached; no winner and no learning reward.")
                return False
            if self.phase == "end": self.active = 1 - self.active
            self.turn += 1
            self.stack.active=self.active;self.stack.priority=self.active
            self.land_played = False
            self.land_plays_this_turn = 0
            self.turn_development[self.active]=False
            self.life_gained_turn=[0,0]
            self.damage_to_players=[set(),set()]
            self._end_step_triggers_queued=False
            self.phase = "untap"
            p = self.players[self.active]
            for x in p.battlefield:
                x.tapped, x.fresh = False, False
            self.log("untap", f"Player {self.active + 1} starts turn {self.turn} and untaps.")
        elif self.phase == "untap":
            self.phase = "upkeep"
            due=[e for e in self.rebound_pending if e['controller']==self.active and e['afterTurn']<self.turn]
            self.rebound_pending=[e for e in self.rebound_pending if e not in due]
            waiting=[]
            # Snapshot every beginning-of-upkeep trigger before any rebound can blink a source.
            for trigger in self.event_game('upkeep').upkeep_triggers(
                    {seat:self.controlled_land_count(seat) for seat in range(len(self.players))}):
                source=next(item.card for player in self.players for item in player.battlefield if item.card.id==trigger['source'])
                waiting.append((trigger,source))
            for event in due:
                source=next((c for c in p.exile if root(c)==event['card']),None)
                if source:waiting.append((dict(event,operation='rebound',effect='rebound',name=source.name),source))
            self._waiting_triggers.extend(waiting)
            self.resolve_entry_triggers([],Card('upkeep','Upkeep','spell'))
            return True
        elif self.phase == "upkeep":
            self.phase = "draw"
            if self.diagnostic and self.turn == 1:
                self.log("draw_skipped", "The starting player skips their first draw in this two-player diagnostic.")
            else:
                self.draw(self.active)
                self.outcome()
        elif self.phase == "draw":
            self.phase = "land"
            self.log("phase", "First main phase: land decision.")
            self.advance_sagas_after_draw(self.active)
        elif self.phase in ("land", "main", "second_main"):
            choice = self.decide(self.active)
            if choice.kind == "pass":
                self.phase = {"land": "main", "main": "attack", "second_main": "end_step"}[self.phase]
                self.log("pass", choice.label)
                if self.phase=='attack':
                    game=self.event_game('combat');game.turn_player=self.active
                    pending=game.begin_combat_triggers()
                    self._waiting_triggers.extend(self.combat_reattach_triggers())
                    self.resolve_entry_triggers(pending,Card('combat','Beginning of combat','spell'))
            elif choice.kind=='station':
                self.activate_station(self.active,choice.card_id,choice.tap_ids[0])
            elif choice.kind=='history_tokens':
                self.activate_history(self.active,choice.card_id)
            elif choice.kind=='activate_class_level':
                self.activate_class_level(self.active,choice.card_id)
            elif choice.kind=='copy_enchantment_ability':
                self.activate_enchantment_copy(self.active,choice.card_id,choice.target_stack)
            elif choice.kind=='activate_strip':
                self.activate_strip(self.active,choice.card_id,choice.activation_index)
            elif choice.kind=='activate_graveyard_exile':
                self.activate_graveyard_exile(self.active,choice.card_id,choice.target_permanent)
            elif choice.kind=='activate_color_draw':
                self.activate_color_draw(self.active,choice.card_id)
            elif choice.kind=='activate_tokens':
                self.activate_tokens(self.active,choice.card_id,choice.activation_index)
            elif choice.kind=='activate_tribal_tokens':
                self.activate_tribal_tokens(self.active,choice.card_id)
            elif choice.kind=='activate_scaled_mana':
                self.activate_scaled_mana(self.active,choice.card_id,choice.x_value)
            elif choice.kind=='activate_discard_tokens':
                self.activate_discard_tokens(self.active,choice.card_id,choice.discard_id)
            elif choice.kind=='activate_sacrifice_mana':
                self.activate_sacrifice_mana(self.active,choice.card_id,choice.tap_ids[0])
            elif choice.kind=='activate_sacrifice_boost':
                self.activate_sacrifice_boost(self.active,choice.card_id,choice.tap_ids[0],choice.target_permanent)
            elif choice.kind=='activate_regenerate':
                self.activate_regenerate(self.active,choice.card_id,choice.target_permanent)
            elif choice.kind=='activate_land_counters':
                self.activate_land_counters(self.active,choice.card_id)
            elif choice.kind=='activate_land_animation':
                self.activate_land_animation(self.active,choice.card_id,choice.target_permanent)
            elif choice.kind=='activate_sacrifice_team':
                self.activate_sacrifice_team_boost(self.active,choice.card_id)
            elif choice.kind=='activate_sacrifice_protection':
                self.activate_sacrifice_protection(self.active,choice.card_id,choice.target_permanent,
                                                  ('White','Blue','Black','Red','Green')[choice.x_value])
            elif choice.kind in ('equip','equip_planeswalker'):
                self.activate_equip(self.active,choice.card_id,choice.target_permanent,
                                   planeswalker=choice.kind=='equip_planeswalker')
            elif choice.kind in ('crew','saddle'):
                self.activate_transport(self.active,choice.kind,choice.card_id,choice.tap_ids)
            else:
                card = (p.command_zone if choice.kind == "cast_commander" else
                        next(c for c in (p.graveyard if choice.kind == "cast_flashback" else self.permitted_exile_cards(self.active) if choice.kind=="cast_exile" else p.hand)
                             if c.id == choice.card_id))
                if card is None: raise RuntimeError("Commander is no longer in command zone")
                if choice.kind in ("land","land_back"):
                    if self.land_plays_this_turn>=self.land_play_limit(self.active):
                        raise ValueError('No land plays remain')
                    if choice.kind=="land_back":
                        if card.modal_land_face is None:raise ValueError('No supported land back face')
                        played=replace(card.modal_land_face,modal_front_face=card,
                                       physical_id=root(card))
                    else:
                        if card.kind!="land":raise ValueError('Only a land can be played')
                        played=card
                    p.hand.remove(card)
                    pending=self.enter_creature(played,p)
                    self.land_played = True
                    self.land_plays_this_turn += 1
                    if self.phase == "land": self.phase = "main"
                    self.log("land", f"Player {self.active + 1} plays {played.name}.", card=played.name,
                             modalBack=choice.kind=="land_back")
                    self.resolve_entry_triggers(pending,played)
                elif choice.kind=='cast_modal_back':
                    if card.modal_spell_face is None:raise ValueError('Missing legal modal spell face')
                    back=replace(card.modal_spell_face,modal_front_face=card,physical_id=root(card))
                    self.cast_spell(self.active,back,zone_card=card)
                else:
                    self.cast_spell(self.active,card,choice.x_value,choice.kind=='cast_commander',
                        modal_modes=choice.modal_modes,target=choice.target_permanent or choice.target_stack,
                        bestow=choice.kind=='bestow',flashback=choice.kind=='cast_flashback',
                         exile_permission=choice.kind=='cast_exile')
        elif self.phase == "attack":
            choice = self.decide(self.active)
            if choice.kind=='attack_group':
                self.declare_attackers(choice.attack_ids);return not self.finished
            if choice.kind == "pass":
                self.phase = "second_main"
                self.log("pass", "No attack.")
            else:
                self.pending = choice.card_id
                x = next(x for x in p.battlefield if x.card.id == self.pending)
                game = self.event_game("combat")
                game.attack(x.card.id, 1-self.active, defer=True)
                self.sync_events(game)
                self.phase = "block"
                self.log("attack", f"Player {self.active + 1} attacks with {x.card.name}.",
                         attacker=x.card.id)
                for event in game.events:
                    if event["kind"] == "trigger":
                        if event.get('operation') in ('create_tokens','counter_power_tokens','subtype_count_boost','attacking_subtype_boost','equipment_basic_search'):
                            self.resolve_entry_triggers([event],x.card)
                            if self.finished: return False
                            continue
                        self.log("trigger", f"{x.card.name}: {event['effect']}.",
                                 **{k:v for k,v in event.items() if k != "kind"})
        elif self.phase in ('first_damage','regular_damage'):
            self.strike_damage_step(self.phase=='first_damage')
        elif self.phase in ('group_damage_start','group_regular_damage'):
            self.group_damage_step()
        elif self.phase == "block":
            if self.group_combat is not None:
                choice=self.decide(1-self.active)
                if choice.kind=='crew':self.activate_transport(1-self.active,'crew',choice.card_id,choice.tap_ids)
                else:self.declare_blockers(dict(choice.blocks))
                return not self.finished
            if not any(item.card.id==self.pending and self.effective_card(item) is not None for item in p.battlefield):
                self.pending=None;self.phase='second_main'
                self.log('combat_skipped','The attacker is no longer a creature on the battlefield.')
                return True
            defender = self.players[1-self.active]
            choice = self.decide(1-self.active)
            if choice.kind == "crew":
                game = self.event_game("combat")
                game.crew(choice.card_id, list(choice.tap_ids), 1-self.active)
                self.sync_events(game)
                self.log("crew", choice.label, actor=1-self.active, target=choice.card_id, tapped=list(choice.tap_ids))
                return True
            a = next(x for x in p.battlefield if x.card.id == self.pending)
            b = next((x for x in defender.battlefield if x.card.id == choice.card_id), None)
            effective_attacker = self.effective_card(a)
            effective_blocker = self.effective_card(b) if b else None
            if effective_attacker is None: raise RuntimeError("Attacker is no longer a creature")
            early={item.card.id for item,card in ((a,effective_attacker),(b,effective_blocker)) if item and card and any(k in card.traits.split(';')[-1].split(',') for k in ('first strike','double strike'))}
            if early or a.marked_damage or (b and b.marked_damage):
                self.combat_context=dict(attacker=a.card.id,blocker=b.card.id if b else None,blocked=b is not None,early=early)
                self.log('block',choice.label,actor=1-self.active,blocker=b.card.id if b else None)
                self.phase='first_damage' if early else 'regular_damage'
                return True
            d = self.damage(effective_attacker, effective_blocker)
            regenerated=[]
            game=self.event_game('combat')
            for item,owner,key in ((a,self.active,'attackerDies'),(b,1-self.active,'blockerDies')):
                if item and d[key] and self.replace_regeneration(owner,item,game):
                    d[key]=False;regenerated.append(item)
            dead_ids = ([a.card.id] if d["attackerDies"] else []) + ([b.card.id] if b and d["blockerDies"] else [])
            damage_triggers=[];combat_draws=[]
            if d['damage']>0:
                game=self.event_game('combat')
                combat_draws=game.combat_draw_triggers(a.card.id)
                from oracle_abilities import matches, event_data
                for watcher in game.battlefield.values():
                    for trigger in watcher.definition.triggers:
                        if trigger.event=='combat_damage' and matches(trigger.subject,watcher,game.battlefield[a.card.id],True):
                            ability=event_data(trigger,watcher,game.battlefield[a.card.id])
                            damage_triggers.append(dict(ability,target=1-self.active))
            game=self.event_game('combat')
            death_triggers = game.death_triggers(dead_ids)
            dealt=[]
            if b:
                attack_damage=max(0,effective_attacker.power)
                if 'trample' in effective_attacker.traits.split(';')[-1].split(','):
                    attack_damage=min(attack_damage,1 if 'deathtouch' in effective_attacker.traits.split(';')[-1].split(',') else max(0,effective_blocker.toughness))
                if attack_damage:dealt.append(dict(source=a.card.id,target=b.card.id,amount=attack_damage))
                defense_damage=max(0,effective_blocker.power)
                if defense_damage:dealt.append(dict(source=b.card.id,target=a.card.id,amount=defense_damage))
            if d['damage']>0:dealt.append(dict(source=a.card.id,target=None,amount=d['damage']))
            death_triggers.extend(game.aura_damage_triggers(dealt,1-self.active))
            self.log("block", choice.label, actor=1-self.active,
                     blocker=b.card.id if b else None)
            if b:
                a.marked_damage+=max(0,effective_blocker.power)
                dealt=max(0,effective_attacker.power)
                abilities=effective_attacker.traits.split(';')[-1].split(',')
                if 'trample' in abilities:
                    dealt=min(dealt,1 if 'deathtouch' in abilities else max(0,effective_blocker.toughness))
                b.marked_damage+=dealt
            for item in regenerated:item.marked_damage=0
            self.gain_life(self.active,d["gainA"])
            self.gain_life(1-self.active,d["gainB"])
            defender.life -= d["damage"]
            if a.card.id == p.commander_id and d["damage"] > 0:
                defender.commander_damage[a.card.id] = defender.commander_damage.get(a.card.id, 0) + d["damage"]
            if d["attackerDies"]:
                self.send_to_destination(p, a)
            if b and d["blockerDies"]:
                self.send_to_destination(defender, b)
                if a.card.name == "Zurgo Helmsmasher" and not d["attackerDies"]:
                    a.counters += self.event_game('main').counter_amount(a.card.id,1)
                    self.log("trigger", "Zurgo gains a +1/+1 counter when the damaged creature dies.",
                             card=a.card.name, counters=a.counters)
            self.log("combat", "Combat damage resolves.", **d)
            self.pending = None
            self.outcome()
            if not self.finished:
                death_triggers.extend(damage_triggers)
                death_triggers.extend(combat_draws)
                self.resolve_entry_triggers(death_triggers,a.card)
            if not self.finished: self.phase = "second_main"
        elif self.phase == "end_step":
            # Snapshot triggers exactly once, and preserve end-step priority
            # windows before advancing to cleanup. Life gained after the
            # beginning of this step cannot retroactively make a trigger fire.
            if not self._end_step_triggers_queued:
                self._end_step_triggers_queued=True
                game=self.event_game('end_step')
                for event in game.end_step_triggers(self.life_gained_turn[self.active]):
                    source=next(item.card for item in self.players[self.active].battlefield if item.card.id==event['source'])
                    self._waiting_triggers.append((event,source))
                self._waiting_triggers.extend(self.queue_life_counter_triggers(game))
                self.resolve_entry_triggers([],Card('end-step','End step','spell'))
                return True
            if self.stack.items:
                raise ValueError('Cannot leave end step with unresolved stack items')
            self.phase='cleanup'
            return True
        elif self.phase == "cleanup":
            self.exile_cast_permissions={key:value for key,value in self.exile_cast_permissions.items()
                if not (value[0]==self.active and value[1]<=self.turn)}
            # Deterministic discard is a declared sandbox rule, not a learned policy.
            while len(p.hand) > 7:
                c = p.hand.pop()
                p.graveyard.append(c)
                self.log("discard", f"Player {self.active+1} discards {c.name}.", card=c.name)
            for player in self.players:
                for item in player.battlefield:
                    item.marked_damage=0;item.regeneration_shields=0
                    item.temporary_land_power=None;item.temporary_land_subtype=''
            game = self.event_game("cleanup")
            game.cleanup()
            self.sync_events(game)
            for owner in self.players:
                for attached in list(owner.battlefield):
                    if attached.card.kind=='aura' and not attached.attached_to:
                        owner.battlefield.remove(attached)
                        if not attached.card.is_token:owner.graveyard.append(attached.card)
            self.resolve_entry_triggers([],Card('cleanup','Cleanup','spell'))
            self.phase = "end"
            self.log("end", f"Player {self.active+1} ends the turn.")
        else:
            self.pause("Unknown turn stage " + self.phase)
        return not self.finished

    def run(self) -> dict:
        try:
            while self.step(): pass
        except (ValueError, RuntimeError, KeyError, StopIteration) as exc:
            self.pause("Engine invariant or unsupported decision: " + str(exc))
        return self.report()

    def report(self):
        return {"schemaVersion": 1, "kind": "turn-replay", "mode": "diagnostic-group-combat-v2" if self.diagnostic else "sandbox-single-attacker-v1",
                "combatMode": "group-v2" if self.diagnostic else "single-attacker-v1",
                "notice": "Partial diagnostic/classroom match; not a complete Commander game or Minecraft entity test.",
                "seed": self.seed, "starter": self.starter, "turns": self.turn, "result": self.result,
                "winner": self.winner, "openingMulligans": list(self.opening_mulligans), "learningEligible": not self.diagnostic and self.result in ("win", "draw") and not self.questions,
                "productionEligible": False, "policyVersions": [p.version for p in self.policies],
                "events": self.events, "questions": self.questions}



def diagnostic_land(definition: dict, identity: set[str]) -> dict | None:
    """Explicit land patterns in the submitted decks; no generalized Oracle guessing."""
    from land_abilities import compile_land
    composed=compile_land(definition,rule_text(definition.get('oracleText','')))
    if composed:
        program=composed.pop('land_program')
        counter_ability=composed.pop('land_counter_ability','')
        counter_scope=composed.pop('land_counter_scope','all')
        composed['event']=EventDefinition(definition['name'],frozenset({'Land'}),frozenset(definition.get('subTypes',[])),
            'Legendary' in definition.get('superTypes',[]),0,0,program.keywords,triggers=program.triggers,
            land_counter_ability=counter_ability,land_counter_scope=counter_scope)
        return composed
    text = definition.get("oracleText", "")
    names = {"White": 1, "Blue": 2, "Black": 4, "Red": 8, "Green": 16}
    if text == "{T}: Add one mana of any color in your commander's color identity.":
        mask = sum(names.get(color, 0) for color in identity)
        return {"kind":"land", "mask":mask, "land_rule":""} if mask else None
    lines = text.splitlines()
    if len(lines) == 2:
        two = re.fullmatch(r"\{T\}: Add \{([WUBRG])\} or \{([WUBRG])\}\.", lines[1])
        if two:
            bits = {"W":1,"U":2,"B":4,"R":8,"G":16}
            mask = bits[two[1]] | bits[two[2]]
            if lines[0] == "This land enters tapped unless you control two or more other lands.":
                return {"kind":"land","mask":mask,"land_rule":"two_other_lands"}
            typed = re.fullmatch(r"This land enters tapped unless you control a (Plains|Island|Swamp|Mountain|Forest) or a (Plains|Island|Swamp|Mountain|Forest)\.",lines[0])
            if typed:
                return {"kind":"land","mask":mask,"land_rule":"has_type:"+typed[1]+","+typed[2]}
        basic=re.fullmatch(r"\(\{T\}: Add \{([WUBRG])\} or \{([WUBRG])\}\.\)",lines[0])
        if basic and lines[1] == "This land enters tapped unless you control two or more basic lands.":
            bits={"W":1,"U":2,"B":4,"R":8,"G":16}
            return {"kind":"land","mask":bits[basic[1]]|bits[basic[2]],"land_rule":"two_basics"}
    return None


def import_diagnostic_card(rules: RulesBridge, definition: dict, seat: int,
                           uid: str, identity: set[str]) -> Card:
    if definition.get('layout')=='transform':
        faces=definition.get('faces',())
        if len(faces)==2 and all(isinstance(face,dict) for face in faces):
            def as_card(face,noncastable=False):
                # The bridge rejects a missing mana cost, correctly for cards
                # cast from hand. A transformed back is NOT a castable card:
                # validate its Oracle program using a temporary {0} bridge
                # sentinel, then restore the genuinely absent printed cost.
                printed_cost=face.get('manaCost','')
                raw=dict(definition,name=face.get('name',''),types=face.get('types',[]),
                         superTypes=face.get('superTypes',[]),subTypes=face.get('subTypes',[]),
                         manaCost=printed_cost or ('{0}' if noncastable else ''),
                         oracleText=face.get('text',''),power=face.get('power',''),
                         toughness=face.get('toughness',''),colors=face.get('colors',[]),
                         layout='normal',faces=[])
                parsed=import_diagnostic_card(rules,raw,seat,uid,identity)
                if noncastable and not printed_cost and parsed.kind!='unsupported':
                    definition=parsed.event_definition
                    parsed=replace(parsed,mana_cost='',printed_mana_value=None,
                        event_definition=replace(definition,mana_cost='') if definition else None)
                return parsed
            front=as_card(faces[0]);back=as_card(faces[1],noncastable=True)
            if (front.kind=='enchantment' and front.event_definition and
                    front.event_definition.saga_chapter_scale and
                    back.kind=='creature' and back.event_definition and
                    back.event_definition.self_artifact_enchantment_scale):
                return replace(front,transform_back_face=back)
        return Card(uid,definition['name'],'unsupported')
    if definition.get('layout')=='modal_dfc':
        faces=definition.get('faces',[])
        # The current two-face executor supports modal spell-front/land-back
        # cards, not transform, Saga, or two spell faces. Reject partial support.
        if len(faces)==2 and all(isinstance(face,dict) for face in faces):
            def face_definition(face):
                raw={**definition,
                     'name':face.get('name',''),'types':face.get('types',[]),
                     'superTypes':face.get('superTypes',[]),
                     'subTypes':face.get('subTypes',[]),
                     'colors':face.get('colors',[]),
                     'manaCost':face.get('manaCost',''),
                     'oracleText':face.get('text',''),
                     'power':face.get('power',''),'toughness':face.get('toughness',''),
                     'layout':'normal','faces':[]}
                return raw
            front=import_diagnostic_card(rules,face_definition(faces[0]),seat,uid,identity)
            back=import_diagnostic_card(rules,face_definition(faces[1]),seat,uid,identity)
            if front.kind not in ('unsupported','land') and back.kind=='land' and not back.mana_cost:
                return replace(front,modal_land_face=back)
            if (front.kind not in ('unsupported','land') and
                    back.kind not in ('unsupported','land') and back.mana_cost):
                return replace(front,modal_spell_face=back)
        return Card(uid,definition['name'],'unsupported')
    parsed = audit_card(rules, definition)
    event_definition = parse_event_card(definition)
    allowed = (definition["name"] in ("Kolodin, Triumph Caster", "Zurgo Helmsmasher", "Brightfield Mustang", "Nested Shambler")
               or bool(event_definition.triggers or event_definition.static_effects or event_definition.attack_effects or event_definition.attachment or event_definition.activations or event_definition.devotion or event_definition.bestow or bool({"hexproof", "menace","shroud"} & event_definition.abilities) or any(k.startswith('block_power_below_') for k in event_definition.abilities) or "Planeswalker" in event_definition.types or event_definition.role_events or event_definition.modal_role_choices or event_definition.animate_land_ability or event_definition.enchanted_draw or event_definition.life_multiplier!=1 or event_definition.life_addition or event_definition.cost_reductions or event_definition.counter_replacements or event_definition.entry_counter_grants or event_definition.attack_watchers or event_definition.token_replacements or event_definition.token_action_triggers or event_definition.token_leave_triggers or event_definition.opponent_creatures_enter_tapped or event_definition.linked_exile or event_definition.tribal_tap_tokens or event_definition.scaled_mana_tap or event_definition.sacrifice_ability or event_definition.mentor or event_definition.attack_nontoken_tokens or event_definition.modal_attack_tokens or event_definition.prevents_opponent_sacrifice or event_definition.sacrifice_team_boost or event_definition.sacrifice_protection or event_definition.attack_group_draw or event_definition.discard_token_ability or event_definition.regenerate_subtype or event_definition.entry_keyword_choices or event_definition.dynamic_pt_color or event_definition.combat_limits or event_definition.upkeep_token_rule or event_definition.land_type_effect or event_definition.additional_land_plays or event_definition.end_step_life_distribution or event_definition.equipment_basic_search or event_definition.station or event_definition.history_activation or event_definition.crew is not None or event_definition.saddle is not None or event_definition.graveyard_exile_activation or event_definition.class_program or event_definition.constellation_counter or event_definition.enchantment_combat_copy or event_definition.saga_chapter_scale or event_definition.self_artifact_enchantment_scale) or "Vehicle" in definition.get("subTypes", []))
    cost = definition.get("manaCost") or ""
    if (parsed["kind"] == "unsupported" and allowed and event_definition.supported
            and (rules.query("cost",cost)["supported"] or "Land" in event_definition.types and not cost)):
        keywords = sorted(event_definition.abilities)
        parsed = {"kind":("vehicle" if "Vehicle" in event_definition.subtypes else
                          "creature" if "Creature" in event_definition.types else
                          "land" if "Land" in event_definition.types else
                          "planeswalker" if "Planeswalker" in event_definition.types else
                          "station" if event_definition.station else
                          "artifact" if "Artifact" in event_definition.types and not event_definition.attachment else
                          event_definition.attachment[0] if event_definition.attachment else "enchantment"),
                  "power":event_definition.power,"toughness":event_definition.toughness,
                  "traits":f"{event_definition.power};{event_definition.toughness};"+",".join(keywords),
                  "event":event_definition}
    if parsed["kind"] == "unsupported":
        text = definition.get("oracleText", "")
        token_spec = parse_token_creation(text)
        if definition.get("types") == ["Sorcery"] and token_spec and rules.query("cost",cost)["supported"]:
            template = EventDefinition(" ".join(token_spec.subtypes),frozenset({"Creature"}|({"Land"} if token_spec.land else set())|({"Enchantment"} if token_spec.enchantment else set())),frozenset(token_spec.subtypes),
                False,token_spec.power,token_spec.toughness,token_spec.keywords,colors=frozenset(token_spec.colors))
            parsed = {"kind":"token_spell", "token_count":token_spec.amount,
                      "token_definition":template,"token_tapped":token_spec.tapped}
        else:
            parsed = diagnostic_land(definition, identity) or parsed
    storm_text=rule_text(definition.get('oracleText',''))
    storm_lines=storm_text.splitlines()
    if (parsed['kind']=='unsupported' and definition.get('types')==['Sorcery'] and len(storm_lines)==2
            and rules.query('cost',cost)['supported']):
        # Flashback is an alternate graveyard-casting permission, not a second
        # token effect. Require the full two-line Oracle program to be known.
        flashback=re.fullmatch(r'Flashback ((?:\{[^{}]+\})+)',storm_lines[1])
        spec=parse_token_creation(storm_lines[0]) if flashback else None
        if flashback and spec and rules.query('cost',flashback[1])['supported']:
            template=EventDefinition(' '.join(spec.subtypes),
                frozenset({'Creature'}|({'Land'} if spec.land else set())|({'Enchantment'} if spec.enchantment else set())),
                frozenset(spec.subtypes),False,spec.power,spec.toughness,spec.keywords,colors=frozenset(spec.colors))
            parsed={'kind':'token_spell','token_count':spec.amount,
                    'token_definition':template,'token_tapped':spec.tapped,
                    'flashback_cost':flashback[1]}
    if (parsed['kind']=='unsupported' and definition.get('types')==['Sorcery'] and len(storm_lines)==2
            and storm_lines[1]=='Storm' and rules.query('cost',cost)['supported']):
        spec=parse_token_creation(storm_lines[0])
        if spec:
            template=EventDefinition(' '.join(spec.subtypes),frozenset({'Creature'}|({'Land'} if spec.land else set())|({'Enchantment'} if spec.enchantment else set())),
                frozenset(spec.subtypes),False,spec.power,spec.toughness,spec.keywords,colors=frozenset(spec.colors))
            parsed={'kind':'token_spell','token_count':spec.amount,'token_definition':template,'token_tapped':spec.tapped,'storm':True}
    destruction=rule_text(definition.get('oracleText',''))
    from modal_sweeps import parse as parse_modal_sweeps
    modal=parse_modal_sweeps(destruction,definition.get('types',[]))
    from sweep_rewards import parse as parse_sweep_rewards
    sweep_reward=parse_sweep_rewards(destruction,definition.get('types',[]))
    if parsed['kind']=='unsupported' and sweep_reward and rules.query('cost',cost)['supported']:
        parsed={'kind':'removal_spell','removal':'destroy_creatures_reward','sweep_reward':sweep_reward}
    if parsed['kind']=='unsupported' and modal and rules.query('cost',cost)['supported']:
        parsed={'kind':'removal_spell','removal':'modal_sweep','modal_sweeps':modal}
    if (parsed['kind']=='unsupported' and definition.get('types')==['Sorcery']
            and rules.query('cost',cost)['supported']):
        # Whole-text recognition; regeneration prohibition is represented
        # by the current sandbox's lack of regeneration effects.
        if destruction in ('Destroy all creatures.',
                           "Destroy all creatures. They can't be regenerated."):
            parsed={'kind':'removal_spell','removal':'destroy_all_creatures',
                        'removal_no_regenerate':"can't be regenerated" in destruction}
        else:
            minimum=re.fullmatch(r'Destroy all creatures with toughness ([1-9][0-9]*) or greater\.',destruction)
            if minimum:
                parsed={'kind':'removal_spell','removal':'destroy_toughness_min',
                        'removal_min_toughness':int(minimum[1])}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=='Destroy target creature.' and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'destroy'}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=="Exile target creature. Its controller may search their library for a basic land card, put that card onto the battlefield tapped, then shuffle."
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'exile_creature_basic_land'}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=='Exile target creature. Its controller gains life equal to its power.'
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'exile_creature_life'}
    damage_removal=re.fullmatch(r'Exile target creature that dealt damage to you this turn\.',destruction)
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and damage_removal and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'exile_creature_damaged_you'}
    ox= re.fullmatch(r'Destroy target (artifact or creature|creature or artifact)\. Its controller creates (.+)\.',destruction)
    if parsed['kind']=='unsupported' and ox and definition.get('types') in (['Instant'],['Sorcery']) and rules.query('cost',cost)['supported']:
        spec=parse_token_creation('Create '+ox[2]+'.')
        if spec is not None:
            template=EventDefinition(' '.join(spec.subtypes),
                frozenset({'Creature'}|({'Land'} if spec.land else set())|
                          ({'Enchantment'} if spec.enchantment else set())),
                frozenset(spec.subtypes),False,spec.power,spec.toughness,
                spec.keywords,colors=frozenset(spec.colors))
            parsed={'kind':'removal_spell','removal':'destroy_artifact_creature_token',
                    'token_count':spec.amount,'token_definition':template,
                    'token_tapped':spec.tapped}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=='Destroy target artifact or enchantment.'
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'destroy_artifact_enchantment'}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=='Destroy all nonland permanents your opponents control.'
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'opponent_nonlands'}
    artifact_only=re.fullmatch(
        r"Destroy target artifact\.(?: It can't be regenerated\.)?",
        rule_text(definition.get('oracleText','')))
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and artifact_only and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'destroy_artifact'}
    counter=re.fullmatch(r'Counter target (?:(creature|noncreature) )?spell\.',rule_text(definition.get('oracleText','')))
    if (parsed['kind']=='unsupported' and definition.get('types')==['Instant'] and counter
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'counter_spell','counter_filter':counter[1] or 'any'}
    variable=x_spells.parse(cost,definition.get('oracleText',''),definition.get('types',[]))
    if parsed['kind']=='unsupported' and variable:
        parsed={'kind':'x_spell','x_effect':variable['effect']}
        if variable['effect']=='tokens':
            spec=variable['token']
            parsed['token_definition']=EventDefinition(' '.join(spec.subtypes),frozenset({'Creature'}|({'Land'} if spec.land else set())|({'Enchantment'} if spec.enchantment else set())),frozenset(spec.subtypes),
                False,spec.power,spec.toughness,spec.keywords,colors=frozenset(spec.colors))
            parsed['token_tapped']=spec.tapped
    blink_lines=rule_text(definition.get('oracleText','')).splitlines()
    if parsed['kind']=='unsupported' and definition.get('types')==['Instant'] and blink_lines and blink_lines[1:] in ([],['Rebound']):
        # The zone-change instruction, object reference and return controller are
        # parsed separately. A new printing/name with the same words still works.
        blink_rule=re.fullmatch(
            r"Exile target creature you control, then return (?:it|that card) to the battlefield under (its owner's|your) control\.",
            blink_lines[0])
        if blink_rule and rules.query('cost',cost)['supported']:
            parsed={'kind':'blink_spell','blink':True,'rebound':len(blink_lines)==2,
                    'blink_to_controller':blink_rule[1]=='your'}
    return_subtype=re.fullmatch(
        r'Return target ([A-Z][a-z]+) card from your graveyard to your hand\.',
        rule_text(definition.get('oracleText','')))
    if (parsed['kind']=='unsupported' and 'Sorcery' in definition.get('types',[]) and return_subtype and rules.query('cost',cost)['supported']):
        parsed={'kind':'graveyard_return_spell','graveyard_return_subtype':return_subtype[1]}
    from forced_sacrifice import edict as parse_forced_sacrifice
    forced_sacrifice=parse_forced_sacrifice(rule_text(definition.get('oracleText','')),
                                           definition.get('types',[]))
    if parsed['kind']=='unsupported' and forced_sacrifice and rules.query('cost',cost)['supported']:
        parsed={'kind':'sacrifice_spell','forced_sacrifice':forced_sacrifice}
    from targeted_modifiers import parse as parse_targeted_modifier
    modifier=parse_targeted_modifier(rule_text(definition.get('oracleText','')),
                                     definition.get('types',[]))
    if parsed['kind']=='unsupported' and modifier and rules.query('cost',cost)['supported']:
        parsed={'kind':'modifier_spell','target_modifier':modifier}
    from artifact_color_mana import parse as parse_artifact_color_mana
    color_program=parse_artifact_color_mana(rule_text(definition.get('oracleText','')),definition.get('types',[]))
    if parsed['kind']=='unsupported' and color_program and rules.query('cost',cost)['supported']:
        parsed={'kind':'mana_artifact',**color_program}
    output=mana_pool.production(definition.get("oracleText", ""))
    if (parsed["kind"]=="unsupported" and definition.get("types")==["Artifact"]
            and output and rules.query("cost",cost)["supported"]):
        parsed={"kind":"mana_artifact","mana_production":output}
    return Card(id=uid, name=definition["name"], kind=parsed["kind"],blink=parsed.get("blink",False),rebound=parsed.get("rebound",False),blink_to_controller=parsed.get("blink_to_controller",False),flashback_cost=parsed.get("flashback_cost",""),graveyard_return_subtype=parsed.get("graveyard_return_subtype",""),
        forced_sacrifice=parsed.get('forced_sacrifice',()),
        mana_as_any_color=parsed.get('mana_as_any_color',False),color_draw_cost=parsed.get('color_draw_cost',''),
        target_modifier=parsed.get('target_modifier',()),modal_sweeps=parsed.get('modal_sweeps',()),sweep_reward=parsed.get('sweep_reward',()),
        instant=("Instant" in definition.get("types",[]) or bool(event_definition.supported and "flash" in event_definition.abilities)), counter_filter=parsed.get("counter_filter",""), removal=parsed.get("removal",""), removal_min_toughness=parsed.get("removal_min_toughness",0), removal_no_regenerate=parsed.get("removal_no_regenerate",False), mana_cost=cost, mana_production=parsed.get("mana_production",()), traits=parsed.get("traits", ""), power=parsed.get("power", 0),
        toughness=parsed.get("toughness", 0), mask=parsed.get("mask", 0),
        enters_tapped=parsed.get("tapped", False), draw=parsed.get("draw", 0),
        life=parsed.get("life", 0), land_rule=parsed.get("land_rule", ""),
        land_subtypes=tuple(definition.get("subTypes", [])),
        basic_land="Basic" in definition.get("superTypes", []), snow="Snow" in definition.get("superTypes", []), event_definition=parsed.get("event") or (event_definition if event_definition.supported and "Planeswalker" in event_definition.types else None),
        storm=parsed.get("storm",False), x_effect=parsed.get("x_effect",""), token_count=parsed.get("token_count",0),
        token_definition=parsed.get("token_definition"),token_tapped=parsed.get("token_tapped",False),
        printed_types=tuple(definition.get('types',[])),
        printed_mana_value=library_effects.mana_value(cost) if definition.get('layout','normal') in ('normal','token') else None,
        colors=tuple(definition.get("colors") or []), legendary="Legendary" in (definition.get("superTypes") or []))


def import_diagnostic_deck(rules: RulesBridge, deck: dict, seat: int) -> list[Card]:
    """Keep all 99 actual main-deck cards. Unsupported cards remain unplayable, never blanked."""
    if sum(c["quantity"] for c in deck["commanders"]) != 1 or sum(c["quantity"] for c in deck["mainboard"]) != 99:
        raise ValueError("Expected one commander and 99 main-deck cards")
    result = []
    identity = set(deck["commanders"][0].get("colorIdentity", []))
    for definition in deck["mainboard"]:
        for _ in range(definition["quantity"]):
            result.append(import_diagnostic_card(rules, definition, seat, f"{seat}-card-{len(result):03d}", identity))
    return result


def deck_fingerprint(deck: dict) -> str:
    """Deck identity uses commander and complete card quantities, not title or printing."""
    def counts(cards):
        total = {}
        for card in cards:
            name = unicodedata.normalize("NFKC", card["name"]).casefold().strip()
            total[name] = total.get(name, 0) + int(card["quantity"])
        return sorted(total.items())
    content = {"commanders":counts(deck.get("commanders", [])), "mainboard":counts(deck.get("mainboard", []))}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def unique_decks(pool: list[dict]) -> list[dict]:
    unique = []
    seen_ids, seen_lists = set(), set()
    for deck in pool:
        key = deck_fingerprint(deck)
        source_id = deck.get("sourceDeckId")
        if key in seen_lists or source_id is not None and source_id in seen_ids: continue
        seen_lists.add(key)
        if source_id is not None: seen_ids.add(source_id)
        unique.append(deck)
    return unique


def select_decks(pool: list[dict], seed: int) -> list[dict]:
    """Uniformly choose two different deck lists, reproducible without exposing shuffles to agents."""
    unique = unique_decks(pool)
    if len(unique) < 2: raise ValueError("At least two different deck lists are required; mirror matches are disabled.")
    return random.Random(seed ^ 0x4341535A).sample(unique, 2)


def schedule_decks(pool: list[dict], seed: int, matches: int) -> list[list[dict]]:
    """Randomize distinct matchups, without repeating a pairing within a batch."""
    unique = unique_decks(pool)
    pairs = list(itertools.combinations(unique, 2))
    if matches < 1 or matches > len(pairs):
        raise ValueError(f"Request 1 to {len(pairs)} distinct matches; repeated/mirror pairings are disabled.")
    rng = random.Random(seed ^ 0x4341535A)
    rng.shuffle(pairs)
    result = []
    for first, second in pairs[:matches]:
        result.append([second,first] if rng.randrange(2) else [first,second])
    return result


def diagnose(rules: RulesBridge, decks: list[dict], seed: int, turns_per_player: int) -> dict:
    """Limited visible diagnostic, never a legal game or eligible for learning."""
    if len(decks) != 2 or turns_per_player < 1:
        raise ValueError("Two decks and a positive turn count are required")
    if (deck_fingerprint(decks[0]) == deck_fingerprint(decks[1])
            or decks[0].get("sourceDeckId") is not None
            and decks[0].get("sourceDeckId") == decks[1].get("sourceDeckId")):
        raise ValueError("Mirror matches are disabled.")
    cards = tuple(import_diagnostic_deck(rules, deck, seat) for seat, deck in enumerate(decks))
    commanders = tuple(import_diagnostic_card(rules, deck["commanders"][0], seat, f"{seat}-commander",
        set(deck["commanders"][0].get("colorIdentity", []))) for seat, deck in enumerate(decks))
    sim = Simulator(rules, seed, max_turns=turns_per_player * 2, decks=cards,
                    commanders=commanders, diagnostic=True)
    result = sim.run()
    turns = [sum(e["kind"] == "end" and e["actor"] == seat for e in result["events"])
             for seat in (0, 1)]
    started = [sum(e["kind"] == "untap" and e["actor"] == seat for e in result["events"])
               for seat in (0, 1)]
    audit = audit_decks(rules, decks)
    partially_supported = {c.name for deck_cards in cards for c in deck_cards
                           if c.event_definition is not None or c.kind == "token_spell" or c.land_rule}
    partially_supported.update(c.name for c in commanders if c.event_definition is not None)
    parsed_abilities = {c.name:([dict(kind="trigger",**json.loads(json.dumps(asdict(t),default=sorted))) for t in c.event_definition.triggers]
                              + [dict(kind="static",**asdict(e)) for e in c.event_definition.static_effects])
                        for c in [*cards[0],*cards[1],*commanders]
                        if c.event_definition and (c.event_definition.triggers or c.event_definition.static_effects)}
    for seat, deck in enumerate(decks):
        imported = {card.name:card for card in cards[seat]}
        for definition in deck["mainboard"]:
            if (audit_card(rules, definition)["kind"] == "unsupported"
                    and imported[definition["name"]].kind != "unsupported"):
                partially_supported.add(definition["name"])
    for q in audit["questions"]:
        if q.get("card") in partially_supported:
            q["diagnosticSupport"] = True
            q["supportNote"] = "Supported in the limited diagnostic; full timing, combat and live game integration remain open."
            if q["card"] in parsed_abilities:
                q["parsedAbilities"] = parsed_abilities[q["card"]]
            if q["card"] in DIAGNOSTIC_RULINGS:
                q["ruleAnswer"] = DIAGNOSTIC_RULINGS[q["card"]]
    result.update(mode="real-deck-diagnostic", learningEligible=False, productionEligible=False,
                  spectatorReplay=True,
                  spectatorNotice="Omniscient saved replay: both players' hand identities are visible to the viewer only, never to the AI. Libraries remain hidden.",
                  notice="Diagnostic only: real decks and supported commanders are used; unsupported cards cannot be played and the rules are incomplete. Results are not a valid Commander game.",
                  deckNames=[d["name"] for d in decks],
                  deckIds=[d.get("sourceDeckId") for d in decks],
                  deckFingerprints=[deck_fingerprint(d) for d in decks],
                  commanders=[d["commanders"][0]["name"] for d in decks],
                  turnsCompleted=turns, turnsStarted=started,
                  questions=audit["questions"] + result["questions"],
                  unsupportedInHand=[[c.name for c in p.hand if c.kind == "unsupported"] for p in sim.players],
                  unsupportedDiscarded=[[c.name for c in p.graveyard if c.kind == "unsupported"] for p in sim.players])
    if result["result"] == "timeout" and turns == [turns_per_player, turns_per_player]:
        result["result"] = "diagnostic_window_complete"
    result["rulesProgress"] = {
        "notice":"Observed rule execution, not evidence of learned strategy or complete Magic support.",
        "cardsPlayableInDiagnostic":[sum(c.kind != "unsupported" for c in cards[i]) + int(commanders[i].kind != "unsupported") for i in (0,1)],
        "landsPlayed":sum(e["kind"]=="land" for e in result["events"]),
        "spellsCast":sum(e["kind"]=="cast" for e in result["events"]),
        "triggerLogEntries":sum(e["kind"]=="trigger" for e in result["events"]),
        "runtimeQuestions":[q["reason"] for q in sim.questions],
        "unsupportedEncountered":sorted({name for row in result["unsupportedInHand"]+result["unsupportedDiscarded"] for name in row}),
        "unsupportedCommanders":[c.name for c in commanders if c.kind=="unsupported"],
    }
    return result

def match_score(report: dict, seat: int) -> tuple[int, int]:
    # Lexicographic: speed never compensates for one fewer win. Loss speed has no benefit.
    if not report["learningEligible"]: return (0, 0)
    return (1, -report["turns"]) if report["winner"] == seat else (0, 0)


def evaluate(rules: RulesBridge, candidate: Policy, champion: Policy,
             seeds: list[int]) -> dict:
    scores = {"candidate": [0, 0], "champion": [0, 0]}
    completed = 0
    for seed in seeds:
        for seat in (0, 1):
            policies = (candidate, champion) if seat == 0 else (champion, candidate)
            report = Simulator(rules, seed, starter=seed % 2, policies=policies).run()
            if not report["learningEligible"]: continue
            completed += 1
            for key, actor in (("candidate", seat), ("champion", 1-seat)):
                score = match_score(report, actor)
                scores[key] = [a+b for a,b in zip(scores[key], score)]
    return {**scores, "completed": completed, "expected": len(seeds)*2,
            "promote": completed == len(seeds)*2 and tuple(scores["candidate"]) > tuple(scores["champion"])}


def train(rules: RulesBridge, output: Path, generations: int, seed: int, games: int = 8) -> dict:
    if generations < 1 or games < 2: raise ValueError("Need positive generations and at least two evaluation seeds")
    checkpoint = output / "champion.json"
    journal_path = output / "history.json"
    state_path = output / "state.json"
    if state_path.exists():
        saved = json.loads(state_path.read_text())
        if saved.get("sandboxVariant") != "distinct-decks-v2":
            raise ValueError("This checkpoint belongs to the older mirror-deck demo; use a new output directory to preserve it.")
        if saved["seed"] != seed or saved["evaluationSeedsPerGeneration"] != games:
            raise ValueError("Resume with the original seed/evaluation settings, or choose a new output directory.")
        champion = Policy.from_json(saved["champion"])
        history = saved["history"]
    else:
        if checkpoint.exists() or journal_path.exists():
            raise ValueError("Missing authoritative training state; preserve this directory and select a new one.")
        champion = Policy()
        history = []
    def save_training():
        # One authoritative atomic generation commit; other files are readable exports.
        write_json(state_path, {"schemaVersion":1,"sandboxVariant":"distinct-decks-v2","seed":seed,"evaluationSeedsPerGeneration":games,
                                "champion":champion.to_json(),"history":history})
        write_json(checkpoint, champion.to_json())
        write_json(journal_path, history)
    save_training()
    # Continuing consumes the next generation's seeds; never replay a completed generation.
    start = len(history)
    for generation in range(start, start + generations):
        rng = random.Random(seed + generation * 100003)
        # Both agents play with frozen shared parameters. Pool only after the game.
        selfplay = Simulator(rules, seed + generation, starter=generation % 2,
                             policies=(champion, champion))
        report = selfplay.run()
        # No updates from blocked/truncated matches.
        if not report["learningEligible"]:
            row = {"generation": generation, "status": "blocked", "promoted": False}
            history.append(row);save_training()
            continue
        # Evolutionary policy learning: mutate reusable decision weights, evaluate on fresh shuffles.
        winner = report["winner"]
        pools = [[d["features"] for d in selfplay.decisions if d["seat"] == seat] for seat in (0, 1)]
        means = [tuple(sum(row[i] for row in rows) / max(1, len(rows)) for i in range(len(FEATURES)))
                 for rows in pools]
        # General action-feature feedback from BOTH independent agents after the match ends.
        feedback = tuple(0. if winner is None else
                         (means[winner][i]-means[1-winner][i]) /
                         (1+abs(means[winner][i])+abs(means[1-winner][i]))
                         for i in range(len(FEATURES)))
        weights = tuple(max(-150., min(150., w+.1*delta+rng.gauss(0, .35)))
                        for w, delta in zip(champion.weights, feedback))
        candidate = Policy(champion.version+1, weights)
        seeds = [seed + 1_000_000 + generation * games + n for n in range(games)]
        result = evaluate(rules, candidate, champion, seeds)
        row = {"generation": generation, "status": "evaluated", "selfPlayWinner": report["winner"],
               "selfPlayTurns": report["turns"], "pooledDecisions": [len(rows) for rows in pools],
               "featureFeedback": dict(zip(FEATURES, feedback)), "evaluationSeeds": seeds, **result,
               "promoted": result["promote"]}
        write_json(output / "replays" / f"generation-{generation}.json", report)
        write_json(output / "candidates" / f"generation-{generation}.json", candidate.to_json())
        if result["promote"]:
            champion = candidate
            write_json(output / "checkpoints" / f"generation-{generation}.json", champion.to_json())
            write_json(checkpoint, champion.to_json())
        history.append(row)
        save_training()
    return {"scope": champion.scope, "championVersion": champion.version, "history": history,
            "notice": "Sandbox evolutionary policy training only. Not wired to live golems or real decks."}


def pack_replay(report: dict) -> dict:
    """Lossless public replay packing for small, phone-friendly HTML files."""
    if not report.get("events"): return report
    packed = {k: v for k, v in report.items() if k != "events"}
    catalog, indices, events = [], {}, []
    def reference(card):
        key = card["id"]
        if key not in indices:
            indices[key] = len(catalog)
            catalog.append({k:v for k,v in card.items() if k not in ("tapped","fresh")})
        return indices[key]
    for e in report["events"]:
        state = e["state"]
        players = []
        for p in state["players"]:
            field = [[reference(c),int(c["tapped"]),int(c["fresh"]),c["power"],c["toughness"],c["traits"],
                      c.get("saddled",False),c.get("counters",0),
                      c.get("kind"),c.get("isCreature"),c.get("loyalty"),c.get("chargeCounters"),
                      c.get("attachedTo"),c.get("hexproof"),c.get("wardCosts"),c.get("bestowed",False)]
                     for c in p["battlefield"]]
            grave = [reference(c) for c in p["graveyard"]]
            # Append public fields rather than changing existing indices, so
            # earlier packed fixture replays remain readable by the viewer.
            exile = [reference(c) for c in p.get("exile",[])]
            players.append([p["life"],p["handCount"],p["libraryCount"],field,grave,
                            p.get("commanderInZone",False),p.get("commanderDamage",{}),
                            exile,p.get("manaPool",[])])
        # The optional ninth slot is a deliberate omniscient SPECTATOR view.
        # No hidden cards are added to public state or policy observations.
        hands=[[reference(c) for c in cards] for cards in e["spectatorHands"]] if "spectatorHands" in e else None
        compact=[e["index"],e["turn"],e["phase"],e["actor"],e["kind"],e["message"],
                 e["details"],[state["active"],state["turn"],state["phase"],players,
                               state.get("stack",[]),state.get("priority")]]
        if hands is not None:compact.append(hands)
        events.append(compact)
    return {**packed,"packedReplay":1,"cardCatalog":catalog,"compactEvents":events}


def export_review(output: Path, report: dict):
    write_json(output, report)
    template = (HERE / "viewer.html").read_text(encoding="utf-8")
    # Escape script delimiters in data imported from external deck/card names.
    payload = json.dumps(pack_replay(report), ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    output.with_suffix(".html").write_text(template.replace("/*EMBEDDED_REPLAY*/null", payload), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Audit real decks and create blocking questions; no games or learning")
    audit.add_argument("--decks", nargs="+", type=Path, default=sorted((HERE/"decks").glob("*.json")))
    audit.add_argument("--out", type=Path, default=HERE/"reports/deck-review.json")
    sim = sub.add_parser("simulate", help="Run a synthetic supported-subset classroom match")
    sim.add_argument("--demo", action="store_true", required=True)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--starter", type=int, choices=(0,1), default=0)
    sim.add_argument("--max-turns", type=int, default=100)
    sim.add_argument("--out", type=Path, default=HERE/"reports/demo-replay.json")
    diagnostic = sub.add_parser("diagnose", help="Run real decks in a visibly incomplete, non-training diagnostic")
    diagnostic.add_argument("--decks", nargs="+", type=Path, default=sorted((HERE/"decks").glob("*.json")))
    diagnostic.add_argument("--seed", type=int, default=42)
    diagnostic.add_argument("--turns-per-player", type=int, default=10)
    diagnostic.add_argument("--out", type=Path, default=HERE/"reports/real-decks-diagnostic.json")
    pool = sub.add_parser("pool-diagnose", help="Run random, non-mirror real-deck diagnostics (never used for training)")
    pool.add_argument("--decks", nargs="+", type=Path, default=sorted((HERE/"decks").glob("*.json")))
    pool.add_argument("--seed", type=int, default=42)
    pool.add_argument("--matches", type=int, default=6)
    pool.add_argument("--turns-per-player", type=int, default=10)
    pool.add_argument("--out", type=Path, default=HERE/"reports/pool")
    learning = sub.add_parser("train", help="Persistent evolutionary learning in the sandbox only")
    learning.add_argument("--demo", action="store_true", required=True)
    learning.add_argument("--generations", type=int, default=3)
    learning.add_argument("--seed", type=int, default=42)
    learning.add_argument("--evaluation-seeds", type=int, default=8)
    learning.add_argument("--out", type=Path, default=HERE/"runs/distinct-demo")
    args = parser.parse_args()
    with RulesBridge() as rules:
        if args.command == "audit":
            report = audit_decks(rules, [json.loads(p.read_text()) for p in args.decks])
            if args.out.exists():
                old = json.loads(args.out.read_text())
                answers = {q["id"]: q.get("answer") for q in old.get("questions", [])}
                for q in report["questions"]:
                    q["answer"] = answers.get(q["id"])
            export_review(args.out, report)
            print(json.dumps({"status": report["status"], "questions": len(report["questions"]), "output": str(args.out)}))
        elif args.command == "diagnose":
            selected = select_decks([json.loads(p.read_text()) for p in args.decks], args.seed)
            report = diagnose(rules, selected, args.seed, args.turns_per_player)
            export_review(args.out, report)
            print(json.dumps({k: report[k] for k in ("result", "deckNames", "commanders",
                              "turnsCompleted", "learningEligible", "unsupportedInHand",
                              "unsupportedDiscarded")}, ensure_ascii=False))
        elif args.command == "pool-diagnose":
            if args.matches < 1: raise ValueError("At least one match is required")
            deck_pool = [json.loads(p.read_text()) for p in args.decks]
            results = []
            schedule = schedule_decks(deck_pool, args.seed, args.matches)
            for i, selected in enumerate(schedule):
                match_seed = args.seed + i
                report = diagnose(rules, selected, match_seed, args.turns_per_player)
                export_review(args.out / f"match-{i+1:03d}.json", report)
                players = report["events"][-1]["state"]["players"]
                results.append({"match":i+1,"seed":match_seed,"deckNames":report["deckNames"],
                    "commanders":report["commanders"],"deckIds":report["deckIds"],"result":report["result"],
                    "turnsCompleted":report["turnsCompleted"],"life":[p["life"] for p in players],
                    "winner":report["winner"],"learningEligible":False,"rulesProgress":report["rulesProgress"]})
            write_json(args.out/"summary.json", {"matches":results,"notice":"Incomplete diagnostics; never used for training."})
            print(json.dumps({"matches":results},ensure_ascii=False))
        elif args.command == "simulate":
            report = Simulator(rules, args.seed, args.starter, max_turns=args.max_turns).run()
            export_review(args.out, report)
            print(json.dumps({k: report[k] for k in ("result", "winner", "turns", "learningEligible")}))
        else:
            report = train(rules, args.out, args.generations, args.seed, args.evaluation_seeds)
            print(json.dumps(report))


if __name__ == "__main__":
    main()
