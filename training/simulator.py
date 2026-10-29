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
    printed_types: tuple[str, ...] = ()
    printed_mana_value: int | None = None
    physical_id: str = ""
    blink: bool = False
    rebound: bool = False
    blink_to_controller: bool = False
    flashback_cost: str = ""



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
        self.object_sequence=0
        self._rebound_permission=None
        self.pending: str | None = None
        self.land_played = False
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
        self.life_gained_turn=[0,0]
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
                if self.diagnostic and card.kind=="removal_spell" and card.removal in ("destroy","opponent_nonlands","destroy_artifact_enchantment","destroy_artifact_creature_token","exile_creature_life","exile_creature_basic_land","destroy_all_creatures","destroy_toughness_min"):
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
                "hexproof": bool(state and game.has(state,'hexproof')), "wardCosts": list(game.ward_costs(state)) if state else [], "loyalty": item.loyalty, "chargeCounters": item.charge_counters}

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
                definition=replace(definition,mana_cost=card.mana_cost)
                game.battlefield[card.id] = EventPermanent(card.id, definition, seat, item.tapped,
                    item.fresh, item.saddled, item.animated, counters=item.counters, token=item.card.is_token,temporary_power=item.temporary_power,
                    temporary_toughness=item.temporary_toughness,temporary_abilities=item.temporary_abilities,attached_to=item.attached_to,
                    entered_at=item.entered_at,attachment_at=item.attachment_at,lost_abilities=dict(item.lost_abilities),
                    temporary_ability_times=dict(item.temporary_ability_times),loyalty=item.loyalty,charge_counters=item.charge_counters)
        return game

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
                        "shroud", "plainswalk", "islandwalk", "swampwalk", "mountainwalk", "forestwalk"):
            if game.has(state, ability): keywords.add(ability)
        return replace(item.card, kind="creature", power=power, toughness=toughness,
                       traits=f"{power};{toughness};"+",".join(sorted(keywords)))

    def land_entry_tapped(self,card,seat,entry_logs):
        player=self.players[seat]
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
        lands=[replace(p.card,land_subtypes=tuple(p.card.event_definition.subtypes)) if p.card.event_definition else p.card
               for p in player.battlefield if p.card.kind=='land' or p.card.event_definition and 'Land' in p.card.event_definition.types]
        return land_enters_tapped(card,lands)

    def enter_creature(self, card: Card, player: Player, attached_to=None):
        return self.enter_creatures([card],player,attached_targets={card.id:attached_to} if attached_to else None)

    def enter_creatures(self, cards, player: Player, bestowed_targets=None, attached_targets=None):
        game=self.event_game('main')
        game._next_token=self.token_sequence
        known=set(game.battlefield)
        controller=next(i for i,candidate in enumerate(self.players) if candidate is player)
        entrants=[];entry_logs=[]
        bestowed_targets=bestowed_targets or {}
        attached_targets=dict(attached_targets or {},**bestowed_targets)
        for card in cards:
            definition=card.event_definition
            if definition is None:
                definition=EventDefinition(card.name,frozenset(card.printed_types or (('Land',) if card.kind=='land' else ('Creature',))),frozenset(card.land_subtypes),card.legendary,
                    card.power,card.toughness,frozenset(k for k in card.traits.split(';')[-1].split(',') if k),
                    colors=frozenset(card.colors))
            if card.id in bestowed_targets:definition=self.bestowed_definition(definition)
            enters_tapped=self.land_entry_tapped(card,controller,entry_logs) if card.kind=='land' else card.enters_tapped
            entrants.append(EventPermanent(card.id,replace(definition,mana_cost=card.mana_cost),controller,tapped=enters_tapped,
                                           attached_to=attached_targets.get(card.id)))
        game.life_totals={seat:p.life for seat,p in enumerate(self.players)}
        game.enter_batch(entrants)
        self.entry_history.extend(dict(turn=self.turn,controller=controller,subtypes=sorted(p.definition.subtypes)) for p in entrants)
        player.battlefield.extend(Permanent(card,attached_to=attached_targets.get(card.id),bestowed=card.id in bestowed_targets) for card in cards)
        for token_id in game.battlefield.keys()-known-{card.id for card in cards}:
            token_state=game.battlefield[token_id]
            if not token_state.token:raise RuntimeError('Unknown event-created permanent')
            d=token_state.definition
            token=Card(token_id,d.name,'creature',traits=f'{d.power};{d.toughness};'+','.join(sorted(d.abilities)),
                       power=d.power,toughness=d.toughness,event_definition=d,is_token=True)
            player.battlefield.append(Permanent(token))
        self.token_sequence=game._next_token
        self.sync_events(game)
        for kind,message,details in entry_logs:self.log(kind,message,**details)
        return [event for event in game.events if event['kind']=='trigger']

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
            invalid_auras=[];detached=[]
            for owner,player in enumerate(self.players):
                for item in player.battlefield:
                    if item.card.kind not in ('aura','equipment') and not item.bestowed:continue
                    target=game.battlefield.get(item.attached_to)
                    if target and game.creature(target) and not game.protected(target,item.card.colors):continue
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
            if not dead and not invalid_auras and not detached:break
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
                if event.get('operation')=='create_role':
                    targets=self.role_targets(event)
                    chosen=next((p for p in targets if p.card.id==event.get('target')),None) if event.get('target') else max(targets,key=lambda p:(self.effective_card(p).power,p.card.id),default=None)
                    if chosen is None:
                        self.log('role_no_target','No legal other creature for the Role trigger.',source=event['source'])
                        continue
                    event=dict(event,target=chosen.card.id)
                item=self.stack.push(controller,(event,origin),event.get('name',origin.name))
                self.log('stack_push',f'{item.label} ability goes on the stack.',stackId=item.id,controller=controller)
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

    def response_choices(self,seat):
        if seat!=self.stack.priority: return ()
        return tuple(c for c in self.players[seat].hand if c.instant and c.kind in ('spell','token_spell','counter_spell','removal_spell','blink_spell')
                     and (not c.draw or c.draw<=len(self.players[seat].library))
                     and self.payment(c,seat=seat)['paid'])

    def token_ability_choices(self,seat):
        result=[]
        for source in self.players[seat].battlefield:
            definition=source.card.event_definition
            for index,(cost,spec) in enumerate(definition.activations if definition else ()):
                payment=self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)
                if payment['paid']:
                    result.append(Candidate(source.card.id+':activate:'+str(index),'activate_tokens',source.card.id,
                        features=features(power=spec.amount*spec.power,toughness=spec.amount*spec.toughness,
                                          cost=len(payment['sources'])),label='Activate '+source.card.name,activation_index=index))
        return result

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

    def equip_choices(self,seat):
        choices=[]
        for source in self.players[seat].battlefield:
            if source.card.kind!='equipment' or source.attached_to:continue
            cost=source.card.event_definition.attachment[1]
            if not self.payment(replace(source.card,mana_cost=cost),seat=seat,spell_cost=False)['paid']:continue
            for owner,target in self.creature_targets(seat,source.card):
                if owner==seat and source.attached_to!=target.card.id:
                    choices.append(Candidate(source.card.id+':equip:'+target.card.id,'equip',source.card.id,
                        features=features(power=.5),label='Equip '+source.card.name,target_permanent=target.card.id))
        return choices

    def activate_equip(self,seat,source_id,target):
        if self.stack.items or self.stack.priority!=seat or seat!=self.active or self.phase not in ('main','second_main'):raise ValueError('Illegal equip timing')
        source=next((p for p in self.players[seat].battlefield if p.card.id==source_id and p.card.kind=='equipment'),None)
        if source is None or target not in {p.card.id for owner,p in self.creature_targets(seat,source.card) if owner==seat}:raise ValueError('Illegal equip target')
        payment=self.payment(replace(source.card,mana_cost=source.card.event_definition.attachment[1]),seat=seat,spell_cost=False)
        if not payment['paid']:raise ValueError('Cannot pay equip')
        for p in self.players[seat].battlefield:
            if p.card.id in payment['sources']:p.tapped=True
        self.players[seat].mana_pool=list(payment['pool'])
        self.resolve_entry_triggers([dict(operation='attach',source=source_id,target=target,controller=seat,name=source.card.name)],source.card)

    def creature_targets(self,controller=None,source=None):
        game=self.event_game('main')
        return tuple((seat,item) for seat,player in enumerate(self.players) for item in player.battlefield
                     if item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])
                     and not game.has(game.battlefield[item.card.id],'shroud')
                     and (controller is None or seat==controller or not game.has(game.battlefield[item.card.id],'hexproof'))
                     and (source is None or not game.protected(game.battlefield[item.card.id],source.colors)))

    def controlled_land_count(self, seat):
        return sum(item.card.kind=='land' or
                   (item.card.event_definition is not None and
                    'Land' in item.card.event_definition.types)
                   for item in self.players[seat].battlefield)

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

    def removal_targets(self,controller,source):
        """Only legal targets for an explicitly parsed targeted removal spell."""
        if source.removal in ('destroy','exile_creature_life','exile_creature_basic_land'):return self.creature_targets(controller,source)
        if source.removal not in ('destroy_artifact_enchantment','destroy_artifact_creature_token'):return ()
        game=self.event_game('main')
        targets=[]
        for seat,player in enumerate(self.players):
            for item in player.battlefield:
                types=set(item.card.printed_types)
                if item.card.event_definition:types.update(item.card.event_definition.types)
                allowed={'Artifact','Enchantment'} if source.removal=='destroy_artifact_enchantment' else {'Artifact','Creature'}
                if not types.intersection(allowed) and not (source.removal=='destroy_artifact_creature_token' and
                        item.card.id in game.battlefield and game.creature(game.battlefield[item.card.id])):continue
                state=game.battlefield.get(item.card.id)
                if state and game.has(state,'shroud'):continue
                if state and seat!=controller and game.has(state,'hexproof'):continue
                if state and game.protected(state,source.colors):continue
                targets.append((seat,item))
        return tuple(targets)

    def removal_choices(self,seat,card,kind):
        if card.removal in ('opponent_nonlands','destroy_all_creatures','destroy_toughness_min'):
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

    def nonland_destruction_set(self,controller):
        game=self.event_game('main')
        return tuple((owner,item) for owner,player in enumerate(self.players) if owner!=controller
                     for item in player.battlefield if item.card.kind!='land'
                     and not (item.card.event_definition and 'Land' in item.card.event_definition.types)
                     and not (item.card.id in game.battlefield and game.has(game.battlefield[item.card.id],'indestructible')))

    def destroy_batch(self,targets,card,reason="destroy"):
        game=self.event_game('main')
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
        self.resolve_entry_triggers(triggers,card)

    def counter_stack_item(self,frame):
        removed=self.stack.counter(frame.id)
        if removed and removed.payload[0].get('operation')=='spell' and not removed.payload[0].get('copy'):
            owner=self.players[removed.controller];countered=removed.payload[1]
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
        actions.extend(self.token_ability_choices(seat))
        actions.extend(self.strip_ability_choices(seat))
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
        if choice.kind=='activate_strip':
            self.activate_strip(seat,choice.card_id,choice.activation_index)
            return 'activate'
        if choice.kind=='activate_tokens':
            self.activate_tokens(seat,choice.card_id,choice.activation_index)
            return 'activate'
        card=next(c for c in self.players[seat].hand if c.id==choice.card_id)
        self.cast_spell(seat,card,target=choice.target_permanent or choice.target_stack)
        return 'cast'

    def cast_spell(self,seat,card,x=None,commander=False,target=None,bestow=False,rebound=False,flashback=False):
        player=self.players[seat]
        if not card.instant and seat!=self.stack.priority: raise ValueError('Player lacks priority')
        if self.stack.items:
            if seat!=self.stack.priority or not card.instant: raise ValueError('Spell timing or priority invalid')
        elif seat!=self.active or self.phase not in ('main','second_main'):
            if not card.instant or seat!=self.stack.priority: raise ValueError('Spell timing invalid')
        if rebound and self._rebound_permission!=(seat,root(card)):raise ValueError('No rebound casting permission')
        if flashback and (commander or rebound or bestow or not card.flashback_cost):
            raise ValueError('No supported flashback permission')
        casting_zone=player.exile if rebound else player.graveyard if flashback else player.hand
        if not commander and card not in casting_zone: raise ValueError('Card not in casting zone')
        if bestow and (not card.event_definition or not card.event_definition.bestow):raise ValueError('Card has no supported bestow ability')
        if (card.kind=='aura' or bestow) and target not in {p.card.id for _,p in self.creature_targets(seat,card)}:raise ValueError('Illegal Aura target')
        if card.kind=='removal_spell' and card.removal not in ('opponent_nonlands','destroy_all_creatures','destroy_toughness_min') and target not in {item.card.id for _,item in self.removal_targets(seat,card)}:
            raise ValueError('Removal requires a legal permanent target')
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
        else:casting_zone.remove(card)
        prior=sum(e['kind']=='cast' and e['turn']==self.turn for e in self.events)
        self.stack.active=self.active
        frame=self.stack.push(seat,({'operation':'spell','controller':seat,'x':x,'target':target,'bestow':bestow,'flashback':flashback,'fromHand':not rebound and not flashback and not commander},card),card.name)
        self.log('cast',f'Player {seat+1} casts {card.name}.',actor=seat,card=card.name,
                 manaSources=payment['sources'],manaPool=list(player.mana_pool),commander=commander,xValue=x,bestow=bestow,rebound=rebound,flashback=flashback,targetStack=target if card.kind=='counter_spell' else None,
                 targetPermanent=target if card.kind=='removal_spell' else None)
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
            if event['target'] not in {p.card.id for _,p in self.creature_targets(controller,card)}:
                if not event.get('copy'):p.graveyard.append(card)
                self.log('illegal_target',f'{card.name} has no legal Aura target.')
                return
            pending=self.enter_creature(card,p,attached_to=event['target'])
            self.resolve_entry_triggers(pending,card)
            self.log('attach',f'{card.name} enchants a creature.',targetPermanent=event['target'])
            return
        if card.kind=='equipment':
            self.enter_creature(card,p)
            return
        if card.kind in ('creature','vehicle','enchantment','planeswalker','station','artifact'):
            triggers=self.enter_creature(card,p)
            self.resolve_entry_triggers(triggers,card)
        elif card.kind=='mana_artifact': p.battlefield.append(Permanent(card))
        elif not event.get('copy'):
            (p.exile if event.get('flashback') else p.graveyard).append(original)
        if card.kind=='removal_spell':
            if card.removal in ('destroy_all_creatures','destroy_toughness_min'):
                threshold=card.removal_min_toughness if card.removal=='destroy_toughness_min' else 0
                self.destroy_batch(self.creature_board_destruction_set(threshold),card)
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
            self.counter_stack_item(frame)
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
                created=self.event_game('main').token_amount(controller,card.token_count)
                for _ in range(created):
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
            if event.get('operation')=='create_role':
                self.resolve_role(event)
                continue
            if event.get('operation')=='ordered_effects':
                for part in event['steps']:
                    self._resolve_entry_effects([{**event,**part}],card)
                    if self.finished:return
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
                    self.counter_stack_item(frame)
                    self.log('ward_counter',f"{event['name']} counters {frame.label} because ward was not paid.",
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
            if event.get('operation')=='subtype_count_boost':
                game=self.event_game('combat');source=game.battlefield.get(event['source'])
                if source:
                    count=sum(other.id!=source.id and other.controller==source.controller and event['subtype'] in other.definition.subtypes
                              for other in game.battlefield.values())
                    source.temporary_power+=event['power']*count;source.temporary_toughness+=event['toughness']*count
                    self.sync_events(game)
                self.log('subtype_count_boost',f"{event['name']} resolves its temporary attack bonus.",source=event['source'])
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
            if event.get("operation") == "create_tokens":
                if event.get('optional') and not self.choose_optional_token_creation(event):
                    self.log('token_creation_declined','Optional token creation declined.',
                             actor=event['controller'],source=event['source'])
                    continue
                spec=event["tokenSpec"]
                owner=self.players[event["controller"]]
                pending=[]
                owner.life -= event.get("controllerLoss",0)
                created=self.event_game('main').token_amount(event['controller'],spec['amount'])
                event=dict(event,tokenSpec=dict(spec,amount=created))
                for _ in range(created):
                    self.token_sequence+=1
                    definition=EventDefinition(" ".join(spec["subtypes"]),frozenset({"Creature"}|({"Land"} if spec.get("land") else set())|({"Enchantment"} if spec.get("enchantment") else set())),frozenset(spec["subtypes"]),
                        False,spec["power"],spec["toughness"],frozenset(spec["keywords"]),colors=frozenset(spec["colors"]),pilot_bonus=spec.get("contribution_bonus",0))
                    token=Card(f"token-{self.token_sequence}",definition.name,"creature",
                        traits=f"{definition.power};{definition.toughness};"+",".join(sorted(definition.abilities)),
                        power=definition.power,toughness=definition.toughness,event_definition=definition,is_token=True)
                    pending.extend(self.enter_creature(token,owner))
                    next(p for p in owner.battlefield if p.card.id==token.id).tapped=spec["tapped"]
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
                if source and event['target'] in {p.card.id for owner,p in self.creature_targets(event['controller'],source.card) if owner==event['controller']}:
                    if source.attached_to!=event['target']:
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
                source=next((item for player in self.players for item in player.battlefield if item.card.id==event['source']),None)
                if source:
                    game=self.event_game('main')
                    source.counters+=game.counter_amount(source.card.id,event['amount'])
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
        triggers=game.death_triggers([item.card.id for item in dead])
        triggers.extend(game.aura_damage_triggers(dealt,1-self.active))
        if to_player and attacker:
            triggers.extend(game.combat_draw_triggers(attacker.card.id))
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
                        if attached.card.is_token:
                            # An Aura Role token also leaves when its host
                            # disappears; this is another real token-leave
                            # event, not a sacrifice. Snapshot before either
                            # permanent is removed from the battlefield.
                            game=snapshot or self.event_game('main')
                            self._waiting_triggers.extend((event,attached.card)
                                for event in game.token_leave_events(owner_index,1))
                        owner.battlefield.remove(attached)
                        if not attached.card.is_token:owner.graveyard.append(attached.card)
        destination=self.players[self.card_owners.get(root(item.card),next(i for i,p in enumerate(self.players) if p is player))]
        player.battlefield.remove(item)
        if item.card.is_token:
            return  # Tokens cease to exist after leaving the battlefield.
        if root(item.card) == destination.commander_id:
            destination.command_zone = item.card  # This prototype chooses the command-zone option.
        elif to_hand:
            destination.hand.append(item.card)
        elif to_exile:
            destination.exile.append(item.card)
        else:
            destination.graveyard.append(item.card)

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

    def mana_sources(self, seat: int):
        sources=[]
        for item in self.players[seat].battlefield:
            if item.tapped: continue
            definition=item.card.event_definition
            mask=item.card.mask if item.card.kind=='land' else 0
            if definition and 'Land' in definition.types:
                mask|=sum(bit for subtype,bit in {'Plains':1,'Island':2,'Swamp':4,'Mountain':8,'Forest':16}.items()
                         if subtype in definition.subtypes)
                if 'Creature' in definition.types and item.fresh:
                    effective=self.effective_card(item)
                    if effective is None or 'haste' not in effective.traits.split(';')[-1].split(','): continue
            if item.card.kind=='land' and item.card.mana_production:
                options=(item.card.mana_production,)
            elif mask:
                options=tuple(tuple(int(i==color) for i in range(6)) for color in range(6) if mask&(1<<color))
            elif item.card.kind=='mana_artifact': options=(item.card.mana_production,)
            else: continue
            sources.append((item.card.id,options))
        return sources

    def payment(self, card: Card, tax: int = 0, x: int | None = None, seat: int | None = None,
                spell_cost: bool = True) -> dict:
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
            if not self.land_played:
                for c in p.hand:
                    if c.kind == "land":
                        actions.append(Candidate(c.id, "land", c.id, features(power=1), "Play " + c.name))
        elif self.phase in ("main", "second_main"):
            if self.diagnostic: actions.extend(self.activation_choices(seat, {"crew","saddle"}))
            actions.extend(self.special_choices(seat))
            actions.extend(self.equip_choices(seat))
            actions.extend(self.token_ability_choices(seat))
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
            for c in p.hand:
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
                        for owner,target in self.creature_targets(seat,c))
                    continue
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
                           "history_tokens","activate_tokens","activate_strip"):
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
            self.turn_development[self.active]=False
            self.life_gained_turn=[0,0]
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
        elif self.phase in ("land", "main", "second_main"):
            choice = self.decide(self.active)
            if choice.kind == "pass":
                self.phase = {"land": "main", "main": "attack", "second_main": "end_step"}[self.phase]
                self.log("pass", choice.label)
            elif choice.kind=='station':
                self.activate_station(self.active,choice.card_id,choice.tap_ids[0])
            elif choice.kind=='history_tokens':
                self.activate_history(self.active,choice.card_id)
            elif choice.kind=='activate_strip':
                self.activate_strip(self.active,choice.card_id,choice.activation_index)
            elif choice.kind=='activate_tokens':
                self.activate_tokens(self.active,choice.card_id,choice.activation_index)
            elif choice.kind=='equip':
                self.activate_equip(self.active,choice.card_id,choice.target_permanent)
            elif choice.kind in ('crew','saddle'):
                self.activate_transport(self.active,choice.kind,choice.card_id,choice.tap_ids)
            else:
                card = (p.command_zone if choice.kind == "cast_commander" else
                        next(c for c in (p.graveyard if choice.kind == "cast_flashback" else p.hand)
                             if c.id == choice.card_id))
                if card is None: raise RuntimeError("Commander is no longer in command zone")
                if choice.kind == "land":
                    p.hand.remove(card)
                    pending=self.enter_creature(card,p)
                    self.land_played = True
                    if self.phase == "land": self.phase = "main"
                    self.log("land", f"Player {self.active + 1} plays {card.name}.", card=card.name)
                    self.resolve_entry_triggers(pending,card)
                else:
                    self.cast_spell(self.active,card,choice.x_value,choice.kind=='cast_commander',
                        target=choice.target_permanent or choice.target_stack,
                        bestow=choice.kind=='bestow',flashback=choice.kind=='cast_flashback')
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
                        if event.get('operation') in ('create_tokens','counter_power_tokens','subtype_count_boost'):
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
            dead_ids = ([a.card.id] if d["attackerDies"] else []) + ([b.card.id] if b and d["blockerDies"] else [])
            damage_triggers=[];combat_draws=[]
            if d['damage']>0:
                game=self.event_game('combat')
                combat_draws=game.combat_draw_triggers(a.card.id)
                from oracle_abilities import matches
                for watcher in game.battlefield.values():
                    for trigger in watcher.definition.triggers:
                        if trigger.event=='combat_damage' and matches(trigger.subject,watcher,game.battlefield[a.card.id],True):
                            damage_triggers.append({'controller':watcher.controller,'name':watcher.definition.name,'source':watcher.id,'target':1-self.active})
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
                death_triggers.extend(dict(t,operation='discard',effect='discard') for t in damage_triggers)
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
                self.resolve_entry_triggers([],Card('end-step','End step','spell'))
                return True
            if self.stack.items:
                raise ValueError('Cannot leave end step with unresolved stack items')
            self.phase='cleanup'
            return True
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
        composed['event']=EventDefinition(definition['name'],frozenset({'Land'}),frozenset(definition.get('subTypes',[])),
            'Legendary' in definition.get('superTypes',[]),0,0,program.keywords,triggers=program.triggers)
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
    parsed = audit_card(rules, definition)
    event_definition = parse_event_card(definition)
    allowed = (definition["name"] in ("Kolodin, Triumph Caster", "Zurgo Helmsmasher", "Brightfield Mustang", "Nested Shambler")
               or bool(event_definition.triggers or event_definition.static_effects or event_definition.attack_effects or event_definition.attachment or event_definition.activations or event_definition.devotion or event_definition.bestow or bool({"hexproof", "menace","shroud"} & event_definition.abilities) or any(k.startswith('block_power_below_') for k in event_definition.abilities) or "Planeswalker" in event_definition.types or event_definition.role_events or event_definition.enchanted_draw or event_definition.life_multiplier!=1 or event_definition.life_addition or event_definition.cost_reductions or event_definition.counter_replacements or event_definition.entry_counter_grants or event_definition.token_replacements or event_definition.token_action_triggers or event_definition.token_leave_triggers or event_definition.opponent_creatures_enter_tapped or event_definition.station or event_definition.history_activation or event_definition.crew is not None or event_definition.saddle is not None) or "Vehicle" in definition.get("subTypes", []))
    cost = definition.get("manaCost") or ""
    if (parsed["kind"] == "unsupported" and allowed and event_definition.supported
            and rules.query("cost",cost)["supported"]):
        keywords = sorted(event_definition.abilities)
        parsed = {"kind":("vehicle" if "Vehicle" in event_definition.subtypes else
                          "creature" if "Creature" in event_definition.types else
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
    if (parsed['kind']=='unsupported' and definition.get('types')==['Sorcery']
            and rules.query('cost',cost)['supported']):
        # Whole-text recognition; regeneration prohibition is represented
        # by the current sandbox's lack of regeneration effects.
        if destruction in ('Destroy all creatures.',
                           "Destroy all creatures. They can't be regenerated."):
            parsed={'kind':'removal_spell','removal':'destroy_all_creatures'}
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
    output=mana_pool.production(definition.get("oracleText", ""))
    if (parsed["kind"]=="unsupported" and definition.get("types")==["Artifact"]
            and output and rules.query("cost",cost)["supported"]):
        parsed={"kind":"mana_artifact","mana_production":output}
    return Card(id=uid, name=definition["name"], kind=parsed["kind"],blink=parsed.get("blink",False),rebound=parsed.get("rebound",False),blink_to_controller=parsed.get("blink_to_controller",False),flashback_cost=parsed.get("flashback_cost",""),
        instant="Instant" in definition.get("types",[]), counter_filter=parsed.get("counter_filter",""), removal=parsed.get("removal",""), removal_min_toughness=parsed.get("removal_min_toughness",0), mana_cost=cost, mana_production=parsed.get("mana_production",()), traits=parsed.get("traits", ""), power=parsed.get("power", 0),
        toughness=parsed.get("toughness", 0), mask=parsed.get("mask", 0),
        enters_tapped=parsed.get("tapped", False), draw=parsed.get("draw", 0),
        life=parsed.get("life", 0), land_rule=parsed.get("land_rule", ""),
        land_subtypes=tuple(definition.get("subTypes", [])),
        basic_land="Basic" in definition.get("superTypes", []), event_definition=parsed.get("event") or (event_definition if event_definition.supported and "Planeswalker" in event_definition.types else None),
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
