# Oracle language learning cycles — 2026-11-01

Branch: `experiment/commander-ai-golem`. Starting commit: `9dc62eb`.
Dataset: all seven committed `training/decks/*.json` snapshots (700 card
copies). All counts are **diagnostic executor coverage**, never proof of
Commander legality or eligibility for AI strategy training.

| Cycle | Shared grammar/operation added | New saved-deck card | Unique unresolved before → after |
| --- | --- | --- | --- |
| 1 | Typed target-permanent filter for **destroy + controller creates token** | Beast Within | 150 → 149 |
| 2 | Resolution-time **creature power/toughness thresholds** and independent ability-word labels in counted instructions | Shamanic Revelation | 149 → 148 |
| 3 | Resolution-time **Domain** operand (distinct basic land types) on temporary targeted P/T modifiers | Gaea's Might | 148 → 147 |

These are intentionally whole-text verified programs, not a list of
name-specific exceptions. Unrecognized extra clauses remain unsupported. All
three tests also compile unfamiliar spell names and parameter changes.

## Exact changes and remaining limits

1. `destroy_target_token` uses the same target binding, priority stack, ward,
   protection and resolution-time target recheck as other removal, for
   permanent, listed permanent types, or unions of artifact/creature. The
   controller of the targeted permanent receives the tokens even if the
   permanent survives because it is indestructible. If the target becomes
   illegal, the token instruction does not resolve.
2. `BattlefieldCount` now supports **power N or greater** and **toughness N
   or greater** filters for creatures, evaluated against effective stats when
   the instruction resolves. A printed ability-word label before a complete
   counted instruction contributes no rules effect. Unknown effects and
   unsupported cardinality/target syntax are still rejected.
3. `DomainCount` evaluates the five basic land subtypes across all lands a
   player controls, counting each subtype once, including those of nonbasic
   lands. The result multiplies the verified signed P/T modifier and expires
   at turn cleanup. It does not establish support for arbitrary characteristic
   expressions or continuous-effect dependency ordering.

## Audit

- Starting support: 547/700 copies; **150 distinct unsupported names**
  (153 unsupported card copies).
- After three cycles: 550/700 copies; **147 distinct unsupported names**
  (150 unsupported card copies).
- Garbo Gobbos and Getting Wild with Enchantments remain 100/100 each;
  Lupitas Elves advances 71/100 → 74/100.
- A fully parsed diagnostic card is not inherently full Commander-rules
  complete; the simulator still lacks general execution for many triggers,
  activation costs, choices, continuous layers and replacement effects.

## Verification

- Targeted destroy-and-create, counted-effect, composed modifier and existing
  Oracle-ability suites pass (13, 11, 13 and 70 tests respectively).
- Full Python regression: **1,166 tests, six failures, one skip**. The five
  `test_planeswalker_damage.py` failures and the single
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions` failure
  were independently reproduced on the untouched starting commit `9dc62eb`.
  They are inherited regressions, not new failures caused by these cycles.
- Java/Gradle tests remain unverified in this environment: only JDK 17 is
  installed while this mod targets Java 25.

### Next candidate families

Use the refreshed `question_batches.py` report and inspect *complete* Oracle
text before choosing. `Natural Order` exposes a composition gap between
additional sacrifice costs and already-supported library searches. Wider
shared gaps include activations, target choices, token replacement/creation
and equipment combat triggers. Carry all remaining cards as unsupported until
their complete programs have independent behavioral tests.
