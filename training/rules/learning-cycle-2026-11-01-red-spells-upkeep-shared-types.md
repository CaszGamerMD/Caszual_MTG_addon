# Oracle language learning cycles — red spell damage, upkeep prevention, shared-type mana

Target: `experiment/commander-ai-golem` (standalone two-player Commander
diagnostic). Starting published HEAD: `744b10d853546adda8ba8c9f5a03cf3e0b7ffb39`.
All seven saved 100-card decks were audited after **each** independent cycle,
including the question-batch generation. These are importer/runtime diagnostic
figures, **not** full Commander legality or AI-training eligibility.

| Cycle | Generalized Oracle grammar and runtime | Real-deck witness | Supported copies / 700 | Distinct unresolved names | Focused tests |
| --- | --- | --- | --- | --- | --- |
| 1 | Additional damage from red **spells** to any permanent or player; numeric `plus N`, spell-vs-permanent source checked at damage event | Sulfuric Vapors | 565 → 566 | 132 → 131 | 22 passing in `test_damage_replacement_programs.py` |
| 2 | All players' upkeep damage on stack plus continuous prevention of **all** life gain; prevention ends when source leaves | Sulfuric Vortex | 566 → 567 | 131 → 130 | 5 passing in `test_upkeep_damage_prevention.py` |
| 3 | Optional colorless mana from any creature entry, counting controller's creatures that share a subtype at **resolution**; includes changelings and self-entry | Mana Echoes | 567 → 568 | 130 → 129 | 5 passing in `test_shared_type_mana.py` |

## Semantics and bounds

- Whole-text grammar only. Source card **names are not used as dispatch keys**.
  Renamed source cards are positively tested; extra, unimplemented Oracle
  sentences and mismatched permanent types fail closed. Sulfuric Vapors also
  accepts an unfamiliar positive numeric damage bonus.
- Spell-only damage replacements compose with the prior common damage pipeline,
  including direct, ability, combat, grouped-combat and permanent assignments.
  A red creature permanent does not qualify as a red spell. The effects apply
  to either controller's qualifying spell.
- Upkeep damage is put on the normal triggered-ability stack from all active
  battlefield sources for each player. The target is the **active player**,
  not automatically the enchantment controller's opponent. A queued trigger
  survives source departure; its life-gain prevention does not. Damage is
  distinguishable from life loss and life gain, and produces the usual damaged
  player record. With a competing life-gain-to-life-loss replacement, this
  diagnostic chooses prevention first; a complete player-choice model remains
  future work.
- Shared-type mana counts on resolution and therefore sees intervening
  creature entries and exits. The entrant's last-known subtype information is
  retained if it leaves before the trigger resolves. An entering changeling
  shares types with all creature types, including itself. The diagnostic
  takes the optional nonnegative mana offer; strategic decline requires a
  richer decision policy. Mana is added to the colorless (`C`) pool, not
  arbitrary colored mana.
- These rules are additions to a limited two-player simulator, **not** a
  universal Oracle parser. The deterministic replacement ordering policy and
  incomplete Commander mechanics remain explicit limitations. Both 100%-covered
  focal decks remain so; the Squirrel deck still has 37 unresolved entries.

## Verification and next work

- Cycle 1: all 22 damage replacement tests passed; all seven decks and the
  question batch re-audited.
- Cycle 2: all five new upkeep/prevention tests passed; all seven decks and
  the question batch re-audited.
- Cycle 3: all five new creature-type mana tests passed; all seven decks and
  the question batch re-audited.
- Full Python/Java-bridge regression: **1,253 tests in 493.024 seconds**,
  **six failures and one skipped**. The failures are the same six already
  documented in the previous published learning-cycle report: five in
  `test_planeswalker_damage.py` and the runtime-question assertion in
  `test_simulator.py`. No new failure category appeared. The separate Fabric
  Gradle build (JDK 25 requirement) was not run in this standalone diagnostic.
- Current diagnostic `learningEligible=false`. Two decks remain 100/100;
  Mono Red Gobs improved from 72/100 to 75/100 during these three cycles.
- Next examine complete Oracle for the remaining Mono Red Gobs enchantment,
  attachment or upkeep families (e.g. **Braid of Fire**, **Hammer of Purphoros**,
  **Thornbite Staff**) and prioritize rules with executable event/state
  composition. Do not promote partial card rules.
