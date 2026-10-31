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
enum. General targets, durations, arbitrary conditions, variable amounts and
timing remain explicit next-stage typed bindings. A matching handler name alone
is insufficient: even a model proposal with all operations mapped cannot execute.

### Four-step targeted-modifier increment

`training/composed_modifier_blocks.py` independently verifies a **limited,
complete** family of targeted instants/sorceries and composes these typed
blocks without dispatching on card names:

1. **Target binding:** exactly one target creature, or zero to two distinct
   target creatures. The existing engine verifies hexproof, shroud and
   protection at cast time **before paying** and again at resolution. If all
   chosen targets are illegal, the whole spell fizzles; if some remain legal,
   only those receive the modifier. Choosing zero targets for an "up to"
   instruction is legal.
2. **Temporary modifier:** signed P/T deltas, a verified keyword grant, or a
   color-setting effect, all expiring at the same turn's cleanup. Multiple
   targets share the same checked instruction, applied to each legal target.
3. **Conditional follow-on effects:** a typed "if you control an [type or
   subtype]" predicate evaluated at resolution, then existing ordered card
   draw or complete creature-token creation blocks. Effects with independent
   sentences still require the preceding targeted spell to resolve.
4. **Oracle evidence acceptance:** verb anchors recognize standalone keyword
   names (for example "Haste") and stat-characteristic phrases ("power and
   toughness") while still rejecting fabricated verbs and source omissions.

The whole-text parser currently covers forms such as *Strength of Arms*,
*Aphotic Wisps*, *Cutthroat Maneuver*, and unknown names or changed P/T values
with the same grammar. It rejects unknown extra sentences, unsupported keyword
names, targeting modes beyond this family and non-instant/sorcery card types.
The trusted compiler—not a language-model proposal—sets `modifier_program`;
the simulator then uses its real payment, priority stack, event kernel and
cleanup. Independent tests exercise delayed resolution, two-target partial
failure, color/keyword expiration, conditional token creation and failed cast
legality. These tests demonstrate an increment in *mechanical* reuse, not
general semantic verification or full Commander legality.

### Resolution-time quantified effect blocks

`training/counted_effect_blocks.py` adds an immutable `BattlefieldCount`
operand and `QuantityBlock` compiler. Unlike a literal amount, this operand
is bound to current `EventGame` state at the **moment its instruction resolves**:

- Relation: permanents you control, permanents opponents control, or any
  permanent on the battlefield.
- Kind: creature, artifact, enchantment, land, planeswalker, or a named subtype
  such as Elf; optional tapped/untapped or nontoken qualification.
- Effect: multiply a verified literal factor for draw, gain life or creature
  token creation. The resulting complete `Effect`/`TokenSpec` passes through
  the same atomic compiler as literal effects. Zero skips only that operation;
  counts beyond the sandbox's 1000-effect bound pause with an explicit question
  instead of silently truncating the amount.

The whole-text importer accepts counted spells with additional verified
fixed steps, and the **same quantity block** can be used after a targeted
temporary modifier, including one with an Equipment condition. A sequence
that creates creatures and then draws once per creature recomputes the second
count after the new tokens exist. This deliberately avoids evaluating count
expressions at cast time. Unknown clauses, costs, targets, linked quantities,
unsupported effects, and invalid filter phrases still reject the entire
program. A model proposal remains untrusted, never executable.

The read-only semantic block inspector now reports `candidateCountOperand`
when a model operation's potential handler matches a single independently
parsed count operand in the complete Oracle line. The report records the
relation, type/subtype, status filter and literal factor for review, but
retains `executionReady=false`, `approved=false` and
`learningEligible=false`. This exposes reusable operand families in LLM
batch audits without treating model claims as gameplay instructions.

Examples of mechanically reusable wording include:

```
Draw a card for each creature you control.
You gain 2 life for each Elf you control.
Create a 1/1 green Saproling creature token for each creature you control.
Target creature gets +1/+1 until end of turn. Draw a card for each creature you control.
```

This is a **bounded quantity-binding increment**, not implementation of
arbitrary numeric Oracle expressions, linked "this way" events, modal choice,
or triggered abilities with variable amounts.

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

**Live status:** The GitHub owner-branch `OPENAI_API_KEY` successfully ran a
bounded 15-card sample after per-card semantic rejection isolation (12 accepted
evidence-checked proposals, 3 rejected, 35 proposed operations, 4 potential
handler matches, and 0/15 supported by the independent diagnostic executor
at that snapshot). The evidence validator had false negatives for standalone
"Haste" and "power and toughness" wording, addressed above. These are
proposal-format/evidence results, **not** verified semantic correctness or a
fresh 15-card executable-coverage claim; the four-step increment is tested on
specified mechanics separately. No new paid model batch is implied.

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
