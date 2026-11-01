# Oracle language learning cycles — composed library operations (2026-11-01)

Branch: `experiment/commander-ai-golem`. Starting GitHub commit:
`06f5f061de31f062d829d605ad2267ba3ad40ae1`.

All metrics below are **diagnostic import/execution support** across seven
committed 100-card decks, not certified Commander legality or eligible AI
learning. The model semantic reader remains read-only and cannot promote an
unverified understanding directly into an executable card.

| Cycle | Transferable program operation | Motivating real deck card | Unique unresolved before → after |
| --- | --- | --- | --- |
| 1 | Whole-text search, optional reveal, **put onto battlefield**, shuffle, and deferred entry triggers | Unfamiliar library-search examples | 147 → 147 |
| 2 | Typed **additional sacrifice cost** on a complete search program; validate controller/type/color before mana payment, pay during casting, queue death triggers above the spell | Natural Order | 147 → 146 |
| 3 | Typed **mana-value ≤ X** search binding, declared X payment choices, and an owner's-library self-shuffle step validated against the card's own name | Green Sun's Zenith | 146 → 145 |

The changes compose small trusted instructions. The same grammar and runtime
are exercised on unfamiliar spell names, changed types/colors, an artifact
sacrifice cost, failed searches, illegal payment choices and unmatched extra
sentences. No card-name dispatch was added to the executor. The only name
comparison certifies that a printed self-reference actually refers to the
source card; renaming both source and Oracle reference retains support.

## Mechanics and correctness boundaries

- Searches use a deterministic private-library choice for this diagnostic,
  not a claimed optimal strategic decision. Search results enter through the
  established permanent-entry event path. No result means no fabricated card;
  shuffle still happens.
- Sacrifices are **costs**, not targets or resolving spell effects. They are
  validated while the card remains in hand; illegal choices do not consume
  mana or move a card. After casting, sacrificing remains paid even if the
  spell is countered. Phased-out or opponent-controlled permanents are not
  eligible.
- X is bounded to 0–1000, validated before payment, and applied to the
  *printed* mana value of candidate library cards at resolution. The existing
  mana engine still pays the total cost. The search and spell self-shuffle
  are distinct ordered instructions.
- An unknown additional sentence, unsupported search target/zone, unsupported
  additional cost, or mismatched source name blocks the whole card. These
  programs do not generalize automatically to arbitrary replacement effects,
  player choices, hidden-information policy, or all future Oracle grammar.

## Measured outcome

- Starting: **550/700** supported card copies; **147** unique unresolved.
- After three cycles: **552/700** supported; **145** unique unresolved.
- Lupitas Elves: 74/100 → 76/100. Garbo Gobbos and Getting Wild remain 100/100.
- All 19 `test_library_search*.py` focused regression tests passed after
  these additions.

## Next focus

The largest unresolved groups still involve activated abilities, token
creation/replacement, combat triggers, and equipment. Prefer complete typed
target-and-choice bindings over widening text matches without executable
rules. Continue testing new semantic grammar on unseen names and altered
parameters, with full-card rejection when a necessary operation is missing.
