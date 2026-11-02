# MTG Golem — Goblins and Elves completion, second four-cycle pass (2026-11-02)

Scope: standalone diagnostic Oracle parser on `experiment/commander-ai-golem`.
No Minecraft changes and no promotion of diagnostic matches into training.

## Unchanged seven-deck baseline and per-cycle audit

All seven saved 100-card deck snapshots were checked with both
`diagnostic_coverage.py` and `question_batches.py` at baseline and after each
independent implementation-plus-test cycle. Counts are **card slots**, not
proof of complete legal Commander gameplay.

| Cycle | Full executable Oracle composition | New saved card | Supported slots | Unique unresolved names |
|---|---|---|---:|---:|
| Baseline | Previously published four-cycle pass | — | **584/700** | 113 |
| 1 | Multikicker paid on casting; +1/+1 counters applied **as entry replacements**; continuous subtype anthem dynamically scales with live source counters | Joraga Warcaller (Elves) | **585/700** | 112 |
| 2 | Equipped-creature player-hit ability chooses any target as the trigger enters the stack, deals typed-source damage, then draws; an invalid single target fizzles the **entire** trigger | Sword of Fire and Ice (Mono-Red) | **586/700** | 111 |
| 3 | Two independent mana-paid creature abilities: target another subtype creature for regeneration, and pump/grant a keyword to all controlled subtype creatures until end of turn | Ezuri, Renegade Leader (Elves) | **587/700** | 110 |
| 4 | Kindred Sorcery has two distinct legal uses: cast for typed creature tokens, **or** pay mana and discard the card from hand to reinforce a selected creature on the stack | Hunting Triad (Elves) | **588/700** | 109 |

Current deck coverage: Lupitas elves **90/100** (10 unresolved), Mono Red
Gobs **85/100** (15 unresolved), Budget Deck 79/100, faeries 71/100, Getting
Wild with Enchantments 100/100, Garbo Gobbos 100/100, squirrels 63/100.
Diagnostic game data remains `learningEligible=false`.

## Semantic behavior and scope

- `multikicker_anthem.py` consumes all three non-reminder lines, with generic
  costs, quantities, and creature subtypes. The declared kicker count is paid
  during casting and carried by the spell stack object. The entry event
  applies its counters before enter triggers, with pre-existing counter
  replacement effects eligible. Source counters scale the other-creature
  static effect live; removing the source removes that bonus. Diagnostic
  action enumeration offers zero and a few affordable positive kick counts;
  explicit casting accepts other payable counts.
- `equipment_composition.py` now includes targeted damage and card draw as
  closed, ordered equipped-player-hit atoms. The target is selected when the
  ability queues. Both legality and the original permanent incarnation are
  checked on resolution. A fizzle suppresses the subsequent draw; otherwise
  damage uses the Equipment's own source type/color even if the source left.
  A permanent target can cause ward before the underlying trigger resolves.
- `paid_regeneration_pump.py` composes two complete paid abilities. The first
  does **not** tap its source or require haste, unlike an older tap-regenerate
  ability. It creates a shield on a legal other target that survives source
  removal. The other uses the existing paid subtype team pump and applies
  temporary power, toughness and keyword changes at stack resolution.
- `reinforce_spells.py` distinguishes Sorcery/Kindred Sorcery from an in-hand
  activated ability. Casting creates tokens through the established token
  spell engine. Reinforce pays mana, discards from hand to graveyard **as a
  cost**, selects one legal target, supports ward, and places counters only on
  resolution after rechecking target legality and zone incarnation. Neither
  route silently drops the alternate rules text.
- Each new grammar is name-independent, amount/subtype-parameterized, and
  rejects unknown additional Oracle instructions. The current simulator is
  two-player and uses deterministic diagnostic choices; it is not a full
  multiplayer Commander rules certification.

## Verification

- `python3 -m unittest discover -s training/tests -p test_deck_completion_cycles.py -v`:
  **17/17 passed** (nine new test methods this pass). Cases include real
  saved cards, invented names, changed amounts and subtypes, actual mana and
  discard payments, priority/target timing, source removal, illegal-target
  fizzles, controller and opposing scope, Hardened Scales replacing Joraga's
  entry counters, a regeneration shield replacing destruction, dynamic
  counters, and strict unknown remainder rejection.
- Both seven-deck diagnostic audit and generated question inventory:
  **successful after every cycle**, with deltas above and no lost support.
- Full regression, `python3 -m unittest discover -s training/tests -q`:
  first run **1,315 tests in 589.611 seconds; seven failures, one skip**.
  An additional failure beyond the previous six was reported but not captured
  by name. The **second full run**, with its output preserved, completed
  **1,315 tests in 610.525 seconds; six failures, one skip**. These are
  exactly the same six pre-existing failures as the published checkpoint:
  five in `test_planeswalker_damage.py` and one in
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions`.
  Each of those modules was independently rerun with its known failure count.
  The earlier extra failure was **transient and not reproduced**; it is not
  claimed to be understood or fixed. All 17 focused completion tests and
  multiple affected Oracle/priority/counter/equipment suites passed independently.

## Unresolved teaching-deck queue

- **Mono-Red (15):** Squee, Dubious Monarch; Infantry Shield; Fortune Thief;
  Howlsquad Heavy; Sword of Hearth and Home; Sword of Hours; Sword of Truth
  and Justice; Excalibur, Sword of Eden; Sword of the Squeak; Valduk, Keeper
  of the Flame; Mister Gutsy; Raubahn, Bull of Ala Mhigo; Armory Automaton;
  Rhuk, Hexgold Nabber; Dissection Tools.
- **Elves (10):** Kenrith's Transformation; Mosswort Bridge; The Great
  Henge; Gala Greeters; Growing Rites of Itlimoc // Itlimoc, Cradle of the
  Sun; Galadhrim Brigade; Bow of Nylea; Umbral Mantle; Genesis Wave; Sword
  of Once and Future.
- Suggested next mechanics: **Galadhrim Brigade** (Squad copies and a live
  Elf anthem), **Excalibur, Sword of Eden** (historic-cost discount and
  legendary-only equip), or **Sword of Truth and Justice** (counter target
  choice and full proliferate counter types). Keep each unresolved until its
  entire executable Oracle program and tests are complete.
