# Blind Commander-legal Scryfall Rules Learning

## Target and validity

Goal: **at least 10/15** on a brand-new random batch of 15 distinct paper
Commander-legal cards from Scryfall, with the WHOLE card accepted by the
diagnostic rules compiler. Never cherry-pick or curate a batch. Repeat fresh
batches after generic rule improvements, and re-run the exact original corpus.

This threshold measures **diagnostic importer recognition only**, not full
legal Commander-game execution. A true ability implementation must also have
legal-action, costs, targets, stack-resolution and state tests. Do not cheat
by marking unsupported code as supported, by ignoring leftover Oracle
instructions or by swapping game rules based on a card's name.

Baseline initial test: GitHub Actions run 41064652535,
**1/15 accepted**. Raw Scryfall JSON is retained as artifact
`blind-scryfall-commander-knowledge-exam`, id `12982482012`.
The repeatable GitHub CI workflow is
`.github/workflows/scryfall-rules-learning.yml`; it obtains that source
artifact, replays 15 known cards, then fetches 15 **fresh** random cards.
Every checkpoint prints `RULE_LEARNING_CHECKPOINT`, stores both exact
Scryfall source samples, reports what failed, and prints goalMet.

New hourly automation **MTG Random Card Rule Learning** works separately
from the existing MTG Card Learning task. It should run multiple useful
read → generalize → implement → test → retest cycles per session, only stop
once target is verified.

## Original unsupported corpus: generalize these mechanism families

- **Radagast of Rhosgobel:** once-per-turn cost reduction plus timing
  permission, not a name-specific shortcut.
- **Spoils of War:** legal X based on opponent graveyard types, then divide
  +1/+1 counters among several legal targets.
- **Seal from Existence:** intrinsic ward, linked ETB exile to LTB return,
  valid nonland opposing targets and stack/ward checks.
- **Kithkin Daggerdare:** generic colored mana + tap activation cost,
  targeted *attacking* creature boost until end of turn.
- **Caller of the Untamed:** draft/sealed pregame reveal/exile and token-copy
  activation; requires an explicit supported game format and object storage.
- **Ichorspit Basilisk:** Toxic N as combat-damage-triggered poison counters
  with poison-based loss and deathtouch interactions.
- **Ronom Unicorn:** sacrificing the source as an activation cost, targeting
  and destroying an enchantment, invalid target/fizzle and timing.
- **Life Finds a Way:** nontoken creature ETB with actual power threshold;
  populate copies of an existing creature token. Targeting/choices needed.
- **Hopeless Nightmare:** ETB discard/life loss, graveyard-leave scry trigger,
  and an activated self-sacrifice cost.
- **Spitfire Lagac:** landfall via land-entry event and damage to each
  opponent (do not treat a land as a creature).
- **Ihsan's Shade:** protection from a color. Generic intrinsic protection
  parser and diagnostic importer bridge now added, including arbitrary
  colored-name tests.
- **Solarium Sentry:** opponent spell cast event and mana-value threshold
  trigger with controller gaining life.
- **Make Disappear:** Casualty N sacrifice as an optional casting cost,
  triggered copy on stack, new target selection and conditional counter
  unless its controller pays mana.
- **Dirge Bat:** Mutate as a new cast mode with merge rules, characteristics
  and mutate triggers; Flash and Flying alone are not sufficient.

The only original accepted card was **A.I.M. Labs**, whose diagnostic roles
include life gain; this is not certified land/stack conformance.

## Fresh batch findings: do not overfit

From the first fresh batch after adding intrinsic color protection:
**2/15 diagnostic accepted**. New missed families included global subtype
anthems (Anaba Spirit Crafter), ETB counter manipulation (Quarry Hauler),
Bestow (Nyxborn Unicorn), Flurry N, temporary exile-to-cast permissions,
Kicker with conditional ETB effect, modal spell options, additional creature
ETB triggers, untap restrictions and multi-cost activated artifact abilities.

Generic global creature subtype anthems (+ or - P/T, both controllers) and
additional intrinsic keyword bridging have since been added with tests.
Each *new* random batch varies; avoid treating a smaller score as a regression
without also checking the identical original 15.

## Current work checkpoints

- Baseline original 15: **1/15**.
- Latest verified original-corpus score as of 2026-10-30 13:51 UTC:
  **2/15** (CI run 41066534033).
- Latest verified fresh-sample score as of the same run:
  **1/15** (different random cards; target not met).
- Active work branch: `experiment/commander-ai-golem`.
- No Minecraft integration or production-trained gameplay is claimed.

## Recommended learning loop

1. Inspect the actual Oracle text, complete importer error and executable
   abilities for a set of unsupported cards. Choose the most reusable
   semantic grammar pattern, not the easiest card to whitelist.
2. Implement a typed rule block with costs, subject selectors, targeting
   and resolution. Connect the new block to the shared existing event/stack
   engine. Reject incomplete, unsupported combinations.
3. Test unknown renamed cards, novel creature subtypes, different colors,
   opponent-controlled permanents, invalid costs/targets, event order,
   state changes and removal of a source on the stack.
4. Run previous tests, exact 15 regression, and 15 fresh random cards;
   report both results and retained CI run/artifact links.
5. If fresh score <10, keep the checkpoint and iterate. At 10 or higher,
   require tests passing and explicit diagnostic-only qualification, then
   stop the hourly rule-learning automation.

Use `training/COMPOSITIONAL_RULES.md` for architectural rules and
`training/compiled_rules_knowledge.py` for confirmed-vs-hypothetical
strategy evidence.
