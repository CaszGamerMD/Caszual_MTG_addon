#!/usr/bin/env python3
"""Independent self-play sandbox, strict real-deck intake, and human-readable replays.
The Java subset supplies card parsing and combat; diagnostic mana pools extend its payment rules.
This is NOT a complete Commander rules engine or a Minecraft entity test.
"""
from __future__ import annotations
import argparse
from card_events import Game as EventGame, Permanent as EventPermanent, Definition as EventDefinition, parse_card as parse_event_card, rule_text
import base64
from oracle_abilities import parse_token_creation
import mana_pool
import x_spells
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
        "question": "Implement/validate complete Commander timing, priority, multiple attackers/blockers, commander zones/damage and replacement effects before running these decks.",
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
    temporary_power: int = 0
    temporary_toughness: int = 0
    temporary_abilities: frozenset[str] = frozenset()


@dataclass
class Player:
    library: list[Card]
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
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


@dataclass(frozen=True)
class Observation:
    """The agent boundary: own hand + public information, no library order or enemy hand."""
    seat: int
    turn: int
    phase: str
    own_hand: tuple[Card, ...]
    public_state: str  # JSON string is immutable; it contains no private identities.
    legal_actions: tuple[Candidate, ...]


@dataclass(frozen=True)
class Policy:
    version: int = 0
    weights: tuple[float, ...] = tuple(DEFAULT_WEIGHTS.values())
    scope: str = "sandbox-single-attacker-v1"

    def choose(self, observation: Observation) -> Candidate:
        if not observation.legal_actions:
            raise ValueError("No legal action")
        # Identical observations give identical decisions. No access to the engine or replay.
        return max(observation.legal_actions,
                   key=lambda a: (sum(w * f for w, f in zip(self.weights, a.features)), a.id))

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


