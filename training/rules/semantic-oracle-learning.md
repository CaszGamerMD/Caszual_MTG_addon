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

In this development environment the API key is **not configured**, so only
the offline preparation and mocked protocol tests were run. Do not claim an
LLM passed 15 cards based on a prepared request or on the validator alone.

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
