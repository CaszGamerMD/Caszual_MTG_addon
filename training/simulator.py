#!/usr/bin/env python3
"""Independent self-play sandbox, strict real-deck intake, and human-readable replays.
The existing Java subset is the authority for card parsing, mana and combat.
This is NOT a complete Commander rules engine or a Minecraft entity test.
"""
from __future__ import annotations
import argparse
import base64
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FEATURES = ("power", "toughness", "evasion", "haste", "lethal", "damage",
            "survive", "life", "draw", "cost", "pass")
DEFAULT_WEIGHTS = dict(zip(FEATURES, (1., .3, .8, .6, 100., 3., 1., .2, .7, -.1, -2.)))


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
    enters_tapped: bool = False
    draw: int = 0
    life: int = 0


@dataclass
class Permanent:
    card: Card
    tapped: bool = False
    fresh: bool = True


@dataclass
class Player:
    library: list[Card]
    hand: list[Card] = field(default_factory=list)
    battlefield: list[Permanent] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    life: int = 40
    failed_draw: bool = False


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    card_id: str = ""
    features: tuple[float, ...] = ()
    label: str = ""


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
        p, t, cost, keywords = ((2, 2, "{1}{G}", ""), (3, 3, "{2}{G}", ""),
                               (1, 1, "{G}", "haste"), (4, 4, "{3}{G}", "trample"),
                               (2, 3, "{2}{G}", "vigilance"), (2, 2, "{2}{G}", "lifelink"),
                               (2, 2, "{2}{G}", "double strike"))[i % 7]
        result.append(Card(f"{seat}-creature-{i}", "Training creature " + str(i + 1), "creature",
                           cost, f"{p};{t};{keywords}", p, t))
    return result


