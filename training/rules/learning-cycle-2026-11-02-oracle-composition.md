# Three Oracle composition cycles — 2026-11-02

Experiment: `experiment/commander-ai-golem` (standalone diagnostic simulator).
Source: the same seven saved 100-card Commander deck JSON snapshots under
`training/decks/`, plus independently renamed/parameterized Oracle test cases.
No card-name dispatch, and no change to `learningEligible=false`.

## Baseline and measured incremental coverage

Before: **574 / 700** individual saved deck cards importable, **123** unique
unresolved names. All seven decks were inventoried before changes. Each new
component independently accepts one previously unresolved saved card; the
other two new components are not needed to parse that card. Incremental
before/after below is the disjoint per-family contribution verified by the
new tests and final same-deck audit, not a simulated or estimated count.

| Cycle | Independently executed rule family | Saved deck impact | Cumulative supported | Unresolved unique names |
|---|---|---|---|---|
| 1 | Pay a parsed mana cost on a cast trigger before executing a fully parsed instruction; compose with live type anthem | Leaf-Crowned Visionary, Lupitas elves +1 | 575 / 700 | 122 |
| 2 | Equipped creature attack adds parameterized counters to the attacker at stack resolution; compose with equip and continuous bonuses | Bone Sabres, Lupitas elves +1 | 576 / 700 | 121 |
| 3 | Independent equip-creature-token activated cost plus ordinary equip cost and passive grants; enforce target kind at payment time | Team Pennant, faeries +1 | 577 / 700 | 120 |

Post-cycle audit: Lupitas elves **85/100**, Mono Red Gobs **79/100**,
Budget Deck **79/100**, faeries **71/100**, Getting Wild with Enchantments
**100/100**, Garbo Gobbos **100/100**, squirrels **63/100**. Seven deck snapshots
were refreshed by `training/diagnostic_coverage.py` and
`training/question_batches.py` using the exact same inputs as the baseline.

## Semantic blocks and rules behavior

1. `oracle_abilities.Effect.payment_cost` is an optional trigger-resolution
   payment gate, not part of spell casting. Its instruction must itself parse
   completely. The simulator checks a controller decision and legal mana
   payment at resolution; an unpaid trigger has no action and a paid draw
   cannot be declined again. Existing independent triggers and static effects
   compose unchanged.
2. `equipment_composition.equipped_attack_counters` parses an equipped-creature
   attack instruction and separately validates the remaining equipment's
   complete static/equip text. The attack snapshots the actual equipped
   attacker and its battlefield entry timestamp. The stack effect survives
   the Equipment leaving, respects live counter replacements, and does not
   affect a newly entered object with the same card ID.
3. `equipment_composition.token_equip_cost` validates the full equipment text
   with its token-only alternative removed, and then offers the alternative
   exclusively for token creatures. Ordinary equip still targets nontoken
   creatures at its own cost. Duplicate normal and token-specific equip
   instructions reject the whole card.

All three implementations fail closed on unmatched additional instructions.
Verified alternate costs, card names, subtype parameters, counter quantities,
and other independently executable grant combinations. The narrow new grammar
does not claim to cover unrestricted optional costs, arbitrary modal effects,
or other Equipment-trigger families.

## Validation and remaining limits

- `test_oracle_composition_cycles.py`: **7 focused tests passed**. These cover
  real card Oracle imports, renamed and altered-cost clauses, legal and
  unaffordable/declined payments, stack timing, removal of the trigger source,
  counter replacement effects, changed-zone source identity, target-kind
  restrictions, ordinary equip fallback, static grants, and strict unknown
  remainder rejection.
- Full suite: `python3 -m unittest discover -s training/tests -q`
  completed **1,289 tests** in **514.838 seconds**, with **6 failures and
  1 skipped**. These are the same six known pre-existing failures as the
  1,282-test baseline: five cases in `test_planeswalker_damage.py` and one
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions` mismatch.
  All **7 newly added tests passed**; no new full-suite failures were observed.
- Question batch audit remains diagnostic work prioritization, not legal game
  adjudication or model training. Neither the two-player simulator nor its
  imported-card ratio grants full Commander rules coverage.

Next candidate combinable families: `Wildborn Preserver` (optional X payment
and reflexive counter trigger; non-Human entry selector), `Bladegraft Aspirant`
(Equipment spell and activated-cost reductions), or `Quietus Spike` (equipped
combat-damage life reduction). Treat each as unsupported until its complete
Oracle behavior, timing and negative tests pass.
