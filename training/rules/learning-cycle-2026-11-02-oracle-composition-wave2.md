# MTG Golem — composable Oracle rules, second three-cycle wave (2026-11-02)

Branch: `experiment/commander-ai-golem`. Scope: standalone diagnostic
Commander simulator; no Minecraft mod edits or generated training examples.

## Actual saved-deck baseline and independent cycle deltas

All **seven unchanged 100-card decks** under `training/decks/*.json` were
re-imported and questioned at the start and after every independent cycle.
Every new card required the complete generalized grammar, an executable rules
path, and the targeted negative/zone/priority tests to pass before counting.

| Cycle | Executable new language combination | Newly recognized saved card | Recognized copies | Unresolved unique names |
|---|---|---|---|---|
| Baseline | Already published from previous session | — | 577/700 | 120 |
| 1 | Equipment's **equipped-creature combat damage to player** trigger + complete attached keyword/equip program; positive damage creates a stack event; life loss evaluated when resolved | Quietus Spike (Mono Red Gobs) | **578/700** | 119 |
| 2 | **Equipment spell discount** + separate **activated Equipment cost discount when target is this creature**, composed with intrinsic menace | Bladegraft Aspirant (Mono Red Gobs) | **579/700** | 118 |
| 3 | **Another non-[creature type] entry selector**, optionally **pay X**, then create a separate reflexive **“When you do”** counter trigger, composed with flash/reach | Wildborn Preserver (Lupitas elves) | **580/700** | 117 |

Final deck-specific diagnostic parse coverage: Lupitas elves **86/100**, Mono
Red Gobs **81/100**, Budget Deck **79/100**, faeries **71/100**, Getting Wild
with Enchantments **100/100**, Garbo Gobbos **100/100**, squirrels **63/100**.
Neither import coverage nor a seven-game diagnostic is a legal Commander
certification. `learningEligible` remains **false**.

## Semantic implementation and guardrails

- `equipment_composition.equipped_combat_life` consumes a whole isolated
  combat-to-player-damage clause and validates every remaining equipment
  instruction through the existing attachment parser. Supports an exact fixed
  life-loss amount and half the current life rounded up. The event snapshots
  the equipped attacking creature upon positive damage, and the resulting
  stack trigger survives detachment or source destruction. Prevented damage
  creates no trigger; separate first/double-strike hits generate separate
  triggers.
- `oracle_abilities.Program.equipment_target_ability_discount` composes with
  keywords and spell reductions without erasing either. `Simulator.payment`
  applies this discount only to the generic mana portion of activated
  Equipment abilities, only when the Equipment targets that actual creature.
  The cost-planning checks and payment use the same target-aware rule; ordinary
  targets still pay their printed equip cost. Equivalent target/costs share a
  cache within choice enumeration.
- `oracle_abilities.selector` supports variable `non-<creature subtype>` in
  other-controlled entry events, including changeling exclusion. The X-choice
  is made and mana spent when the initial ability resolves; a separate
  reflexive counter ability is then placed on the stack. A changed-zone
  permanent with the same ID does not receive those counters. The default
  diagnostic X decision examines affordable choices up to six; this is a
  declared limited **policy**, not a rules maximum.
- All new grammar uses whole-line matching, new-name and parameter tests, and
  complete-card rejection for unknown trailing text. No exact card names
  select behavior. Full `When you do` vs `If you do` timing is distinguished.

## Verification

- `python3 -m unittest discover -s training/tests -p test_oracle_composition_wave2.py -v`:
  **9/9 passed**. Real Oracle cards; renamed/changed values and subtype;
  dynamic current-life rounding; prevention; double strike; triggered source
  leaves; spell/activation payment separation; proper alternate and ordinary
  targets; non-Human and opposing entry filters; X payment; two stack events;
  declined payments; changed-zone source; strict unknown remainder.
- Per-cycle `diagnostic_coverage.py` and `question_batches.py`: succeeded
  against the same seven snapshots each time; exact deltas above.
- Full Python regression: `python3 -m unittest discover -s training/tests -q`
  completed **1,298 tests in 557.093 seconds**, with **six failures and one
  skip**. The failures are unchanged from the previous 1,289-test checkpoint:
  five cases in `test_planeswalker_damage.py` and
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions`.
  There were **no new failures**, and all nine new composition checks passed.

Next important families: `Nectar Faerie` (paid tap target keyword grants),
`Galadhrim Brigade` (Squad copies combined with a live Elf anthem), or the
multi-clause Sword of [X] and [Y] equipment damage triggers. None is promoted
on partial-language recognition.
