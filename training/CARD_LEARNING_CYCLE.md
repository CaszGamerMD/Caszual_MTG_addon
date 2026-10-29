# MTG Golem — repeating card-language learning cycle

This is the standing work protocol for **the standalone Commander simulator only** on `experiment/commander-ai-golem`. Do **not** migrate this to Minecraft until separately requested. Each pass must work from the current repository head, never from remembered coverage totals.

## One iteration

1. **Refresh and inventory.** Inspect new commits, CI outcomes, saved `training/decks/*.json`, and the previous cycle's unresolved items. Re-run the current diagnostic parser coverage and card-language grouping:
   ```sh
   python3 training/diagnostic_coverage.py
   python3 training/question_batches.py --decks training/decks/*.json --focal-id 5189995 --out training/reports/question-batches-current.json
   ```
   Record the current branch SHA, deck counts, unique unresolved names, and any tool/CI failures. These are **diagnostic parser metrics**, not Commander legality metrics.
2. **Choose a reusable language family.** Prefer failures affecting several cards across saved decks, then the focal Garbo Gobbos (`5254666`) and Getting Wild With Enchantments (`5189995`) decks, then rules hit in actual question logs. Inspect **all Oracle clauses** of each impacted card, not just a matching keyword. Families and templates in `question_batches.py` are heuristic; their affected-card counts overlap and are not guaranteed support gains.
3. **Decide what is missing.** Distinguish lexical parsing, parameterized grammar, target/choice legality, timing and priority-stack semantics, costs, zones, continuous/replacement effects, and full simulation mechanics. Explicitly mark any existing partial support. A text pattern being recognized does **not** mean its underlying rules execute.
4. **Implement transferable handling.** Add grammar productions and shared operations for the entire Oracle instruction, including costs, optional decisions and targets. Parameterize numbers, objects, types, self-references, and controllers. Compose with existing stack/events. Do **not** add exact-name fallbacks or drop unrecognized clauses. Unknown or incompletely executed programs must remain unsupported and must not generate learning-eligible game data.
5. **Prove the rule.** Add focused regression tests for (a) the motivating real card; (b) a previously unseen card name with equivalent rules text; (c) another amount, controller or relevant type; (d) targets, timing, choices, ordering and zone transitions; (e) extra unknown clauses rejected without silently accepting a subset; and (f) important cross-interactions with existing rule families. Run focused tests, then:
   ```sh
   python3 -m unittest discover -s training/tests -v
   ```
   Where Java rules checks or workflow checks apply, run those too. Record exactly which tests ran and which could not be run; do not infer passing results.
6. **Reaudit, compare, persist.** Repeat both inventory commands from step 1 against the same deck snapshots. Record before/after unresolved names, card copies and the changed grammar family. If tests fail or coverage regresses, fix or revert the change before promotion. Commit a small coherent increment to this experimental branch with code, tests, and accurate results. Refresh HEAD and reconcile concurrent edits; never force-push or overwrite another worker.
7. **Repeat.** Move to the next highest-impact unresolved family. When a rule is blocked by a more foundational mechanic, record that dependency and select another candidate. Each scheduled run resumes from the current branch and freshly calculated reports rather than reusing stale unsupported-card totals.

## Completion and safety gates

- **Diagnostic parse-supported:** the entire Oracle program can be imported and executed by the specific diagnostic subsystem being measured; the result is verified by representative positive and negative tests.
- **Partially supported:** a clause, mechanical primitive or narrow diagnostic use works but some required text, combined effect or decision semantics do not. It stays in the unresolved queue.
- **Unresolved:** not recognized, not fully executed, or unsupported by the necessary backend. Remains blocked and logged.
- **Full legal Commander support:** requires correct game rules for full targeting, choices, priority, replacement and prevention effects, continuous effect dependencies, command zone, multiplayer and other interactions. The currently incomplete two-player diagnostic is **not** full Commander and is **never eligible to train the final player** merely because import coverage improves.

Each cycle summary must include: branch/commit, number of saved decks scanned, before/after unresolved counts (with count unit), grammar/rules changes, test results, new discoveries, current blockers, and exact next candidate. Do not claim an unchanged, untested or locally speculative result as verified. Keep the viewer work and the Minecraft mod separate from rule-learning changes.
