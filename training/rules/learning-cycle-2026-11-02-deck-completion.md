# MTG Golem — Mono-Red and Elves deck-completion pass (2026-11-02)

Branch: `experiment/commander-ai-golem`. All work is limited to the standalone
diagnostic simulator. No Minecraft changes and no training-data promotion.

## Four independent executable learning cycles

All seven saved, unchanged 100-card decks were inventoried at baseline and
re-audited using `diagnostic_coverage.py` and `question_batches.py` after
each successful implementation/test cycle. Counts below are *card copies*
whose complete Oracle text is parse-supported by the diagnostic engine.

| Cycle | New generalized instruction family | Newly recognized card | Seven-deck recognized copies | Remaining unique unsupported |
|---|---|---|---:|---:|
| Baseline | Previous committed state | — | 580/700 | 117 |
| 1 | Colored unspent mana retained between phases; live stats scale by that colored mana | Omnath, Locus of Mana (Elves) | 581/700 | 116 |
| 2 | Equipped-player-hit atomic sequence: create typed creature token **then** mill damaged player by a specified count; two independent protection colors | Sword of Body and Mind (Mono-Red) | 582/700 | 115 |
| 3 | Equipped-player-hit atomic sequence: damaged player discards specified number of cards **then** untap controller's lands | Sword of Feast and Famine (Mono-Red) | 583/700 | 114 |
| 4 | Equipped-player-hit atomic sequence: controller gains life **then** may return one creature card targeted in their graveyard when the trigger is queued | Sword of Light and Shadow (Mono-Red) | 584/700 | 113 |

Current saved-deck coverage: Mono Red Gobs **84/100** (16 unsupported),
Lupitas elves **87/100** (13 unsupported), Budget Deck 79/100, faeries
71/100, Getting Wild with Enchantments 100/100, Garbo Gobbos 100/100,
squirrels 63/100. The diagnostic remains `learningEligible=false` and is
not a legal Commander simulator.

## Rule behavior and safeguards

- Unspent-mana grammar consumes the *entire* two-line static program. Only the
  specified retained color survives a phase boundary, only for its
  controller while the source persists. The stat boost uses the current
  corresponding pool, including spending and controller isolation.
- The equipment parser consumes one complete, ordered, combat-hit ability and
  verifies all remaining text using the existing equipment attachment grammar.
  Unknown extra text never silently produces a partial supported card. The
  source Equipment must be attached when positive combat damage triggers,
  but need not remain attached or on the battlefield when the stack resolves.
- A triggered ability containing two operations occupies **one stack item**;
  steps execute sequentially when that item resolves. Token creation is
  followed by mill, discard is followed by land untap, and life gain is
  followed by an optional targeted creature-card return. Damage-player scope,
  controller scope, and targeting are separate.
- Multi-color protection keywords are normalized from Oracle's elided noun
  (e.g. `protection from green and from blue`) and still validated against the
  supported keyword vocabulary. The simulator does not dispatch on card names.
- The diagnostic currently uses a deterministic policy for selecting the
  damaged player's discard card and the optional graveyard creature target;
  a decision agent may replace the latter via the choice hook. The graveyard
  target is selected when the trigger queues, and is rechecked at resolution.
  Full multiplayer decisions, complex target-zone-change incarnation handling,
  and general Commander rules remain open.

## Verification

- `python3 -m unittest discover -s training/tests -p test_deck_completion_cycles.py -v`:
  **8/8 passed**, covering actual cards, unfamiliar names, changed colors/
  quantities, damaged player and controller separation, stack timing,
  removal of Equipment before resolution, optional target decline and
  disappearance, mana spending/phase boundaries, card conservation, and
  unsupported extra clauses.
- Each cycle's seven-deck coverage report and question-batch regeneration:
  **successful**, with the copy and unique-name deltas shown above.
- Full regression: `python3 -m unittest discover -s training/tests -q`:
  **1,306 tests in 563.720 seconds; six failures and one skip**. Those six
  failures are unchanged from the previous 1,298-test checkpoint: five in
  `test_planeswalker_damage.py` and one in
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions`.
  There were **no new failures**; the additional eight deck-completion
  tests all passed.

## Remaining queue

- Mono-Red 16: Squee, Dubious Monarch; Infantry Shield; Fortune Thief;
  Howlsquad Heavy; Sword of Hearth and Home; Sword of Hours; Sword of Fire
  and Ice; Sword of Truth and Justice; Excalibur, Sword of Eden; Sword of
  the Squeak; Valduk, Keeper of the Flame; Mister Gutsy; Raubahn, Bull of
  Ala Mhigo; Armory Automaton; Rhuk, Hexgold Nabber; Dissection Tools.
- Elves 13: Ezuri, Renegade Leader; Joraga Warcaller; Kenrith's
  Transformation; Mosswort Bridge; The Great Henge; Gala Greeters;
  Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun; Hunting Triad;
  Galadhrim Brigade; Bow of Nylea; Umbral Mantle; Genesis Wave; Sword of
  Once and Future.
- Exact next candidates: **Sword of Fire and Ice** (choose any target on
  trigger; damage then draw, including protection/ward) and **Joraga
  Warcaller** (multikicker payment, entry counter multiplicity, continuous
  Elf-only anthem). Neither is admitted with partially handled Oracle text.
