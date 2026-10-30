"""Reusable strategic mechanics extracted from printed rules, not deck identities.

The output is an *interpretation*, not an executor: Oracle text supplies clues
for candidate plans; the simulator's compiled rules and legal-action boundary
remain authoritative for what can actually happen in a game.

Card names are used only to associate printed facts with the player's own
drawn cards. No card/deck title or known tribal list selects a strategy.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

# Each piece of strategy is typed by *what it does*, not a preset archetype.
# A Goblin token maker and an Elf token maker have the same output "board".
# A mana-producing Elf reaches that output through a different dependency.
BUILDING_BLOCKS = (
    "mana_engine", "creature_supply", "token_supply", "card_engine",
    "board_amplifier", "attack_payoff", "damage_payoff", "life_engine",
    "recursion_engine", "removal", "board_reset",
)

@dataclass(frozen=True)
class CardBlocks:
    name: str
    produces: tuple[str, ...]
    needs: tuple[str, ...]
    blocks: tuple[str, ...]
    subtypes: tuple[str, ...] = ()
    quantity: int = 1


@dataclass(frozen=True)
class StrategyRoute:
    """A reusable purpose assembled from a chain of mechanic building blocks."""
    goal: str
    steps: tuple[str, ...]
    strengths: tuple[tuple[str, int], ...]
    score: float

    def describe(self):
        return dict(goal=self.goal, steps=list(self.steps),
                    strengths=dict(self.strengths), score=self.score)


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I | re.S) is not None


def parse_card_blocks(card: dict) -> CardBlocks:
    """Conservative finite set of effect roles for any printed card.

    Parsing only *suggests* what a card can contribute. A phrase is not a
    substitute for rules validation or legal action execution.
    """
    text = card.get("oracleText", "") or ""
    types = set(card.get("types", ()))
    subtypes = tuple(card.get("subTypes", ()))
    produces, needs, blocks = set(), set(), set()

    if "Land" in types:
        produces.add("mana")
    if "Creature" in types:
        produces.add("creature_board")
        produces.add("creature_entry")
        blocks.add("creature_supply")
        needs.add("mana")
    if "Enchantment" in types:
        produces.add("enchantment_board")
        needs.add("mana")
    if "Artifact" in types:
        produces.add("artifact_board")
        needs.add("mana")

    # Generic token grammar; no hard-coded Goblin/Elf/etc subtype list.
    token_creature = _matches(
        r"\bcreate\b[^.!?]{0,140}\bcreature tokens?\b|"
        r"\bcreate\b[^.!?]{0,140}\b[0-9]+/[0-9]+[^.!?]{0,60}\btokens?\b", text)
    if token_creature:
        produces.update(("creature_board", "creature_entry"))
        blocks.add("token_supply")
    if _matches(r"\bcreate\b.{0,110}\btreasure tokens?\b", text):
        produces.add("mana")
        blocks.add("mana_engine")
    if _matches(r"\bcreate\b.{0,100}\b(?:food|clue)\s+tokens?\b", text):
        produces.add("artifact_board")

    # Mana creatures, artifacts, and land-ramp spells feed the same resource.
    if _matches(r"(?:\{T\}|tap (?:this|target) [^.]{0,35})\s*:\s*add\b|"
                r"\{T\}:\s*Add\b|\badd \{[WUBRGC0-9X]+\}\b|"
                r"\bsearch your library for (?:a|up to \w+) basic land\b", text):
        produces.add("mana")
        blocks.add("mana_engine")

    if _matches(r"\bdraw (?:a|one|two|three|[0-9]+|\bX\b) cards?\b|"
                r"\bdraw cards? equal to\b", text):
        produces.add("cards")
        blocks.add("card_engine")
        if _matches(r"whenever [^.\n]{0,90}(?:creature|another creature)[^.\n]{0,100}\benters\b", text):
            needs.add("creature_entry")
        if _matches(r"whenever [^.\n]{0,100}\benchantment\b[^.\n]{0,65}\b(?:enters|cast)\b", text):
            needs.add("enchantment_board")
        if _matches(r"whenever [^.\n]{0,100}\b(?:attacks|combat damage)\b", text):
            needs.add("attack")

    if _matches(r"\b(?:creatures|[a-z]+(?: creatures)?) you control (?:get|have|gain)\b[^.\n]{0,75}"
                r"(?:\+[0-9]+/\+[0-9]+|double strike|trample|flying|menace)\b|"
                r"\bother [a-z]+(?: creatures)? (?:you control )?get \+[0-9]+/\+[0-9]+\b|"
                r"\bput (?:a|one|two|[0-9]+) \+1/\+1 counters? on (?:each|all) creature\b", text):
        needs.add("creature_board")
        produces.add("combat_power")
        blocks.add("board_amplifier")

    if _matches(r"\bwhen(?:ever)? [^.\n]{0,105}\battacks?\b|"
                r"\bwhenever [^.\n]{0,100}\bcombat damage\b", text):
        needs.add("attack")
        blocks.add("attack_payoff")

    if _matches(r"\b(?:deals?|deal) [0-9X]+ damage to (?:each opponent|"
                r"target opponent|any target|each player|target player)\b|"
                r"\b(?:opponents?|target player) lose[s]? [0-9X]+ life\b", text):
        produces.add("opponent_damage")
        blocks.add("damage_payoff")

    if _matches(r"\b(?:you )?gain (?:[0-9]+|X|that much) life\b|\blifelink\b", text):
        produces.add("life")
        blocks.add("life_engine")
    if _matches(r"\bwhenever (?:you gain life|you gain [0-9]+ life)\b", text):
        needs.add("life")
    if _matches(r"\breturn (?:target|a) [^.\n]{0,70}\bfrom your graveyard\b", text):
        produces.add("recovered_cards")
        needs.add("graveyard")
        blocks.add("recursion_engine")
    if _matches(r"\b(?:destroy|exile) target (?:creature|permanent|artifact|enchantment)\b", text):
        blocks.add("removal")
    if _matches(r"\bdestroy all creatures\b|\bexile all creatures\b", text):
        blocks.add("board_reset")
    return CardBlocks(card.get("name", ""), tuple(sorted(produces)),
                      tuple(sorted(needs)), tuple(sorted(blocks)), subtypes,
                      max(1, int(card.get("quantity", 1))))


def map_mechanics(deck: dict) -> tuple[CardBlocks, ...]:
    if not deck.get("mainboard") or not deck.get("commanders"):
        raise ValueError("Deck mechanics need a commander and mainboard")
    return tuple(parse_card_blocks(c) for c in
                 [*deck["mainboard"], *deck["commanders"]])


def compose_routes(cards: tuple[CardBlocks, ...]) -> tuple[StrategyRoute, ...]:
    """Compose end goals from supported dependencies; no tribal names required.

    Routes are potential paths, not guaranteed combos. Prefer coherent producer
    -> engine -> finisher chains. Commander is accessible, so double its weight.
    """
    if not cards:
        return ()
    total = Counter()
    for idx, card in enumerate(cards):
        count = card.quantity
        if idx == len(cards) - 1:  # standard single-commander deck
            count = max(count, 2)
        for block in card.blocks:
            total[block] += count
    supply = total["creature_supply"]
    tokens = total["token_supply"]
    mana = total["mana_engine"]
    draw = total["card_engine"]
    buffs = total["board_amplifier"]
    attacks = total["attack_payoff"]
    pings = total["damage_payoff"]
    life = total["life_engine"]
    recursion = total["recursion_engine"]
    routes = []
    if supply or tokens:
        path = []
        if mana >= 2:
            path.append("mana_engine")
        path.append("token_supply" if tokens >= 2 else "creature_supply")
        if draw >= 2:
            path.append("card_engine")
        if buffs:
            path.append("board_amplifier")
        if attacks:
            path.append("attack_payoff")
        path.append("combat_damage")
        contributions = dict(mana_engine=mana,creature_supply=supply,
                             token_supply=tokens,card_engine=draw,
                             board_amplifier=buffs,attack_payoff=attacks)
        routes.append(StrategyRoute(
            "combat_damage", tuple(path), tuple(sorted(contributions.items())),
            round(0.35*min(30,supply) + 0.8*min(12,tokens) +
                  0.7*min(10,buffs) + 0.4*min(8,attacks) +
                  0.25*min(10,mana) + 0.25*min(8,draw),3)))
    if pings >= 2:
        steps = tuple(step for step in ("creature_supply" if supply else "",
                  "token_supply" if tokens else "",
                  "damage_payoff") if step)
        routes.append(StrategyRoute("direct_damage", steps,
                tuple(sorted(dict(damage_payoff=pings,token_supply=tokens,
                                  creature_supply=supply).items())),
                round(pings*.9 + min(tokens,8)*.4,3)))
    if life >= 2:
        routes.append(StrategyRoute("survive_and_outvalue",
                tuple(x for x in ("life_engine","card_engine" if draw else "",
                                  "creature_supply" if supply else "") if x),
                tuple(sorted(dict(life_engine=life,card_engine=draw).items())),
                round(.35*life+.35*draw,3)))
    if recursion >= 2:
        routes.append(StrategyRoute("attrition",
                tuple(x for x in ("graveyard","recursion_engine",
                                  "creature_supply" if supply else "") if x),
                tuple(sorted(dict(recursion_engine=recursion).items())),
                round(recursion*.55+min(draw,8)*.3,3)))
    return tuple(sorted(routes, key=lambda route:(-route.score, route.goal)))


def plan_for_deck(deck: dict) -> dict:
    cards=map_mechanics(deck)
    routes=compose_routes(cards)
    return dict(routes=tuple(r.describe() for r in routes),
                cardBlocks=tuple((c.name,c.blocks) for c in cards),
                buildingBlockCounts=dict(Counter(
                    b for c in cards for b in c.blocks for _ in range(c.quantity))))
