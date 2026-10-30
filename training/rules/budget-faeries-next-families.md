# Budget Deck + Faeries: shared-rule development queue

Branch: `experiment/commander-ai-golem`. Baseline: successful focused-coverage run 41101065074 at commit `b307bccc135aea2882cdd7f60b510d0ecaf14a6f`. Current inspected HEAD: `77a2a9d6c0b3438a1f48fd228c1f5835a287de35`.

The baseline diagnostic importer recognized 79/100 Budget Deck and 68/100 Faeries cards (21 and 32 unsupported card copies respectively). These are **not** full Commander legality or current-HEAD rerun numbers. Do not assume the candidates below are still unsupported: determine current status with `python3 training/diagnostic_coverage.py` and `python3 training/question_batches.py --decks training/decks/*.json --focal-id 27521806 --out training/reports/question-batches-current.json` before coding.

## Candidate generalized families (inspect complete Oracle clauses)

1. **Controller choice as a first-class effect**: Faeries — Boot Nipper ("your choice of a deathtouch counter or a lifelink counter"), Alchemist's Gift ("your choice of deathtouch or lifelink"). Model an enumerated choice, persist keyword counters, apply until-end-of-turn duration for temporary grants. Validate legal options, controller, counter type, and rejection of unparsed trailing text.
2. **Conditional continuous power/toughness**: Faeries — Briarberry Cohort ("as long as you control another blue creature"); Budget — Baird, Argivian Recruiter ("power greater than its base power"). Keep dynamic predicates and distinguish base from modified power; test gains and losses of qualifying permanents and timestamp/layer interactions. **Existing continuous +1/+1 regression failures at HEAD must be repaired first.**
3. **Linked zone-change effects and optional targeting**: Budget — Bovine Intervention (destroy target artifact or creature, then that permanent's controller creates an Ox); Arcbound Mouser (modular counter transfer on death). Resolve legal targets, indestructible, last-known controller, death triggers and optional target choice. Do not equate destruction with sacrifice.
4. **Combat assignment constraints**: Budget — Brave the Sands ("can block an additional creature each combat"). Extend declaration legality per blocker; don't implement as an extra blocker for one attacker.
5. **Object-linked exile and copiable values**: Faeries — Dino DNA (exile from graveyard; later copy *a card exiled with this artifact* with type, stats, color, and trample overrides). Preserve the source object's linked exiled-card identity and apply copy exceptions; reject other exile piles.
6. **Activated abilities with zone costs**: Faeries — Cloud of Faeries (cycling with discard as a cost, then draw), and an ETB untap-up-to-two-lands choice. Validate priority, zone legality, optional selection counts, and mana costs.

## Completion gates

For each family: check current diagnostic status; implement shared grammar and simulator execution rather than card-name branches; add real-card and renamed-unseen-card positive tests, parameter/controller variations, illegal target/choice tests, and rejection of unknown extra Oracle clauses. Run focused tests, full Python suite, and Java checks where applicable; re-audit both decks; record before/after card-copy and unique-name counts; commit only passing increments. Diagnostic support alone must not produce learning-eligible games.

This file is a work queue and source-backed Oracle analysis, **not** evidence of newly implemented mechanics or completed regression tests.