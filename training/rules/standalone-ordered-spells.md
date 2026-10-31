# Standalone ordered Oracle instructions

## Reused grammar and execution

- `oracle_abilities.effect` and `oracle_sequence.parse_sequence` already compile
  fully recognized sequences in triggered abilities. A coordinated verb may
  inherit an explicitly stated `you` subject: `You draw two cards and lose 2
  life.` Both verbs still compile as independent existing `Effect` atoms.
- For ordinary Instant/Sorcery cards, `import_diagnostic_card` now accepts a
  **whole-text** `ordered_effects` program containing two through eight
  self/controller draw, gain-life, and lose-life instructions. Each must be
  target-free and mandatory; unknown text rejects the entire card.
- `sequence_spell` resolves using the **same** `_resolve_entry_effects` ordered
  executor as a triggered sequence. Nothing executes when the spell is cast:
  it waits on the stack, then draws/gains/loses in Oracle order at resolution.
- `compiled_rules_knowledge` emits ordered `spell_resolution` evidence and
  mechanical strategy roles only for fully compiled programs.

This is compositional grammar and interpreter reuse, not a card-name lookup.
The diagnostic still does not certify full Commander legality. No training
result is promoted to `learningEligible=true`.

## Probes and boundaries

- The real paper-legal **Night's Whisper** card compiles without any special
  case. Changed names, amounts, costs, and Instant timing are tested.
- A three-instruction unseen spell exercises shared subject and sequential
  gain, draw, then loss.
- Extra sentences, choices, targets, conditional costs, and unrelated card
  types must fail closed rather than execute partial instructions.
- The saved 15-card random Scryfall snapshot changes from **0 to 1** accepted
  diagnostic cards; this is 1/15 **importer coverage**, not full game proof.

Run `python3 -m unittest discover -s training/tests -q` and optionally
`python3 training/scryfall_random_exam.py --count 5 --rounds 3 --source
training/reports/random-commander-exam-20261031/scryfall-source.json --out
training/reports/random-commander-exam-20261031-recheck` after sampling.
