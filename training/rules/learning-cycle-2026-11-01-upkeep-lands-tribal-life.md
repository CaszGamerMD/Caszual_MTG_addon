# Oracle language learning cycles — cumulative upkeep, land-sacrifice tokens, upkeep life

Published target branch: `experiment/commander-ai-golem` for the standalone
two-player Commander diagnostic (not Minecraft). Starting GitHub HEAD:
`1d723da29d2a07d294867ad5fa8d9027733500de`.

The same **seven saved 100-card decks** were audited after every independently
tested cycle, together with the persistent question batches. These figures
measure diagnostic parsing and executable rules only; they do **not** certify
full Commander legality or authorize training games.

| Cycle | Complete reusable Oracle family | Real-deck witness | Supported entries / 700 | Distinct unresolved names | Focused test result |
| --- | --- | --- | --- | --- | --- |
| 1 | Cumulative upkeep that repeats "Add {color}" per age counter on the controller's upkeep | Braid of Fire | 568 → 569 | 129 → 128 | 4/4 passed (`test_cumulative_upkeep_mana.py`) |
| 2 | Continuous static keyword grant plus mana, tap and land-sacrifice cost to create an artifact-enchantment-creature token | Hammer of Purphoros | 569 → 570 | 128 → 127 | 5/5 passed (`test_land_sacrifice_tokens.py`) |
| 3 | On every player's upkeep create typed creature tokens; when another controlled tribe member enters, gain life based on its current toughness | Wolverine Riders | 570 → 571 | 127 → 126 | 5/5 passed (`test_upkeep_token_entry_life.py`) |

## Reusable execution semantics

- All parsers match **complete normalized Oracle text**, not card names or
  a tempting substring. Renamed witnesses, changed mana symbols, costs,
  token powers/toughness, creature subtypes and unknown clauses were tested.
  The unimplemented remainder is never silently accepted.
- Cumulative upkeep triggers are queued during only the source controller's
  upkeep. When a source survives to resolution, an **age** counter is placed
  through the counter-replacement pipeline; the corresponding mana is added
  for every current age counter. The instruction "Add {R}" is beneficial and
  must not be misinterpreted as a mana *payment*. The trigger does nothing if
  its permanent has left by resolution. Age counters are separate from
  +1/+1, charge, and lore counters.
- The Hammer-style parser composes an existing, verified static-effect
  grammar with a new generic land-sacrifice activation. The controller must
  have priority, a ready untapped source, available mana and a land to
  sacrifice. Mana payment, source tapping and land sacrifice happen as
  costs; the token is created on stack resolution, and retains all three
  printed card types (Creature, Artifact, Enchantment). The haste effect
  applies only to the controller's creatures and expires with the source.
- The Wolverine-style parser composes existing token-spec parsing with new
  each-upkeep and tribal-entry listeners. The token trigger is controlled
  by its source's controller regardless of whose turn it is. A qualifying
  **other** creature entering under that controller creates an independent
  life-gain trigger. The amount uses current toughness on resolution or
  the entering creature's last-known toughness if it left. Standard life-gain
  replacement effects still apply. Tokens themselves produce the appropriate
  tribal entry triggers.
- The two previously completed focal decks remain **100/100**. Mono Red
  Gobs improved **75 → 77/100**; Lupitas Elves improved **81 → 82/100**.
  Squirrels remains **63/100**; `learningEligible=false`.

## Verification and remaining work

- Cycle 1: four focused tests passed, then all seven decks and question
  batches were re-audited.
- Cycle 2: five focused tests passed, then all seven decks and question
  batches were re-audited.
- Cycle 3: five focused tests passed, then all seven decks and question
  batches were re-audited.
- Full Python/Java-bridge regression: **1,267 tests in 518.518 seconds**,
  **six failures and one skipped**. Five failures remain in
  `test_planeswalker_damage.py`, plus the existing runtime-question assertion
  in `test_simulator.py`: these are the same six failure categories documented
  in the preceding published learning-cycle report. No new failure category
  appeared. A separate Fabric Gradle build requiring JDK 25 was not run in
  this standalone diagnostic.
- Existing priority/Commander limitations remain. This implementation does
  not claim universal coverage or strategic training readiness.
- Next inspect unresolved mono-red attachments such as **Thornbite Staff**
  and **The Sound of Drums**, or reusable toxic and poison-counter language
  illustrated by **Branchblight Stalker**; require complete semantics across
  combat, triggers, target choices and zone transitions before promoting them.
