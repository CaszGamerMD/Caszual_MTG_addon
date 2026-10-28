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

80 tests pass, including unfamiliar names, altered tribes/colors/amounts,
controller and type boundaries, continuous bonuses disappearing when their
conditions end, and unhandled-text rejection. Six distinct real-deck pairings
(seeds 142–147) each completed ten turns per player: 61 land plays, 20 casts and
22 trigger log entries, preserving the previous baseline. Results are in
`examples/oracle-grammar-pool-summary.json`.