class Simulator:
    """Deterministic classroom turn model. No priority, stack, commanders or multi-attack combat."""
    def __init__(self, rules: RulesBridge, seed: int, starter: int = 0,
                 policies: tuple[Policy, Policy] = (Policy(), Policy()), max_turns: int = 100,
                 decks: tuple[list[Card], list[Card]] | None = None, starting_life: int = 40):
        if starter not in (0, 1) or max_turns < 1 or starting_life < 1:
            raise ValueError("Invalid simulation options")
        self.rules, self.seed, self.starter = rules, seed, starter
        self.policies = tuple(replace(p) for p in policies)  # frozen per-match snapshots
        self.max_turns = max_turns
        self.players = []
        for seat, cards in enumerate(decks or (demo_deck(0), demo_deck(1))):
            cards = list(cards)
            random.Random(seed * 2 + seat).shuffle(cards)
            self.players.append(Player(cards, life=starting_life))
        if len({c.id for p in self.players for c in p.library}) != sum(len(p.library) for p in self.players):
            raise ValueError("Card identities must be unique")
        self.total_cards = tuple(len(p.library) for p in self.players)
        self.turn, self.active, self.phase = 0, starter, "setup"
        self.events: list[dict] = []
        self.decisions: list[dict] = []  # post-match data; never supplied to either player
        self.questions: list[dict] = []
        self.finished = False
        self.winner: int | None = None
        self.result = "running"
        self.pending: str | None = None
        self.land_played = False
        self.main_return = ""
        self.log("setup", "Two independent agents use frozen policies; sandbox rules apply.")
        for player in self.players:
            for card in player.library:
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

    def state(self) -> dict:
        return {"active": self.active, "turn": self.turn, "phase": self.phase,
                "players": [{"seat": i, "life": p.life, "handCount": len(p.hand),
                             "libraryCount": len(p.library),
                             "battlefield": [{"id": x.card.id, "name": x.card.name,
                                              "kind": x.card.kind, "power": x.card.power,
                                              "toughness": x.card.toughness, "traits": x.card.traits,
                                              "tapped": x.tapped, "fresh": x.fresh} for x in p.battlefield],
                             "graveyard": [{"id": c.id, "name": c.name} for c in p.graveyard]}
                            for i, p in enumerate(self.players)]}

    def invariant(self):
        for i, p in enumerate(self.players):
            cards = p.library + p.hand + p.graveyard + [x.card for x in p.battlefield]
            if len(cards) != self.total_cards[i] or len({c.id for c in cards}) != len(cards):
                raise RuntimeError("Card conservation failed")

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
        dead = [p.life <= 0 or p.failed_draw for p in self.players]
        if any(dead):
            self.finished = True
            self.winner = None if all(dead) else (1 if dead[0] else 0)
            self.result = "draw" if self.winner is None else "win"
            reasons = [["zero life" if p.life <= 0 else None, "failed draw" if p.failed_draw else None] for p in self.players]
            self.log("result", "Draw." if self.winner is None else f"Player {self.winner + 1} wins.",
                     lossReasons=[[r for r in row if r] for row in reasons])

    def payment(self, card: Card) -> dict:
        return self.rules.query("pay", card.mana_cost, *[
            x.card.id + ":" + str(x.card.mask) for x in self.players[self.active].battlefield
            if x.card.kind == "land" and not x.tapped])

    def damage(self, a: Card, b: Card | None) -> dict:
        return self.rules.query("combat", a.traits, b.traits if b else "",
                                self.players[self.active].life, self.players[1 - self.active].life)

    def legal(self, seat: int) -> tuple[Candidate, ...]:
        p = self.players[seat]
        actions = []
        if self.phase == "land":
            if not self.land_played:
                for c in p.hand:
                    if c.kind == "land":
                        actions.append(Candidate(c.id, "land", c.id, features(power=1), "Play " + c.name))
        elif self.phase in ("main", "second_main"):
            for c in p.hand:
                if c.kind in ("creature", "spell") and self.payment(c)["paid"]:
                    if c.draw and len(p.library) < c.draw:
                        continue  # never choose a known self-decking draw spell
                    keywords = c.traits.split(";")[-1].split(",") if c.traits else []
                    actions.append(Candidate(c.id, "cast", c.id,
                        features(power=c.power, toughness=c.toughness,
                                 evasion=int(any(k in keywords for k in ("flying", "shadow", "horsemanship", "skulk"))),
                                 haste=int("haste" in keywords), life=c.life, draw=c.draw,
                                 cost=len(self.payment(c).get("sources", []))), "Cast " + c.name))
        elif self.phase == "attack":
            for x in p.battlefield:
                c = x.card
                if c.kind != "creature" or x.tapped: continue
                keywords = c.traits.split(";")[-1].split(",")
                if "defender" in keywords or x.fresh and "haste" not in keywords: continue
                responses = [self.damage(c, None)]
                for b in self.players[1-seat].battlefield:
                    if b.card.kind == "creature" and not b.tapped:
                        d = self.damage(c, b.card)
                        if d["legal"]: responses.append(d)
                minimum = min(max(0, d["damage"]-d["gainB"]) for d in responses)
                lethal = all(self.players[1-seat].life + d["gainB"] - d["damage"] <= 0 for d in responses)
                actions.append(Candidate(c.id, "attack", c.id,
                    features(power=c.power / 10, damage=minimum, lethal=int(lethal),
                             survive=int(not any(d["attackerDies"] for d in responses))),
                    "Attack with " + c.name))
        elif self.phase == "block":
            a = next(x.card for x in self.players[self.active].battlefield if x.card.id == self.pending)
            responses = [(None, self.damage(a, None))]
            for b in p.battlefield:
                if b.card.kind == "creature" and not b.tapped:
                    d = self.damage(a, b.card)
                    if d["legal"]: responses.append((b.card, d))
            for c, d in responses:
                lethal = p.life + d["gainB"] - d["damage"] <= 0
                actions.append(Candidate(c.id if c else "take", "block", c.id if c else "",
                    features(lethal=-int(lethal), damage=d["gainB"]-d["damage"],
                             power=(a.power if d["attackerDies"] else 0) - (c.power if c and d["blockerDies"] else 0),
                             survive=int(not d["blockerDies"])), "Block with " + c.name if c else "Take damage"))
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
                               "action": choice.kind, "features": list(choice.features)})
        return choice

    def step(self) -> bool:
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
            self.land_played = False
            self.phase = "untap"
            p = self.players[self.active]
            for x in p.battlefield:
                x.tapped, x.fresh = False, False
            self.log("untap", f"Player {self.active + 1} starts turn {self.turn} and untaps.")
        elif self.phase == "untap":
            self.phase = "draw"
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
            else:
                card = next(c for c in p.hand if c.id == choice.card_id)
                if choice.kind == "land":
                    p.hand.remove(card)
                    p.battlefield.append(Permanent(card, card.enters_tapped))
                    self.land_played = True
                    self.phase = "main"
                    self.log("land", f"Player {self.active + 1} plays {card.name}.", card=card.name)
                else:
                    payment = self.payment(card)
                    if not payment["paid"]: raise RuntimeError("Mana changed before action")
                    for x in p.battlefield:
                        if x.card.id in payment["sources"]: x.tapped = True
                    p.hand.remove(card)
                    if card.kind == "creature":
                        p.battlefield.append(Permanent(card))
                    else:
                        p.graveyard.append(card)
                    self.log("cast", f"Player {self.active + 1} casts {card.name}.",
                             card=card.name, manaSources=payment["sources"])
                    if card.kind == "spell":
                        for _ in range(card.draw): self.draw(self.active)
                        p.life += card.life
                        self.log("resolve", f"{card.name} resolves.", lifeGain=card.life, drawn=card.draw)
                        self.outcome()
        elif self.phase == "attack":
            choice = self.decide(self.active)
            if choice.kind == "pass":
                self.phase = "second_main"
                self.log("pass", "No attack.")
            else:
                self.pending = choice.card_id
                x = next(x for x in p.battlefield if x.card.id == self.pending)
                if "vigilance" not in x.card.traits.split(";")[-1].split(","): x.tapped = True
                self.phase = "block"
                self.log("attack", f"Player {self.active + 1} attacks with {x.card.name}.",
                         attacker=x.card.id)
        elif self.phase == "block":
            defender = self.players[1-self.active]
            choice = self.decide(1-self.active)
            a = next(x for x in p.battlefield if x.card.id == self.pending)
            b = next((x for x in defender.battlefield if x.card.id == choice.card_id), None)
            d = self.damage(a.card, b.card if b else None)
            self.log("block", choice.label, actor=1-self.active,
                     blocker=b.card.id if b else None)
            p.life += d["gainA"]
            defender.life += d["gainB"] - d["damage"]
            if d["attackerDies"]:
                p.battlefield.remove(a);p.graveyard.append(a.card)
            if b and d["blockerDies"]:
                defender.battlefield.remove(b);defender.graveyard.append(b.card)
            self.log("combat", "Combat damage resolves.", **d)
            self.pending = None
            self.outcome()
            if not self.finished: self.phase = "second_main"
        elif self.phase == "cleanup":
            # Deterministic discard is a declared sandbox rule, not a learned policy.
            while len(p.hand) > 7:
                c = p.hand.pop()
                p.graveyard.append(c)
                self.log("discard", f"Player {self.active+1} discards {c.name}.", card=c.name)
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
                "winner": self.winner, "learningEligible": self.result in ("win", "draw") and not self.questions,
                "productionEligible": False, "policyVersions": [p.version for p in self.policies],
                "events": self.events, "questions": self.questions}


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
        if saved["seed"] != seed or saved["evaluationSeedsPerGeneration"] != games:
            raise ValueError("Resume with the original seed/evaluation settings, or choose a new output directory.")
        champion = Policy.from_json(saved["champion"])
        history = saved["history"]
    else:
        champion = Policy.from_json(json.loads(checkpoint.read_text())) if checkpoint.exists() else Policy()
        history = json.loads(journal_path.read_text()) if journal_path.exists() else []
    def save_training():
        # One authoritative atomic generation commit; other files are readable exports.
        write_json(state_path, {"schemaVersion":1,"seed":seed,"evaluationSeedsPerGeneration":games,
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
            field = [[reference(c),int(c["tapped"]),int(c["fresh"])] for c in p["battlefield"]]
            grave = [reference(c) for c in p["graveyard"]]
            players.append([p["life"],p["handCount"],p["libraryCount"],field,grave])
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
    learning = sub.add_parser("train", help="Persistent evolutionary learning in the sandbox only")
    learning.add_argument("--demo", action="store_true", required=True)
    learning.add_argument("--generations", type=int, default=3)
    learning.add_argument("--seed", type=int, default=42)
    learning.add_argument("--evaluation-seeds", type=int, default=8)
    learning.add_argument("--out", type=Path, default=HERE/"runs/demo")
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
        elif args.command == "simulate":
            report = Simulator(rules, args.seed, args.starter, max_turns=args.max_turns).run()
            export_review(args.out, report)
            print(json.dumps({k: report[k] for k in ("result", "winner", "turns", "learningEligible")}))
        else:
            report = train(rules, args.out, args.generations, args.seed, args.evaluation_seeds)
            print(json.dumps(report))


if __name__ == "__main__":
    main()