class Simulator:
    """Deterministic classroom turn model. No priority, stack, commanders or multi-attack combat."""
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
        self.total_cards = tuple(len(p.library) + int(p.command_zone is not None) for p in self.players)
        self.turn, self.active, self.phase = 0, starter, "setup"
        self.events: list[dict] = []
        self.decisions: list[dict] = []  # post-match data; never supplied to either player
        self.questions: list[dict] = []
        self.finished = False
        self.winner: int | None = None
        self.result = "running"
        self.combat_context=None
        self.pending: str | None = None
        self.land_played = False
        self.main_return = ""
        self.stack=PriorityStack(starter)
        self._current_spell=None
        self.manual_priority=False
        self._draining_priority=False
        self._resolving_stack=False
        self.token_sequence = 0
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
                if self.diagnostic and card.kind=="removal_spell" and card.removal=="destroy":
                    continue
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
            for _ in range(7):
                self.draw(seat)

    def display_permanent(self, item: Permanent) -> dict:
        effective = self.effective_card(item)
        c = effective or item.card
        return {"id": c.id, "name": c.name, "kind": c.kind, "power": c.power,
                "toughness": c.toughness, "traits": c.traits, "tapped": item.tapped,
                "fresh": item.fresh, "saddled": item.saddled, "counters": item.counters}

    def state(self) -> dict:
        return {"active": self.active, "turn": self.turn, "phase": self.phase,
                "stack": self.stack.public(), "priority": self.stack.priority,
                "players": [{"seat": i, "life": p.life, "handCount": len(p.hand),
                             "libraryCount": len(p.library), "manaPool": list(p.mana_pool),
                             "battlefield": [self.display_permanent(x) for x in p.battlefield],
                             "commanderInZone": p.command_zone is not None,
                             "commanderDamage": dict(p.commander_damage),
                             "graveyard": [{"id": c.id, "name": c.name} for c in p.graveyard]}
                            for i, p in enumerate(self.players)]}

    def invariant(self):
        for i, p in enumerate(self.players):
            cards = p.library + p.hand + p.graveyard + [x.card for x in p.battlefield]
            if p.command_zone: cards.append(p.command_zone)
            cards += [frame.payload[1] for frame in self.stack.items
                      if frame.controller==i and frame.payload[0].get('operation')=='spell'
                      and not frame.payload[0].get('copy')]
            if self._current_spell and self._current_spell[0]==i:
                resolving=self._current_spell[1]
                if not any(c.id==resolving.id for c in cards): cards.append(resolving)
            if sum(not c.is_token for c in cards) != self.total_cards[i] or len({c.id for c in cards}) != len(cards):
                raise RuntimeError("Card conservation failed")

    def event_game(self, phase: str) -> EventGame:
        """Adapt public battlefield state to the shared type-aware event kernel."""
        game = EventGame(turn_player=self.active, phase=phase)
        for seat, player in enumerate(self.players):
            for item in player.battlefield:
                card = item.card
                if card.kind == "land": continue
                definition = card.event_definition
                if definition is None:
                    if card.kind != "creature": continue
                    keywords = frozenset(k for k in card.traits.split(";")[-1].split(",") if k)
                    definition = EventDefinition(card.name, frozenset({"Creature"}), frozenset(card.land_subtypes),
                                                 card.legendary, card.power, card.toughness, keywords,
                                                 colors=frozenset(card.colors))
                game.battlefield[card.id] = EventPermanent(card.id, definition, seat, item.tapped,
                    item.fresh, item.saddled, item.animated, counters=item.counters, token=item.card.is_token,temporary_power=item.temporary_power,
                    temporary_toughness=item.temporary_toughness,temporary_abilities=item.temporary_abilities)
        return game

    def sync_events(self, game: EventGame):
        for player in self.players:
            for item in player.battlefield:
                state = game.battlefield.get(item.card.id)
                if state:
                    item.tapped, item.fresh = state.tapped, state.fresh
                    item.saddled, item.animated, item.counters = state.saddled, state.animated, state.counters
                    item.temporary_power,item.temporary_toughness,item.temporary_abilities=state.temporary_power,state.temporary_toughness,state.temporary_abilities

    def effective_card(self, item: Permanent) -> Card | None:
        game = self.event_game("combat")
        state = game.battlefield.get(item.card.id)
        if not state or not game.creature(state): return None
        power, toughness = game.stats(state)
        keywords = set(state.definition.abilities)
        for ability in ("haste", "indestructible", "flying", "first strike", "double strike",
                        "lifelink", "vigilance", "trample", "defender", "reach", "deathtouch"):
            if game.has(state, ability): keywords.add(ability)
        return replace(item.card, kind="creature", power=power, toughness=toughness,
                       traits=f"{power};{toughness};"+",".join(sorted(keywords)))

    def enter_creature(self, card: Card, player: Player):
        game = self.event_game("main")
        definition = card.event_definition
        if definition is None:
            definition = EventDefinition(card.name, frozenset({"Creature"}), frozenset(card.land_subtypes), card.legendary,
                card.power, card.toughness, frozenset(k for k in card.traits.split(";")[-1].split(",") if k),
                colors=frozenset(card.colors))
        game._next_token = self.token_sequence
        known = set(game.battlefield)
        controller = next(i for i, candidate in enumerate(self.players) if candidate is player)
        game.enter(EventPermanent(card.id, definition, controller))
        player.battlefield.append(Permanent(card))
        for token_id in game.battlefield.keys()-known-{card.id}:
            token_state = game.battlefield[token_id]
            if not token_state.token: raise RuntimeError("Unknown event-created permanent")
            d = token_state.definition
            token = Card(token_id,d.name,"creature",traits=f"{d.power};{d.toughness};"+
                ",".join(sorted(d.abilities)),power=d.power,toughness=d.toughness,
                event_definition=d,is_token=True)
            player.battlefield.append(Permanent(token))
        self.token_sequence = game._next_token
        self.sync_events(game)
        return [event for event in game.events if event["kind"] == "trigger"]

    def resolve_entry_triggers(self, triggers: list[dict], card: Card):
        # APNAP placement: active controller first, nonactive on top. Each controller
        # uses reverse discovery order on placement to preserve discovery resolution order.
        self.stack.active=self.active
        for controller in (self.active,1-self.active):
            for event in reversed([e for e in triggers if e.get('controller',self.active)==controller]):
                item=self.stack.push(controller,(event,card),event.get('name',card.name))
                self.log('stack_push',f'{item.label} ability goes on the stack.',stackId=item.id,controller=controller)
        if not self._resolving_stack: self.stack.priority=self.active
        if not self.manual_priority and not self._resolving_stack:
            self.drain_priority()

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
            self.stack.priority=self.active
        return status

    def response_choices(self,seat):
        if seat!=self.stack.priority: return ()
        return tuple(c for c in self.players[seat].hand if c.instant and c.kind in ('spell','token_spell','counter_spell','removal_spell')
                     and (not c.draw or c.draw<=len(self.players[seat].library))
                     and self.payment(c,seat=seat)['paid'])

    def creature_targets(self):
        game=self.event_game('main')
        return tuple((seat,item) for seat,player in enumerate(self.players) for item in player.battlefield
                     if item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id]))

    def removal_choices(self,seat,card,kind):
        game=self.event_game('main')
        return tuple(Candidate(card.id+':target='+item.card.id,kind,card.id,
                    features=features(power=(2 if owner!=seat else -100) if not game.has(game.battlefield[item.card.id],'indestructible') else -100,
                                      cost=len(self.payment(card,seat=seat).get('sources',[]))),
                    label='Cast '+card.name+' targeting '+item.card.name,target_permanent=item.card.id)
                     for owner,item in self.creature_targets())

    def counter_targets(self,card):
        if card.kind!='counter_spell': return ()
        return tuple(frame for frame in self.stack.items if frame.payload[0].get('operation')=='spell'
                     and (card.counter_filter=='any' or
                          (frame.payload[1].kind=='creature' and card.counter_filter=='creature') or
                          (frame.payload[1].kind!='creature' and card.counter_filter=='noncreature')))

    def priority_observation(self,seat):
        if seat!=self.stack.priority: raise ValueError('Player lacks priority')
        actions=[Candidate('priority-pass','priority_pass',features=features(),label='Pass priority')]
        for card in self.response_choices(seat):
            if card.kind=='removal_spell':
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
        card=next(c for c in self.players[seat].hand if c.id==choice.card_id)
        self.cast_spell(seat,card,target=choice.target_permanent or choice.target_stack)
        return 'cast'

    def cast_spell(self,seat,card,x=None,commander=False,target=None):
        player=self.players[seat]
        if not card.instant and seat!=self.stack.priority: raise ValueError('Player lacks priority')
        if self.stack.items:
            if seat!=self.stack.priority or not card.instant: raise ValueError('Spell timing or priority invalid')
        elif seat!=self.active or self.phase not in ('main','second_main'):
            if not card.instant or seat!=self.stack.priority: raise ValueError('Spell timing invalid')
        if not commander and card not in player.hand: raise ValueError('Card not in hand')
        if card.kind=='removal_spell' and target not in {item.card.id for _,item in self.creature_targets()}:
            raise ValueError('Removal requires a legal creature target')
        if card.kind=='counter_spell' and target not in {f.id for f in self.counter_targets(card)}:
            raise ValueError('Counterspell requires a legal spell target')
        payment=self.payment(card,player.commander_casts if commander else 0,x=x,seat=seat)
        if not payment['paid']: raise ValueError('Cannot pay spell cost')
        for source in player.battlefield:
            if source.card.id in payment['sources']:source.tapped=True
        player.mana_pool=list(payment['pool'])
        if commander:player.command_zone=None;player.commander_casts+=1
        else:player.hand.remove(card)
        prior=sum(e['kind']=='cast' and e['turn']==self.turn for e in self.events)
        self.stack.active=self.active
        frame=self.stack.push(seat,({'operation':'spell','controller':seat,'x':x,'target':target},card),card.name)
        self.log('cast',f'Player {seat+1} casts {card.name}.',actor=seat,card=card.name,
                 manaSources=payment['sources'],manaPool=list(player.mana_pool),commander=commander,xValue=x,targetStack=target if card.kind=='counter_spell' else None,
                 targetPermanent=target if card.kind=='removal_spell' else None)
        self.stack.priority=seat
        self.log('stack_push',f'{card.name} goes on the stack.',stackId=frame.id,controller=seat)
        if card.storm:
            self.log('storm',f'{card.name} creates {prior} spell copies.',copies=prior)
            for _ in range(prior):self.stack.push(seat,({'operation':'spell','controller':seat,'copy':True,'x':x},card),card.name+' copy')
        if not self.manual_priority and not self._resolving_stack:
            self.drain_priority()

    def resolve_spell(self,event,original):
        controller=event['controller'];p=self.players[controller];card=original
        if event.get('copy'): self.log('spell_copy',f'A copy of {card.name} resolves.',card=card.name)
        if card.kind in ('creature','vehicle','enchantment'):
            triggers=self.enter_creature(card,p)
            self.resolve_entry_triggers(triggers,card)
        elif card.kind=='mana_artifact': p.battlefield.append(Permanent(card))
        elif not event.get('copy'): p.graveyard.append(original)
        if card.kind=='removal_spell':
            target=next(((seat,item) for seat,item in self.creature_targets() if item.card.id==event['target']),None)
            if target is None:
                self.log('illegal_target',f'{card.name} has no legal creature target.',targetPermanent=event['target'])
                return
            owner,item=target;game=self.event_game('main')
            if game.has(game.battlefield[item.card.id],'indestructible'):
                self.log('indestructible',f'{item.card.name} cannot be destroyed.',targetPermanent=item.card.id)
                return
            triggers=game.death_triggers([item.card.id])
            self.send_to_destination(self.players[owner],item)
            self.log('destroy',f'{card.name} destroys {item.card.name}.',targetPermanent=item.card.id)
            self.outcome()
            if self.finished:return
            for trigger in triggers:
                if trigger['effect']=='create tapped Squirrels':
                    trigger.update(operation='create_tokens',tokenSpec=dict(amount=trigger['amount'],power=1,toughness=1,
                        colors=['Green'],subtypes=['Squirrel'],keywords=[],tapped=True,land=False))
            self.resolve_entry_triggers(triggers,card)
            return
        if card.kind=='counter_spell':
            frame=next((f for f in self.counter_targets(card) if f.id==event['target']),None)
            if frame is None:
                self.log('illegal_target',f'{card.name} has no legal target and does not resolve.',targetStack=event['target'])
                return
            removed=self.stack.counter(frame.id)
            if not removed.payload[0].get('copy'):
                owner=self.players[removed.controller];countered=removed.payload[1]
                if countered.id==owner.commander_id: owner.command_zone=countered
                else: owner.graveyard.append(countered)
            self.log('counter',f'{card.name} counters {frame.label}.',targetStack=frame.id)
            return
        if card.kind=='x_spell':
            x=event['x']
            card=replace(card,kind='token_spell' if card.x_effect=='tokens' else 'spell',
                         token_count=x if card.x_effect=='tokens' else 0,
                         draw=x if card.x_effect=='draw' else 0,life=x if card.x_effect=='life' else 0)
        if card.kind == "token_spell":
            for resolution in range(1):
                token_triggers = []
                for _ in range(card.token_count):
                    self.token_sequence += 1
                    definition = card.token_definition
                    if definition is None: raise RuntimeError("Missing parsed token characteristics")
                    token = Card(f"token-{self.token_sequence}",definition.name,"creature",
                                 traits=f"{definition.power};{definition.toughness};"+",".join(sorted(definition.abilities)),
                                 power=definition.power,toughness=definition.toughness,
                                 event_definition=definition,is_token=True)
                    token_triggers.extend(self.enter_creature(token,p))
                    next(x for x in p.battlefield if x.card.id==token.id).tapped = card.token_tapped
                    self.log("token", f"Creates a {definition.power}/{definition.toughness} {definition.name} creature token.",
                             card=definition.name, token=token.id)
                # Finish creating the whole batch before any entry trigger resolves.
                self.resolve_entry_triggers(token_triggers, card)
                if self.finished: return False
        if card.kind == "spell":
            for _ in range(card.draw): self.draw(controller)
            p.life += card.life
            self.log("resolve", f"{card.name} resolves.", lifeGain=card.life, drawn=card.draw)
            self.outcome()

    def _resolve_entry_effects(self, triggers: list[dict], card: Card):
        for event in triggers:
            if event.get('operation')=='counter_power_tokens':
                game=self.event_game('main')
                source=game.battlefield.get(event['source'])
                if source is not None:
                    source.counters+=event['counterAmount']
                    amount=max(0,game.stats(source)[0])
                    self.sync_events(game)
                else: amount=max(0,event['lastPower'])
                event=dict(event,operation='create_tokens',tokenSpec=dict(event['tokenSpec'],amount=amount))
            if event.get("operation") == "create_tokens":
                spec=event["tokenSpec"]
                owner=self.players[event["controller"]]
                pending=[]
                owner.life -= event.get("controllerLoss",0)
                for _ in range(spec["amount"]):
                    self.token_sequence+=1
                    definition=EventDefinition(" ".join(spec["subtypes"]),frozenset({"Land","Creature"} if spec.get("land") else {"Creature"}),frozenset(spec["subtypes"]),
                        False,spec["power"],spec["toughness"],frozenset(spec["keywords"]),colors=frozenset(spec["colors"]))
                    token=Card(f"token-{self.token_sequence}",definition.name,"creature",
                        traits=f"{definition.power};{definition.toughness};"+",".join(sorted(definition.abilities)),
                        power=definition.power,toughness=definition.toughness,event_definition=definition,is_token=True)
                    pending.extend(self.enter_creature(token,owner))
                    next(p for p in owner.battlefield if p.card.id==token.id).tapped=spec["tapped"]
                self.log("upkeep" if event.get("event")=="upkeep" else "trigger",
                         f"{event['name']}: controller loses {event.get('controllerLoss',0)} life and creates {spec['amount']} creature tokens.",actor=event["controller"],
                         **{k:v for k,v in event.items() if k!="kind"})
                self.outcome()
                if self.finished: return
                self.resolve_entry_triggers(pending,card)
                if self.finished: return
                continue
            elif event.get('operation')=='self_counter':
                source=next((item for player in self.players for item in player.battlefield if item.card.id==event['source']),None)
                if source:source.counters+=event['amount']
                message=f"{event['name']}: its surviving source receives a counter."
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
                    if permanent.controller == event["controller"] and game.creature(permanent):
                        permanent.counters += event["amount"]
                        affected.append(identifier)
                self.sync_events(game)
                message = f"{event['name']} puts {event['amount']} +1/+1 counters on each of {len(affected)} creatures."
            elif event.get("operation") == "damage":
                target = 1-event["controller"]
                self.players[target].life -= event["amount"]
                # Noncombat damage: never contributes to commander combat damage.
                message = f"{event['name']} deals {event['amount']} damage to Player {target+1}."
            elif event.get("operation") == "lose_life":
                source = event["controller"]
                target = 1-source  # This diagnostic is explicitly two-player.
                self.players[target].life -= event["amount"]
                self.players[source].life += event.get("gain",0)
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
        if has(a,'lifelink'):active.life+=to_blocker+to_player
        if has(b,'lifelink'):defender.life+=to_attacker
        defender.life-=to_player
        if attacker and attacker.card.id==active.commander_id and to_player:
            defender.commander_damage[attacker.card.id]=defender.commander_damage.get(attacker.card.id,0)+to_player
        game=self.event_game('combat');dead=[]
        for player in self.players:
            for item in player.battlefield:
                effective=self.effective_card(item)
                if effective is None:continue
                touch=(item is attacker and to_attacker>0 and has(b,'deathtouch')) or (item is blocker and to_blocker>0 and has(a,'deathtouch'))
                if effective.toughness<=0 or ((item.marked_damage>=effective.toughness or touch) and not game.has(game.battlefield[item.card.id],'indestructible')):
                    dead.append(item)
        triggers=game.death_triggers([item.card.id for item in dead])
        if to_player and attacker:
            from oracle_abilities import matches
            for watcher in game.battlefield.values():
                for trigger in watcher.definition.triggers:
                    if trigger.event=='combat_damage' and matches(trigger.subject,watcher,game.battlefield[attacker.card.id],True):
                        triggers.append(dict(operation='discard',effect='discard',controller=watcher.controller,name=watcher.definition.name,source=watcher.id,target=1-self.active))
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

    def send_to_destination(self, player: Player, item: Permanent):
        for frame in self.stack.items:
            event,_=frame.payload
            if event.get('operation')=='counter_power_tokens' and event.get('source')==item.card.id:
                effective=self.effective_card(item)
                if effective: event['lastPower']=effective.power
        player.battlefield.remove(item)
        if item.card.is_token:
            return  # Tokens cease to exist after leaving the battlefield.
        if item.card.id == player.commander_id:
            player.command_zone = item.card  # This prototype chooses the command-zone option.
        else:
            player.graveyard.append(item.card)

    def log(self, kind: str, message: str, **details):
        self.invariant()
        self.events.append({"index": len(self.events), "turn": self.turn,
                            "phase": self.phase, "actor": details.pop("actor", self.active),
                            "kind": kind, "message": message, "details": details, "state": self.state()})

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

    def mana_sources(self, seat: int):
        sources=[]
        for item in self.players[seat].battlefield:
            if item.tapped: continue
            definition=item.card.event_definition
            mask=item.card.mask if item.card.kind=='land' else 0
            if definition and 'Land' in definition.types:
                mask=sum(bit for subtype,bit in {'Plains':1,'Island':2,'Swamp':4,'Mountain':8,'Forest':16}.items()
                         if subtype in definition.subtypes)
                if 'Creature' in definition.types and item.fresh:
                    effective=self.effective_card(item)
                    if effective is None or 'haste' not in effective.traits.split(';')[-1].split(','): continue
            if mask:
                options=tuple(tuple(int(i==color) for i in range(6)) for color in range(6) if mask&(1<<color))
            elif item.card.kind=='mana_artifact': options=(item.card.mana_production,)
            else: continue
            sources.append((item.card.id,options))
        return sources

    def payment(self, card: Card, tax: int = 0, x: int | None = None, seat: int | None = None) -> dict:
        cost = card.mana_cost + (("{2}" * tax) if tax else "")
        seat=self.active if seat is None else seat
        player=self.players[seat]
        sources=self.mana_sources(seat)
        return mana_pool.plan(cost,player.mana_pool,sources,x)

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
                        helpers.append((other.card.id, effective.power))
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
        actions = []
        if self.phase == "land":
            if not self.land_played:
                for c in p.hand:
                    if c.kind == "land":
                        actions.append(Candidate(c.id, "land", c.id, features(power=1), "Play " + c.name))
        elif self.phase in ("main", "second_main"):
            if self.diagnostic: actions.extend(self.activation_choices(seat, {"crew","saddle"}))
            if (self.diagnostic and p.command_zone and p.command_zone.kind == "creature"
                    and self.payment(p.command_zone, p.commander_casts)["paid"]):
                c = p.command_zone
                actions.append(Candidate(c.id, "cast_commander", c.id,
                    features(power=c.power, toughness=c.toughness, haste=int(c.name == "Zurgo Helmsmasher"),
                             cost=len(self.payment(c, p.commander_casts).get("sources", []))),
                    "Cast commander " + c.name))
            for c in p.hand:
                if c.kind=='removal_spell' and self.payment(c)['paid']:
                    actions.extend(self.removal_choices(seat,c,'cast'))
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
                if c.kind in ("creature", "vehicle", "enchantment", "spell", "token_spell", "mana_artifact") and self.payment(c)["paid"]:
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
        return Observation(seat, self.turn, self.phase, tuple(self.players[seat].hand),
                           json.dumps(self.state(), sort_keys=True), self.legal(seat))

    def decide(self, seat: int) -> Candidate:
        observation = self.observe(seat)
        choice = self.policies[seat].choose(observation)
        if choice not in observation.legal_actions:
            raise RuntimeError("Agent attempted an illegal action")
        self.decisions.append({"seat": seat, "turn": self.turn, "phase": self.phase,
                               "action": choice.kind, "xValue": choice.x_value, "features": list(choice.features)})
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
            self.phase = "untap"
            p = self.players[self.active]
            for x in p.battlefield:
                x.tapped, x.fresh = False, False
            self.log("untap", f"Player {self.active + 1} starts turn {self.turn} and untaps.")
        elif self.phase == "untap":
            self.phase = "upkeep"
            for trigger in self.event_game("upkeep").upkeep_triggers():
                source = next(p.card for player in self.players for p in player.battlefield
                              if p.card.id == trigger["source"])
                self.resolve_entry_triggers([trigger],source)
                if self.finished: return False
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
        elif self.phase in ("land", "main", "second_main"):
            choice = self.decide(self.active)
            if choice.kind == "pass":
                self.phase = {"land": "main", "main": "attack", "second_main": "cleanup"}[self.phase]
                self.log("pass", choice.label)
            elif choice.kind in ("crew","saddle"):
                game = self.event_game("main")
                getattr(game, choice.kind)(choice.card_id, list(choice.tap_ids), self.active)
                self.sync_events(game)
                self.log(choice.kind, choice.label, target=choice.card_id, tapped=list(choice.tap_ids))
            else:
                card = p.command_zone if choice.kind == "cast_commander" else next(c for c in p.hand if c.id == choice.card_id)
                if card is None: raise RuntimeError("Commander is no longer in command zone")
                if choice.kind == "land":
                    p.hand.remove(card)
                    lands = [replace(x.card,land_subtypes=tuple(x.card.event_definition.subtypes))
                             if x.card.event_definition else x.card
                             for x in p.battlefield if x.card.kind == "land" or
                             (x.card.event_definition and "Land" in x.card.event_definition.types)]
                    p.battlefield.append(Permanent(card, land_enters_tapped(card, lands)))
                    self.land_played = True
                    if self.phase == "land": self.phase = "main"
                    self.log("land", f"Player {self.active + 1} plays {card.name}.", card=card.name)
                else:
                    self.cast_spell(self.active,card,choice.x_value,choice.kind=='cast_commander',target=choice.target_permanent or choice.target_stack)
        elif self.phase == "attack":
            choice = self.decide(self.active)
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
                        if event.get('operation') in ('create_tokens','counter_power_tokens'):
                            self.resolve_entry_triggers([event],x.card)
                            if self.finished: return False
                            continue
                        self.log("trigger", f"{x.card.name}: {event['effect']}.",
                                 **{k:v for k,v in event.items() if k != "kind"})
        elif self.phase in ('first_damage','regular_damage'):
            self.strike_damage_step(self.phase=='first_damage')
        elif self.phase == "block":
            if not any(item.card.id==self.pending for item in p.battlefield):
                self.pending=None;self.phase='second_main'
                self.log('combat_skipped','The attacker has left the battlefield.')
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
            if early:
                self.combat_context=dict(attacker=a.card.id,blocker=b.card.id if b else None,blocked=b is not None,early=early)
                self.log('block',choice.label,actor=1-self.active,blocker=b.card.id if b else None)
                self.phase='first_damage'
                return True
            d = self.damage(effective_attacker, effective_blocker)
            dead_ids = ([a.card.id] if d["attackerDies"] else []) + ([b.card.id] if b and d["blockerDies"] else [])
            damage_triggers=[]
            if d['damage']>0:
                game=self.event_game('combat')
                from oracle_abilities import matches
                for watcher in game.battlefield.values():
                    for trigger in watcher.definition.triggers:
                        if trigger.event=='combat_damage' and matches(trigger.subject,watcher,game.battlefield[a.card.id],True):
                            damage_triggers.append({'controller':watcher.controller,'name':watcher.definition.name,'source':watcher.id,'target':1-self.active})
            death_triggers = self.event_game("combat").death_triggers(dead_ids)
            self.log("block", choice.label, actor=1-self.active,
                     blocker=b.card.id if b else None)
            p.life += d["gainA"]
            defender.life += d["gainB"] - d["damage"]
            if a.card.id == p.commander_id and d["damage"] > 0:
                defender.commander_damage[a.card.id] = defender.commander_damage.get(a.card.id, 0) + d["damage"]
            if d["attackerDies"]:
                self.send_to_destination(p, a)
            if b and d["blockerDies"]:
                self.send_to_destination(defender, b)
                if a.card.name == "Zurgo Helmsmasher" and not d["attackerDies"]:
                    a.counters += 1
                    self.log("trigger", "Zurgo gains a +1/+1 counter when the damaged creature dies.",
                             card=a.card.name, counters=a.counters)
            self.log("combat", "Combat damage resolves.", **d)
            self.pending = None
            self.outcome()
            if not self.finished:
                death_triggers.extend(dict(t,operation='discard',effect='discard') for t in damage_triggers)
                # APNAP: triggers of the nonactive player resolve first. Within a
                # controller's set, discovery order is a deterministic legal choice.
                for trigger in sorted(death_triggers, key=lambda t: t["controller"] == self.active):
                    controller = trigger["controller"]
                    if trigger["effect"] == "create tapped Squirrels":
                        entry_triggers = []
                        for _ in range(trigger["amount"]):
                            self.token_sequence += 1
                            definition = EventDefinition("Squirrel",frozenset({"Creature"}),frozenset({"Squirrel"}),
                                False,1,1,frozenset(),colors=frozenset({"Green"}))
                            token = Card(f"token-{self.token_sequence}","Squirrel","creature",traits="1;1;",
                                         power=1,toughness=1,event_definition=definition,is_token=True)
                            owner = self.players[controller]
                            entry_triggers.extend(self.enter_creature(token,owner))
                            next(p for p in owner.battlefield if p.card.id == token.id).tapped = True
                        self.log("trigger", f"Nested Shambler creates {trigger['amount']} tapped Squirrel tokens.", actor=controller, **trigger)
                        # Newly triggered abilities wait until this whole ability finishes.
                        if entry_triggers: self.resolve_entry_triggers(entry_triggers, token)
                        if self.finished: break
                        continue
                    # Use the same effect interpreter for entry, upkeep, and death.
                    # The event retains its controller even after its source leaves.
                    self.resolve_entry_triggers([trigger],a.card)
                    if self.finished: break
            if not self.finished: self.phase = "second_main"
        elif self.phase == "cleanup":
            # Deterministic discard is a declared sandbox rule, not a learned policy.
            while len(p.hand) > 7:
                c = p.hand.pop()
                p.graveyard.append(c)
                self.log("discard", f"Player {self.active+1} discards {c.name}.", card=c.name)
            for player in self.players:
                for item in player.battlefield:item.marked_damage=0
            game = self.event_game("cleanup")
            game.cleanup()
            self.sync_events(game)
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
        return {"schemaVersion": 1, "kind": "turn-replay", "mode": "sandbox-single-attacker-v1",
                "notice": "Synthetic classroom match; not a complete Commander game or Minecraft entity test.",
                "seed": self.seed, "starter": self.starter, "turns": self.turn, "result": self.result,
                "winner": self.winner, "learningEligible": not self.diagnostic and self.result in ("win", "draw") and not self.questions,
                "productionEligible": False, "policyVersions": [p.version for p in self.policies],
                "events": self.events, "questions": self.questions}



