# Oracle learning cycles — toxic, equipment-granted abilities and goaded Auras

Target branch: `experiment/commander-ai-golem` (standalone two-player Commander
diagnostic, not Minecraft). Starting published HEAD:
`75d9a617727f5ae26ed3efe88259312bb5e92a6c`.

The same **seven 100-card saved decks** were audited after each cycle, and
question batches refreshed each time. All counts are diagnostic
importer/simulator support; `learningEligible=false` remains mandatory.

| Cycle | Complete reusable Oracle program | Saved-deck witness | Supported copies | Unique unresolved names | Focused tests |
| --- | --- | --- | --- | --- | --- |
| 1 | Numeric toxic on positive combat damage to a player, with poison totals and loss condition | Branchblight Stalker | 571 → 572/700 | 126 → 125 | 5/5 `test_toxic_programs.py` |
| 2 | Equipment grants a paid tap-to-any-target damage ability plus untap on any creature death; optional subtype entry autoattachment | Thornbite Staff | 572 → 573/700 | 125 → 124 | 5/5 `test_granted_equipment_abilities.py` |
| 3 | Enchant creature + goad + doubled enchanted creature **combat** damage + paid self-return from graveyard | The Sound of Drums | 573 → 574/700 | 124 → 123 | 5/5 `test_goad_damage_aura.py` |

## Execution details and boundaries

- All three programs compile complete, normalized Oracle wording through
  typed operations. The real cards and unfamiliar card names are equivalent;
  changed positive numeric amounts, subtype choices and costs are exercised.
  Unknown additional clauses, missing costs and wrong permanent types are
  rejected rather than running only the understood subset.
- Toxic does **not** convert damage or scale with its damage amount. Once a
  toxic creature actually deals positive combat damage to a player, that
  player gets the fixed number of poison counters. It is applied in grouped
  simultaneous combat, the legacy strike pipeline and the legacy fast combat
  path; blocked and prevented damage do not inflict poison. At ten poison
  counters, that player loses. Poison totals are included in public state.
- Equipment-granted abilities belong to the equipped creature. Mana and
  tap costs are paid by that creature's controller; the activated damage
  uses the common any-target stack resolver, with target legality checks.
  Each creature death independently queues the attached creature's untap
  trigger, which survives the Equipment leaving before resolution. Matching
  creature entries may move the Equipment to the entering creature, even if
  it belongs to the opponent; the diagnostic accepts the optional offer.
- Goad applies to the enchanted creature while the Aura is attached; in a
  **two-player** game it makes that creature attack if able. Only **combat**
  damage from that creature doubles; noncombat damage and other creatures
  are unaffected. This replacement shares the existing damage pipeline for
  player and permanent assignments. The Aura's graveyard ability pays mana
  and enters the normal priority stack, then moves the Aura from graveyard
  to hand on resolution if still there.
- This is not complete multiplayer goad target selection, nor an exhaustive
  dynamic rule-layer dependency model. Deterministic optional choices and
  the existing two-player priority limitations remain explicit.

## Evidence and next work

- Fifteen newly added focused tests passed, five per family, with per-cycle
  audits of all seven saved decks and question-batch regeneration.
- Mono Red Gobs improved **77 → 79/100**, Lupitas Elves **82 → 83/100**;
  the other five saved deck scores remained unchanged. Both focal decks
  remain at **100/100**; Squirrels stays at **63/100**.
- Full Python/Java-bridge regression: **1,282 tests in 520.171 seconds**;
  **six failures and one skipped**. The six match the prior published
  failure categories: five in `test_planeswalker_damage.py` and the known
  runtime-question assertion in `test_simulator.py`. No new failure
  category appeared. The separate Fabric Gradle build requiring JDK 25
  was not run for this standalone diagnostic.
- Remaining **123 distinct unresolved names** include attachment and Equipment
  variations, planeswalker and modal mechanics, and costs/zones beyond the
  current compiler. Next inspect reusable Equipment programs illustrated by
  **Quietus Spike** or **Infantry Shield**, and separately expand Squirrel
  deck coverage while preserving fail-closed incomplete rules.
