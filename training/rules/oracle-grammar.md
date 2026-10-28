# Oracle cause-and-effect parsing

`oracle_abilities.py` compiles supported Oracle paragraphs into immutable
`Trigger(event, subject, effect)` and `StaticEffect(subject, power, toughness,
count, condition)` nodes. Names are used for display and exact self-reference
normalization, never to select these behaviors.

“Whenever another Goblin you control enters, each opponent loses 3 life” becomes
an entry event, a same-controller/other-object/Goblin filter, and a lose-life
operation with amount 3. Different names, tribes and amounts use the same code.

## Supported grammar

- Entry and death events; self, other, creature, subtype and controller filters.
- Distinct damage and life-loss operations; optional controller life gain.
- Self-entry scry, with arbitrary positive amounts.
- Continuous numeric bonuses to other matching subtypes you control, bonuses
  counting matching permanents on either battlefield, and bonuses conditional
  on another creature of a specified color you control.
- Multiple supported abilities and keywords on the same card.
- Whole-text rejection when a paragraph, optional clause, intervening condition,
  unsupported effect or “one or more” trigger cannot be fully interpreted.

Obyra, Faerie Seer, Blood Artist, Zulaport Cutthroat, Impact Tremors, Briarberry
Cohort, Squirrel Mob and Squirrel Sovereign now execute through these nodes.
They are regression fixtures, not name-based dispatch cases. Review questions
show parsed ability structures alongside the original Oracle text.

## Remaining migration and limitations

Token creation, upkeep, Kolodin, Zurgo, equipment and saddle attack effects still
use legacy specialized handlers. Activated costs and arbitrary choices need
further nodes and execution support. This is a strict growing grammar, not a
complete natural-language or Magic rules engine.

Scry still keeps viewed cards in order; target-player drain chooses the opponent.
The diagnostic has no complete priority/response stack or multiplayer engine.
Unsupported first-strike/death timing pauses for a retained question. Real-deck
results remain excluded from policy training and live golem deployment.

## Verification

81 tests pass, including unfamiliar names, altered tribes/colors/amounts,
controller and type boundaries, continuous bonuses disappearing when their
conditions end, and unhandled-text rejection. Six distinct real-deck pairings
(seeds 142–147) each completed ten turns per player: 61 land plays, 20 casts and
22 trigger log entries, preserving the previous baseline. Results are in
`examples/oracle-grammar-pool-summary.json`.

## Generic standalone token instructions

Fixed-quantity sorcery instructions now compile through `parse_token_creation`
into a TokenSpec: amount, power/toughness, colors, subtypes, supported keywords
and tapped state. The simulator executes those characteristics, replacing the
former red-1/1-Goblin-only spell path. Unknown names use the same parser. Token
creation finishes its batch before entry triggers resolve. Creature tokens retain
colors/subtypes and enter fresh; tapped tokens remain tapped.

This does not yet migrate the legacy upkeep, death or self-entry token handlers.
Instant timing, X amounts, variable P/T, 0-toughness token state-based actions,
replacement effects, ward and additional instructions remain rejected or flagged.
There is no automatic flashback support. Complete-text parsing prevents a simple
creation instruction from hiding unimplemented additional abilities.

89 regression tests pass, including an unfamiliar spell creating tapped 2/3
blue-black Faerie Rogues with flying. A six-pairing real-deck batch (seed 342) is
recorded in examples/token-grammar-342.json. Five completed ten turns each; one
ended earlier under diagnostic rules. No strategic-learning claim is made.

## Entry-triggered token creation

Self-entry triggers now compose with the same TokenSpec used by standalone
spells. Goblin Instigator's name-specific handler was removed. The event kernel
queues the ability without creating tokens; resolution creates the entire batch
under the trigger controller before resolving the tokens' entry triggers. Parsed
amount, stats, colors, types, keywords and tapped state are preserved. Structured
review data serializes the token descriptor alongside trigger and subject nodes.

90 checks pass, including an unfamiliar summoner creating two tapped 3/4 blue
Drakes with flying for the nonactive player. Repeating token-entry engines and
generic death-token creation remain rejected pending proper stack/loop handling;
upkeep and last-known-power token handlers still require migration. The six
seed-442 pairings are recorded in examples/entry-token-442.json. This is continued
rules implementation, not learned strategy or complete Commander support.

## Generic upkeep triggers

The parser now recognizes “At the beginning of your upkeep” and composes it with supported effects (fixed token creation, scry, counters, opponent damage/life loss). It also recognizes mandatory “you lose N life and create …” as a single resolving effect with parsed life loss and token characteristics. Only the active controller's permanents trigger; token entry triggers resolve after the parent ability finishes and after checking game loss.

Bitterblossom and Bitterbloom Bearer now use this grammar; their name-specific parsing, upkeep generation, and importer exceptions were removed. Unknown names, token sizes, counts, colors, subtypes, and keywords use the same execution path. Conditions, optional payments, each-player upkeep, and unknown trailing instructions still reject the entire program. This remains a two-player diagnostic without a full response stack.

Validation: 92 tests pass, including unfamiliar upkeep text, opponent-turn exclusion, repeated upkeeps, and existing lethal-life-loss/token-entry timing tests. Seeds 542–547 ran all six distinct deck pairings: four reached ten turns per player; two ended earlier with a winner. Summary: `training/examples/upkeep-542.json`. These runs are not eligible for policy training.

Rules reference: Wizards’ Double Masters 2022 release notes, Bitterblossom: mandatory life loss is not a payment; token creation still occurs. https://media.wizards.com/2022/downloads/2X2_Release_Notes/EN_MTG2X2_Release%20Notes_20220418.pdf
