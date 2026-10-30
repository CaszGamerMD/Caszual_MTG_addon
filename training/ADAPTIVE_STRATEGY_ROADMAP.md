# Adaptive Commander AI — strategy understanding roadmap

**Status:** first experimental deck-derived strategy heuristic on branch
`experiment/commander-ai-golem`. This remains a limited, two-player diagnostic
game, **not** rules-complete Commander or a trained general-purpose Magic player.
Keep all work in the standalone simulator until explicitly approved for Minecraft.

## Goal

Give **every deck the same strategy engine**, which:
1. Reads its own commander and complete printed decklist *before shuffling*.
2. Identifies plausible win conditions, engines, supporting themes, mana curve,
   and risks based on **mechanics**, not a list of hard-coded deck or card names.
3. Chooses a **primary** and **secondary** synergistic plan; can adapt its
   current tactical mode as its draws, board, life total, opponent's visible
   board and available legal moves change.
4. Evaluates *only* engine-supplied legal actions; never reads a shuffled
   library order, the opponent's hand or decklist, or future outcomes.
5. Eventually tests rival plans against the same seeds and opponents, learns
   from legitimate wins and losses, and keeps a versioned championship policy.
   **This step has not yet been built.**

## Initial implementation (v4, extended in v5)

`deck_adaptive_strategy.py` derives a `DeckPlan` from types, creature subtypes,
commander rules text, deck quantities, and keyword patterns in Oracle text.
The profile can detect tribal swarms, tokens, enchantment value, lifegain,
spellcasting synergy, artifact value, graveyard value and generic midrange.
For example, it currently infers:

- **Garbo Gobbos:** Goblin tribal swarm, supported by tokens.
- **Getting Wild:** Enchantment value, supported by lifegain.

The *same* `AdaptiveDeckPolicy` and base action feature weights apply to both
decks. Game context changes tactical mode on each decision:
- **develop:** land drops, cheap development, resource engines.
- **pressure:** push meaningful damage without hopeless attacks.
- **finish:** prioritize reachable lethal, not just raw board power.
- **stabilize:** protect against imminent lethal, removal/trades over greed.
- **rebuild:** restore a board after losing creatures.

Action grading changes with the inferred deck and current mode. Combat damage
remains a heuristic estimate rather than a proven adversarial combat search.

Run tests:
```bash
python -m unittest discover -s training/tests -p test_deck_adaptive_strategy.py -v
```

The matched diagnostic:
```bash
python training/seven_game_deck_adaptive.py --games 7 --turns 15 \
  --seed 5189995 --out training/reports/garbo-wilds-7x15-deck-adaptive
```
stores the inferred plan for each deck, seven outcomes and spectator replays.
Compare to `garbo-wilds-7x15-shared-ai` on identical seeds/seats.

## Compositional strategy v5 — shared goal, different path

Implemented in `strategy_building_blocks.py` and integrated into
`deck_adaptive_strategy.py`:

1. Parse the cards in the player's **own decklist** into reusable mechanic
   building blocks, with typed `produces`, `needs` and `blocks` fields.
   Examples: creature supply, token supply, mana engine, card engine, board
   amplifier, attack trigger, direct damage, recursion and life gain.
2. Link producer cards to consumer cards using the shared resource they
   produce and require, e.g. `creature_entry` or `creature_board`.
3. Compose possible routes such as mana -> creatures -> cards -> buffs ->
   combat damage or tokens -> buffs -> combat damage. The destination may
   be identical even when the setup sequence is different.
4. Use those card roles when evaluating **already legal** actions in the
   tactical policy. A board buff becomes more valuable when creatures are
   available; a token producer is more important when rebuilding.
5. Export `strategyRoutes`, `strategyDependencies` and the per-game
   inferred plans in the diagnostic output.

There is **no fixed Goblin/Elf/specific-card script** in this new layer.
It includes a synthetic unseen-deck test where token-generating Goblins
and mana-generating Elves pursue the same combat objective through distinct
building blocks, as well as a new creature-subtype parser test.

**Important limitation:** this parser currently extracts *candidate*
mechanics from Oracle text with rules-text patterns. It does not itself
verify triggers, targets, timings, cost payments or create legal actions.
The simulator's rule compiler and action validator remain authoritative.
Some printed abilities may be misclassified or missed. Work still needed:
derive each block from compiled rule programs, distinguish generated
resources from replacement/conditional effects, validate trigger conditions,
and search actual legal multi-action sequences. A path is not a proven combo.

Next accuracy milestone: feed the same algorithm two real decks with a shared
win idea but different enablers, e.g. the user's Goblin and Elf lists. Test
plan extraction against their printed card mechanics and then evaluate play
on matched seeds. Avoid deck-ID-specific teaching and use failures to improve
the general rule-to-strategy translator.

## Next milestones (NOT yet implemented)

- **Explainable turn-by-turn reasoning:** log the current tactical mode and
  the top legal alternatives on each decision, with no private future info.
  Track plan switches, threats, cards in hand, and goals accomplished.
- **Real win-condition analysis:** detect enabler/payoff dependencies from
  compiled rules programs, Commander-damage routes, life-gain win conditions,
  combos, counterspells and sweepers; score when a planned line is *actually
  available* rather than assuming it will be drawn.
- **Mana-aware action sequencing:** prioritize profitable combinations of
  legal plays on the same turn. Prevent passing with playable mana and avoid
  premature spells that disable a better line.
- **Opponent adaptation:** model known public threats, board wipes and
  removal, adjust aggression and resource commitments without access to the
  opponent's hidden resources.
- **Matched-seed strategy search:** compare candidate plan weights for each
  archetype over many valid games against several decks, check for overfitting,
  penalize rules-blocked episodes, record ties, then validate on held-out seeds.
- **Rules gate:** do not promote diagnostic performance to a trained champion
  or integrate into Minecraft until the full rules/casting/combat support
  passes the project’s rules coverage and validity gates.

## Measurement

Use same physical decks, matching seed/seat schedule, win rate, turns to real
win (fewer is better only after win count), blocked/question rate, average life
margin, action distribution and ability to recover from a lost board.
A single 7-game result is directional, not convincing evidence of general skill.
