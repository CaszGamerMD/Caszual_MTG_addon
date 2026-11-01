# Oracle language learning cycles — self-attachment, tribal entry and uniqueness gates (2026-11-01)

Target GitHub branch: `experiment/commander-ai-golem`. Starting HEAD:
`94570e79c2fa9bde814a78811993a9bea5d56a8f`.

This is a continuation of the standalone two-player diagnostic parser. Seven
committed, unchanged, 100-card decks were audited at the start and after each
cycle. The numbers describe **diagnostic import and executable-rule support**,
not correct multiplayer Commander, exhaustive Oracle understanding, or data
eligible to train a player. `learningEligible` remains false.

| Cycle | Reusable Oracle operation | Real deck example | Supported copies | Unique unresolved card names |
| --- | --- | --- | --- | --- |
| 1 | Mana-only sorcery-speed targeted Equipment attachment to the source creature, composing with prior two-target tap attachment | Kazuul's Toll Collector | 558/700 → 559/700 | 139 → 138 |
| 2 | Another controlled subtype enters: one source gets parameterized +1/+1 counters on stack resolution | Decorated Champion | 559/700 → 560/700 | 138 → 137 |
| 3 | A nontoken controlled creature enters with no matching name among another controlled creature or any creature card in graveyard: draw a parameterized number of cards | Guardian Project | 560/700 → 561/700 | 137 → 136 |

## Mechanics and correctness boundaries

- **Source attachment:** A `{0}` or mana-cost activation without `{T}` does
  not tap its controller's creature and is not prevented by summoning
  sickness. It can be activated only in its controller's main phase with an
  empty stack and priority, like Equip. The Equipment target remains checked
  when the ability resolves, and the creature source is also the mandatory
  attachment destination. The former two-target `{T}` rule remains available
  and independently tested. Unknown activation timing text is rejected.
- **Tribal counters:** Each other controlled qualifying creature entering
  creates an independent stack trigger. Subtype and counter amount are typed
  parameters. The counter is applied using the existing replacement and
  state-based-actions machinery only if the source still survives when the
  trigger resolves. In the two-player simulator "your team" means only the
  controller; multiplayer teammates are not simulated.
- **Unique-entry draw:** A name/zone predicate is checked on trigger
  placement **and** stack resolution (an intervening-if). The entering
  creature is excluded from the "another" check, but if that creature later
  becomes a creature card in the controller's graveyard, the gate may fail.
  Tokens do not qualify as entrants, though existing controlled creature
  tokens do count toward duplicate-name checking. The trigger survives its
  enchantment source leaving; it draws only if the gate remains true.
- All parsers consume an entire known Oracle program. They do not dispatch
  by card name. Unrecognized words, extra clauses, wrong types or unsupported
  choices still fail closed rather than contributing incomplete game events.

## Verification

- Three added attachment tests plus the earlier six tests passed (9/9),
  covering the real Kazuul card, an unfamiliar name, changed mana cost,
  summoning sickness, timing, shroud and illegal target/cost combinations.
- Four new tribal-entry tests passed (4/4); five separate conditions include
  an unfamiliar source, changed subtype and amount, opponent control,
  source departure and rejected extra instructions.
- Six unique-entry tests passed (6/6): real Guardian Project, unfamiliar
  source, battlefield and graveyard duplicates, a duplicate added while the
  trigger waits, token suppression, source departure and varied draw amount.
- Lupitas Elves **79 → 81/100**; Mono Red Gobs **67 → 68/100**. The other
  five decks' diagnostic support is unchanged; Getting Wild and Garbo Gobbos
  remain **100/100**.
- `training/diagnostic_coverage.py` and `training/question_batches.py`
  reran successfully against all seven saved deck snapshots after each cycle.
- Full Python/Java-bridge regression: **1,220 tests in 499.131 seconds**;
  six failures, one skipped. All six failing tests and error causes match
  the published 1,207-test baseline: five failures in
  `test_planeswalker_damage.py` and one existing runtime-question assertion
  in `test_simulator.py`. No new failures were observed. The Java bridge
  compiled and ran; the separate Fabric Gradle build requires JDK 25 and
  is not verified by this standalone test run.

## Next candidate

Inspect the 136 remaining unique unresolved Oracle programs. Highest-priority
transferable families include damage-replacement effects in Mono Red Gobs,
mode-selection and token replacement in the Elf and Squirrel decks, and
combat/Equipment triggers across multiple decks. Maintain the no-name-dispatch
gate and test new grammars on unfamiliar texts before marking coverage.
