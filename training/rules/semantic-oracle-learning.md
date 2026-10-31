# LLM Oracle comprehension, independent of legal execution

## Why the old improvement metric was misleading

The `scryfall_random_exam.py` verdict measures how many complete cards the
current diagnostic *executor* can handle. It does not measure whether a
language model can understand their instructions. Adding exact regex
alternatives one spell at a time does not create an adaptable language reader.

The new `oracle_semantic_reader.py` adds a **separate comprehension track**:

1. Break every Oracle card into all printed instruction lines and faces. Do
   not merge split spells or discard modal options, reminder text, alternate
   costs, or unknown instructions.
2. An LLM proposes semantic frames for each line. Each frame contains timing,
   cost, an explanation, precise operation words with source evidence, and
   general mechanical capabilities. Linked effects, triggers, modal choice,
   static abilities and activated abilities are explicitly representable.
3. Validate **complete line coverage**, the correct face and line identity,
   no extra JSON keys, grounded amounts and verbs, and evidence for separate
   sentences/coordinated verbs. The validator is **not** proof that the model
   understood or interpreted a Magic rule correctly.
4. Cluster the proposed mechanic families across all input cards. If an
   independent existing importer verdict is requested, show how many
   unsupported cards need each family. This makes the next executor task a
   *mechanic*, not a list of card names.
5. Keep all proposals read-only. Neither LLM output nor evidence matching
   makes an unsupported card playable, changes a game state, or makes learning
   eligible. Future execution promotion needs typed validation, target legality,
   rules tests, and an independent unseen-card evaluation.

The game engine never imports this model reader. This avoids model/network
latency, silent charges, prompt injection into game actions, and accidental
confusion of understanding with legal resolution.

## Reusable execution-block groundwork (October 31, 2026)

The typed bridge is `training/semantic_execution_blocks.py`. It separates
**candidate comprehension** from **trusted, executable compilation**:

1. The model's `draw`, `gain_life`, `lose_life`, `scry`, `surveil`, `mill`,
   `create_token`, etc. remain quoted, untrusted semantic verbs. The read-only
   `inspect_semantic_proposal(card, proposal)` associates verbs with *possible*
   existing handlers without granting playable status.
2. The independent deterministic compiler supplies `oracle_abilities.Effect`
   objects. `compile_effects(tuple_of_effects)` checks **every** field of
   **every** step and produces immutable `AtomicBlock` objects only for fully
   implemented target-free primitives. Missing targets, new qualifiers,
   optional costs, unknown instructions and unsupported scopes reject the
   **whole program** before it can be lowered.
3. The proven `sequence_spell` path in `simulator.resolve_spell` now converts
   trusted effects into those blocks. Only after the existing legal cast,
   payment and priority-stack resolution does `stack_event()` pass the blocks
   to the existing `_resolve_entry_effects` handlers. No LLM proposal reaches
   this path, and the block compiler is **not** a new spell-casting API.
4. `training/semantic_block_audit.py` compares saved Scryfall sources with
   saved semantic proposals using the **Oracle-text fingerprint**. It counts
   potential reusable handlers and missing primitives while retaining rejected
   cards. Its output has `executionReady=false` and `learningEligible=false`.

Existing kernel primitives initially exposed through this bridge are ordered
draw, self/opponent life loss, controller life gain, scry, surveil, mill and
creature-token creation with a complete `TokenSpec`. This is a *foundation*
for reuse, not a claim that the language model can correctly bind all values.
Amounts must presently be bounded literal integers; recipients are a checked
enum. Targets, duration, arbitrary conditions, variable amounts and timing
remain explicit next-stage typed bindings. A matching handler name alone is
insufficient: even a model proposal with all operations mapped cannot execute.

This is the intended progression:

1. **Read** every source line and face (untrusted semantic proposal).
2. **Verify** interpretation independently, including targets, dependencies,
   amount expressions, costs, timing and whole-card completeness. A general
   approval pipeline from model proposals is **not yet implemented**.
3. **Compile** verified instructions into a typed program of reusable blocks.
4. **Execute** only through the existing stack, payment, legality, choices,
   state-based actions and event handlers.
5. **Prove** behavior through unfamiliar-card state-transition tests and
   regressions before counting a card supported.

Audit already-saved model results without another paid request:

```bash
python training/semantic_block_audit.py \
  --source path/to/scryfall-source.json \
  --proposals path/to/semantic-proposals.json \
  --out path/to/semantic-block-audit.json
python -m unittest discover -s training/tests -p test_semantic_execution_blocks.py
```

## Repeatable 15-card trial

Prepare the previously saved **unselected** Scryfall sample without a network
call (the report includes all card faces and printed text):

```bash
python3 training/oracle_semantic_batch.py \
  --source training/reports/random-commander-exam-20261031/scryfall-source.json \
  --prepare --out training/reports/oracle-semantic-audit
```

Expected on this snapshot: **15 cards, 33 Oracle lines**. The prepared file
has the exact prompt and strict JSON Schema. After external review or a model
response, submit an array of one response per card:

```bash
python3 training/oracle_semantic_batch.py \
  --source training/reports/random-commander-exam-20261031/scryfall-source.json \
  --responses proposals.json --diagnostic \
  --out training/reports/oracle-semantic-audit
```

The optional real-model path is **explicit** and requires a separately
configured `OPENAI_API_KEY`, chosen Responses model, and API billing. It is
never automatically invoked by training or gameplay:

```bash
python3 training/oracle_semantic_batch.py \
  --source training/reports/random-commander-exam-20261031/scryfall-source.json \
  --invoke --model gpt-6-astra --diagnostic \
  --out training/reports/oracle-semantic-audit
```

The existing random-card benchmark also supports an explicit
`--semantic-model gpt-6-astra` flag. If supplied, its same 5x3 unselected
sample gets a separate `semantic-proposals.json` alongside the original
`results.json`; diagnostic acceptance remains the same independent verdict.
Without that flag, the benchmark remains free of model calls and charges.

**Live status:** The GitHub owner-branch `OPENAI_API_KEY` now successfully
completed a bounded five-card run (5 model proposals, 10 Oracle lines, 10
candidate capability families, 0/5 accepted by the independent diagnostic
executor). The subsequent 15-card attempt stopped on an ungrounded model verb
before it could save a full semantic report. Per-card semantic rejection was
then isolated, preserving other accepted proposals while still aborting on
authentication or transport failures. A new 15-card batch has **not** been
run with the isolation fix. Neither test is a correctness certification.

## Next interpreter milestones

- Create a typed game-effect graph from frames (source, controller, event,
  costs, targets, duration, actions, dependencies), then independently certify
  supported primitive handlers.
- Add explicit links between created events and measurements such as "cards
  milled this way" so the engine can resolve *Tribune of Rot*-like programs.
- Add a generic option selection/target legality handler for modal cards.
- Build a semantic correctness benchmark with independent card rulings and
  game traces. **Model claims and exact quotes are not that benchmark.**

Current `learningEligible` remains false. These are independent diagnostic
tools outside Minecraft.
