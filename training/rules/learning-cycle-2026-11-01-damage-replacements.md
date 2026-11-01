# Oracle language learning cycles — reusable damage replacement events (2026-11-01)

Target branch: `experiment/commander-ai-golem`. Starting GitHub HEAD:
`2f0936778c809b3ce75eff2edb05c27b3deecbfd`.

The same seven saved 100-card decks were audited before and after each cycle.
Figures are **diagnostic importer and simulator support**; they do not mean
full multiplayer Commander legality or learning-eligible AI games. All
unimplemented Oracle programs still fail closed (`learningEligible=false`).

| Cycle | Typed replacement operation | Saved deck witness | Supported card copies | Unique unresolved names |
| --- | --- | --- | --- | --- |
| 1 | Life-floor replacement: damage to a controlled player cannot reduce that player's life below one; life loss unaffected | Ali from Cairo | 561/700 → 562/700 | 136 → 135 |
| 2 | Double damage from a creature controlled by the replacement's owner to any permanent or player | Gratuitous Violence | 562/700 → 563/700 | 135 → 134 |
| 3 | Add one damage when a controlled red or artifact source would damage an opposing player or permanent | Mechanized Warfare | 563/700 → 564/700 | 134 → 133 |
| 4 | Double all damage to permanents or players from any source, with intrinsic Flash | Dictate of the Twin Gods | 564/700 → 565/700 | 133 → 132 |

## Shared execution and boundaries

- Whole Oracle clauses produce typed `DamageReplacement` programs: operation,
  source filter, target filter, parameterized amount and optional intrinsic keyword. None
  are selected by card name. Unknown additional sentences, altered target
  scopes and unsupported permanent types remain unsupported.
- Replacements are continuous effects from battlefield permanents. They do
  **not** create stack triggers, and cease to apply when the permanent leaves
  or phases out. Different damage sources, controllers, types, colors, and
  recipient kinds are checked for each event.
- The same `replaced_damage` operation is used by regular/first-strike
  combat, grouped simultaneous combat, targeted damage abilities, modal
  damage, board-wide damage and direct player damage. The final amount feeds
  life totals, lethal marked damage, planeswalker loyalty, lifelink,
  commander damage and combat-damage trigger reports where relevant.
- Damage is distinguished from **loss of life** and payment of life. Damage
  floors are applied after other replacements to preserve the affected
  player's life as a deterministic legal ordering choice. Other replacements
  use a stable physical-ID order. The prototype does not yet offer every
  affected player's strategic ordering choice or handle arbitrary replacement
  dependency loops; it must not be presented as full legal Commander.
- The previous two-player diagnostics and gameplay limits remain in effect;
  no Minecraft mod rules were changed and no unsupervised strategy training
  has been authorized by these coverage increases.

## Evidence

- At least 20 focused tests passed across the four cycles, including each
  real deck witness; renamed source cards; controlled vs opposing sources;
  changed floor/bonus amounts, red, artifact and colorless sources; players and permanents; stack and
  grouped combat; lifelink; source departure; extra-text rejection; and
  ordering interactions between addition, doubling and life-floor effects.
- Mono Red Gobs improved **68 → 72/100**. The Elf, Faerie, Budget, Squirrel
  and two focal decks were unchanged. Garbo Gobbos and Getting Wild with
  Enchantments remained **100/100**.
- `training/diagnostic_coverage.py` and the saved-deck question-batch
  generator ran successfully against the same snapshots after each cycle.
- Full Python/Java-bridge regression: **1,239 tests in 844.734 seconds**,
  six failures and one skipped. All six are the same named failures and
  underlying symptoms as the published 1,220-test baseline: five in
  `test_planeswalker_damage.py`, plus the existing runtime-question assertion
  in `test_simulator.py`. No new regression failures appeared. The final
  two numerical-parameterization cases were also rerun afterward in the
  focused 20-test module (all passed). The separate Fabric Gradle build
  requires JDK 25 and was not run in this standalone Java-bridge test.

## Next candidate

Examine remaining 132 unique unresolved cards. Continue integrating damage
replacement and prevention variants only when all applicable damage paths
are executable; good next specimens include Sulfuric Vapors, Sulfuric Vortex,
and red or creature conditional effects. Prioritize complete typed rules,
not substring-based promotions or card-name exceptions.