def diagnostic_land(definition: dict, identity: set[str]) -> dict | None:
    """Explicit land patterns in the submitted decks; no generalized Oracle guessing."""
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
    parsed = audit_card(rules, definition)
    event_definition = parse_event_card(definition)
    allowed = (definition["name"] in ("Kolodin, Triumph Caster", "Zurgo Helmsmasher", "Brightfield Mustang", "Nested Shambler")
               or bool(event_definition.triggers or event_definition.static_effects or event_definition.attack_effects) or "Vehicle" in definition.get("subTypes", []))
    cost = definition.get("manaCost") or ""
    if (parsed["kind"] == "unsupported" and allowed and event_definition.supported
            and rules.query("cost",cost)["supported"]):
        keywords = sorted(event_definition.abilities)
        parsed = {"kind":("vehicle" if "Vehicle" in event_definition.subtypes else
                          "creature" if "Creature" in event_definition.types else "enchantment"),
                  "power":event_definition.power,"toughness":event_definition.toughness,
                  "traits":f"{event_definition.power};{event_definition.toughness};"+",".join(keywords),
                  "event":event_definition}
    if parsed["kind"] == "unsupported":
        text = definition.get("oracleText", "")
        token_spec = parse_token_creation(text)
        if definition.get("types") == ["Sorcery"] and token_spec and rules.query("cost",cost)["supported"]:
            template = EventDefinition(" ".join(token_spec.subtypes),frozenset({"Land","Creature"} if token_spec.land else {"Creature"}),frozenset(token_spec.subtypes),
                False,token_spec.power,token_spec.toughness,token_spec.keywords,colors=frozenset(token_spec.colors))
            parsed = {"kind":"token_spell", "token_count":token_spec.amount,
                      "token_definition":template,"token_tapped":token_spec.tapped}
        else:
            parsed = diagnostic_land(definition, identity) or parsed
    storm_text=rule_text(definition.get('oracleText',''))
    storm_lines=storm_text.splitlines()
    if (parsed['kind']=='unsupported' and definition.get('types')==['Sorcery'] and len(storm_lines)==2
            and storm_lines[1]=='Storm' and rules.query('cost',cost)['supported']):
        spec=parse_token_creation(storm_lines[0])
        if spec:
            template=EventDefinition(' '.join(spec.subtypes),frozenset({'Land','Creature'} if spec.land else {'Creature'}),
                frozenset(spec.subtypes),False,spec.power,spec.toughness,spec.keywords,colors=frozenset(spec.colors))
            parsed={'kind':'token_spell','token_count':spec.amount,'token_definition':template,'token_tapped':spec.tapped,'storm':True}
    if (parsed['kind']=='unsupported' and definition.get('types') in (['Instant'],['Sorcery'])
            and rule_text(definition.get('oracleText',''))=='Destroy target creature.' and rules.query('cost',cost)['supported']):
        parsed={'kind':'removal_spell','removal':'destroy'}
    counter=re.fullmatch(r'Counter target (?:(creature|noncreature) )?spell\.',rule_text(definition.get('oracleText','')))
    if (parsed['kind']=='unsupported' and definition.get('types')==['Instant'] and counter
            and rules.query('cost',cost)['supported']):
        parsed={'kind':'counter_spell','counter_filter':counter[1] or 'any'}
    variable=x_spells.parse(cost,definition.get('oracleText',''),definition.get('types',[]))
    if parsed['kind']=='unsupported' and variable:
        parsed={'kind':'x_spell','x_effect':variable['effect']}
        if variable['effect']=='tokens':
            spec=variable['token']
            parsed['token_definition']=EventDefinition(' '.join(spec.subtypes),frozenset({'Land','Creature'} if spec.land else {'Creature'}),frozenset(spec.subtypes),
                False,spec.power,spec.toughness,spec.keywords,colors=frozenset(spec.colors))
            parsed['token_tapped']=spec.tapped
    output=mana_pool.production(definition.get("oracleText", ""))
    if (parsed["kind"]=="unsupported" and definition.get("types")==["Artifact"]
            and output and rules.query("cost",cost)["supported"]):
        parsed={"kind":"mana_artifact","mana_production":output}
    return Card(id=uid, name=definition["name"], kind=parsed["kind"],
        instant="Instant" in definition.get("types",[]), counter_filter=parsed.get("counter_filter",""), removal=parsed.get("removal",""), mana_cost=cost, mana_production=parsed.get("mana_production",()), traits=parsed.get("traits", ""), power=parsed.get("power", 0),
        toughness=parsed.get("toughness", 0), mask=parsed.get("mask", 0),
        enters_tapped=parsed.get("tapped", False), draw=parsed.get("draw", 0),
        life=parsed.get("life", 0), land_rule=parsed.get("land_rule", ""),
        land_subtypes=tuple(definition.get("subTypes", [])),
        basic_land="Basic" in definition.get("superTypes", []), event_definition=parsed.get("event"),
        storm=parsed.get("storm",False), x_effect=parsed.get("x_effect",""), token_count=parsed.get("token_count",0),
        token_definition=parsed.get("token_definition"),token_tapped=parsed.get("token_tapped",False),
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
                      c.get("saddled",False),c.get("counters",0)] for c in p["battlefield"]]
            grave = [reference(c) for c in p["graveyard"]]
            players.append([p["life"],p["handCount"],p["libraryCount"],field,grave,
                            p.get("commanderInZone",False),p.get("commanderDamage",{})])
        events.append([e["index"],e["turn"],e["phase"],e["actor"],e["kind"],e["message"],
                       e["details"],[state["active"],state["turn"],state["phase"],players]])
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
