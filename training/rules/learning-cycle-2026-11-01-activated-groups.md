# Oracle language learning cycles — counted groups and activations (2026-11-01)

Branch: `experiment/commander-ai-golem`. Starting GitHub HEAD:
`76a21167b97def70fcb5c9857d8108d682341955`. Seven committed 100-card
Commander decks scanned with the same saved card text before and after each
independent grammar/runtime cycle.

The numbers here are **diagnostic card import and execution support**. They
do not prove full Commander legality, all choices, or safe strategy training;
`learningEligible` remains false. Unmatched sentences and missing mechanics
continue to reject the whole card.

| Cycle | Reusable rule operation | Real deck example | Unique unresolved names | Supported copies |
| --- | --- | --- | --- | --- |
| Baseline | — | — | 145 | 552/700 |
| 1 | Target-free group +X/+X and keyword grant; X bound from greatest live controlled power/toughness on resolution | Overwhelming Stampede | 145 → 144 | 552 → 553 |
| 2 | Mana-and-tap activated draw, conditional on a threshold of controlled same-name permanents; check before cost, then independent stack resolution | Endless Atlas | 144 → 143 | 553 → 554 |
| 3 | Tap-cost targeted +X/+X using live creature-type/controller/battlefield counts, target validation, and ward hooks | Timberwatch Elf | 143 → 142 | 554 → 555 |

The examples are **tests of generalized text rules, not name whitelists**.
Changed names, types, mana costs, keywords, counting scopes, and changing
board states are exercised. There are no name-based execution shortcuts.

## Timing, costs, and legality

- Group buffs lock the affected set and greatest power/toughness when the
  spell resolves, then expire at cleanup. Opposing creatures are excluded.
- Same-name activated draws validate the source, its controller, tap
  availability, source readiness if it is a creature, color/generic payment,
  and the required live same-name group *before* paying. The source is
  excluded from paying its own tap cost. The condition is not rechecked as
  the independent stack ability resolves.
- Counted targeted boosts require priority and a legal creature target
  before tapping. They recalculate X on resolution, including the opponent's
  qualifying creatures when Oracle says "on the battlefield" and creatures
  with changeling. An illegal or departed target causes no boost; a departed
  source does not cancel the already activated ability. Target-side ward
  events use the existing stack handling.
- Extra unknown sentences, unsupported costs, unrecognized conditions,
  illegal targets, and noncreature uses of these grammars remain unsupported.
  Generic subtype pluralization and the shared creature-subtype validity
  filter are deliberately bounded; this is not arbitrary English parsing.

## Measured outcome and verification

- Baseline: 552/700 supported, 145 distinct unresolved names.
- After cycle 1: 553/700, 144 unresolved.
- After cycle 2: 554/700, 143 unresolved.
- After cycle 3: **555/700, 142 unresolved**.
- Lupitas Elves improved 76/100 → 78/100. Mono Red Gobs improved
  64/100 → 65/100. The Garbo Gobbos and Getting Wild decks remain 100/100.
- Focused new tests: 4 group modifier, 5 conditional draw, 6 counted tap pump;
  all passed. Additional modifier regressions: 17 passed.
- Full Python regression: **1,194 tests**, six failures and one skipped in
  460.231 seconds. All six names and failure causes exactly match the prior
  published baseline: five `test_planeswalker_damage.py` failures and one
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions` failure.
  No new failures were observed. The Java Gradle mod build still needs JDK 25;
  the available JDK 17 is sufficient for the standalone Java rules bridge,
  not the Fabric mod build.

## Next candidates

The unresolved mono-red deck still has targeted Equipment and damage
replacement effects, and the Elf deck still has modal trigger choices,
counter/regen-cost programs, and complex enter-the-battlefield replacement
effects. Prefer a typed activated-ability/target/choice grammar with
independent legality validation, then attack-equipment trigger composition,
without treating diagnostic support as legal Commander play.
