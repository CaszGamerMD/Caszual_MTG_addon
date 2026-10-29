# Shared-rule question batching

This batch uses engine commit 4336ae1315f5310ff5f52fbc3f62ac283229c097 plus question-report tooling. The shared branch includes the other MTG thread's rules work; coverage gains are not attributed to this planner.

40 games, ten per saved opponent, alternating starting seats. Seeds 5189995–5190034; ten turns per player. Normal outcomes take precedence, otherwise higher remaining life wins and equal life ties.

Results: 24 wins, 16 losses, 0 ties (60% wins), 16 games decided at the turn limit. No blocked games or runtime questions. The focal enchantment deck has 35 unresolved cards; all five decks have 209 unique unresolved cards. These remain incomplete-rules simulator diagnostics, not full Commander strength estimates.

`question-batches.json` groups the current queue by candidate rule family and repeated parameterized clauses. Families overlap, and a card may need several rules. Existing recognized clauses are marked using partial Python grammar checks; an unrecognized component is not proof that the game lacks that rule. The planner is advisory and never grants card support. The batching report was regenerated after the gauntlet as reporting-only refinements were made; simulation engine files were unchanged.

Validation: the synchronized full suite passed 469 tests, including a new 32-combination unseen cast-language matrix; the final planner-only refinement passes two focused tests. Full summary, questions and compressed replays are retained alongside this report.
