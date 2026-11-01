# Oracle language learning cycles — Equipment, entry buffs, and ordered searches (2026-11-01)

Branch: `experiment/commander-ai-golem`. Starting GitHub commit:
`40bac3e520c15f13bee3325b945c7766a2a255b5`.

All numbers below are **diagnostic importer/runtime support** measured against
seven saved 100-card decks. They are not full Commander legality, general AI
understanding of every printed card, or learning eligibility. Unsupported
Oracle programs remain excluded from executable games and player training.

| Cycle | Whole-text reusable grammar and runtime operation | Real saved-deck witness | Supported card copies | Unique unresolved names |
| --- | --- | --- | --- | --- |
| 1 | `{T}` and optional mana: target controlled Equipment, target controlled creature; validate and pay costs, then attach only on stack resolution | Brass Squire | 555/700 → 556/700 | 142 → 141 |
| 2 | Creature enters: grant a team keyword and +X/+X until end of turn, binding X to a live creature/subtype count at resolution | Craterhoof Behemoth | 556/700 → 557/700 | 141 → 140 |
| 3 | Creature enters: search for any number of subtype cards, reveal, shuffle, and put selected cards on top in a chosen order | Goblin Recruiter | 557/700 → 558/700 | 140 → 139 |

## Semantics and limitations

- **Equipment attachment** is a two-target activated ability. The source's
  tap and mana requirements are paid only after both targets are legally
  chosen. A fresh creature source needs haste. Targets are checked again
  when resolving, including controller, protection and battlefield identity.
  The ability can resolve even if the source leaves. Equipment may legally
  be attached again to the same creature. No equipment is attached before
  the priority stack clears.
- **Entry team boosts** enter the stack as triggered abilities. When the
  ability resolves, a parameterized `BattlefieldCount` measures the current
  number of relevant creatures, then the current controlled creatures
  receive the granted keyword and +X/+X until end of turn. Source departure
  between entry and resolution does not cancel the trigger. The grammar
  recognizes an entire two-line ability, not a keyword in isolation.
- **Ordered entry searches** read a private library at resolution. The
  diagnostic chooses all qualifying subtype cards and places them on top
  in physical-ID order, a deterministic **legal choice policy** rather than
  optimal game strategy or arbitrary player choice. A zero-result search
  still shuffles. Cards stay conserved across the operation, and only
  selected names are revealed in public events.
- All families use parameters and unfamiliar test card names; none dispatch
  execution on a named card. Entire unsupported variants, unfamiliar extra
  sentences, missing mechanics, or wrong types fail closed. This is still a
  two-player diagnostic, not the complete multiplayer Commander engine.

## Verification and measured deck effects

- Every family has positive and negative tests with renamed cards, a real
  card witness, and target/cost/timing or order/zone checks. The new test
  modules contain 6 Equipment, 4 team-entry, and 4 library-entry tests,
  including target disappearance and end-of-turn cleanup.
- The deck audit after every cycle passed. Final affected decks: Mono Red
  Gobs **65/100 → 67/100**, Lupitas Elves **78/100 → 79/100**. Garbo Gobbos
  and Getting Wild with Enchantments remain **100/100**.
- `training/diagnostic_coverage.py` and the saved-deck question-batch
  generator were rerun against the same snapshots after all three cycles.
- Full regression suite: **1,207 tests** in **457.121 seconds**, six failures,
  one skipped. The failure names and root symptoms are unchanged from the
  immediately preceding 1,194-test baseline: five failures in
  `test_planeswalker_damage.py` and the runtime-question assertion in
  `test_simulator.py`. No new regression failure was observed. A sixth
  Equipment target-departure test added during the full run was also rerun
  and passed in the focused 6-test module; the next full run will collect it.
- Standalone Java rules bridge tests ran through the Python suite. The
  separate Fabric/Gradle build remains blocked on JDK 25 (JDK 17 installed).

## Next candidate

Inspect the remaining 139 unique unresolved names, particularly equipment
trigger chains in Mono Red Gobs and token/replacement interactions in other
decks. Evaluate each complete Oracle text; implement shared event/cost/zone
operations and compare unfamiliar names before declaring diagnostic support.
