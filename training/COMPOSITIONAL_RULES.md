# Compositional Oracle Rules — "Reading the Card Explains the Card"

## Product goal

MTG Golem must parse new card rules into reusable game instructions,
rather than learn one handwritten card profile at a time.

The desired compiler pipeline is:

1. Read the full printed type line, cost, power/toughness and Oracle text.
2. Bind references to the source object, controller, targets, subtypes,
   colors, zones and legal timing windows.
3. Build an intermediate program containing ability kinds, event conditions,
   costs, selections, sequences and effect operations.
4. Validate every byte of meaningful rules text: **unknown remainder fails
   the whole card**. Never treat incomplete understanding as legal gameplay.
5. Execute supported instructions with the same common engine that supplies
   legal actions, priority, the stack, timing, replacement effects,
   state-based actions and current characteristics.
6. Give the strategy system a read-only view of *compiled, executable*
   roles. Printed-text guesses remain candidate paths, not proven combos.

## What has been implemented now

**1. Independent power-mana and triggered-ability compilation.**

- training/composable_oracle.py compiles a tap ability that adds one
  mana color in an amount equal to the source's power.
- The card-events compiler independently parses all remaining text as
  generic triggers, static effects and keywords.
- The simulator reads the source's **effective power at activation**, so
  counters and temporary buffs change the amount, and restricts the
  choice to the printed color. Summoning sickness, tapping and priority
  remain enforced.
- Proven on the actual Marwyn, the Nurturer, plus a renamed synthetic
  Goblin with a different mana color. It is not card-name dispatch.

**2. Ordered execution of known effects.**

- training/oracle_sequence.py composes independently understood effects
  across comma-and-then and conjunction connectors.
- Supported safe atoms include creature-token creation, draw, life gain,
  self counters, Treasure creation, scry, surveil and mill.
- The complete parsed sequence is attached to one triggered ability.
  The stack resolves it in order, retaining the full creature-token
  specification. Unrecognized actions or target-dependent unsupported
  instructions reject the entire ability, not just the extra clause.
- A newly invented Elf creature that creates a token *then* draws a
  card has been parsed and executed in a real stack test.

**3. Shared compiled rules knowledge for strategy.**

- training/compiled_rules_knowledge.py extracts confirmed trigger
  conditions, selectors, sequential effects and mana activation details
  from the **successful diagnostic importer**.
- Unknown whole cards yield no verified roles.
- training/deck_adaptive_strategy.py can use these compiled mechanic
  roles while scoring only engine-provided legal actions; the unverified
  deck-text plan remains a hypothesis.

## What is still missing

This is an extension of a *partial diagnostic Commander engine*,
not a claim to understand arbitrary MTG text. Remaining work includes:

- Generic parsing for costs, targets, intervening-if conditions, copied
  abilities, replacement and prevention effects, and object references.
- Correct resolution checks for each selected target and an explicit
  variable/context scope for X, "that creature", "it", "that many", etc.
- Multi-line nested conditional/optional/repeat instructions without
  looping or dropping clauses.
- Continuous effect ordering, timestamps, layers, protection and
  replacement ordering in all supported cases.
- Genuine multi-action strategy sequencing over verified dependencies.
- Full regression and differential validation on unseen card printings,
  plus Commander-wide rules coverage before declaring AI training valid.

## Quality gates

- For unfamiliar cards, use a new name/subtype/color on the *same
  mechanics* and compare behavior, not only parse acceptance.
- Check costs and timing, and reject malformed extra text.
- Verify trigger creation, priority, stack resolution, quantity and
  effect ordering.
- Prevent unsupported recursive token-entry triggers from being accepted.
- Keep unsupported whole cards out of strategy training and matched
  win-rate claims.
- Work remains in the GitHub experiment branch, separate from Minecraft.

## Focused checks

Run:

    python -m unittest discover -s training/tests -p test_composable_power_mana.py -v
    python -m unittest discover -s training/tests -p test_oracle_sequence.py -v
    python -m unittest discover -s training/tests -p test_compiled_rules_knowledge.py -v

The dedicated GitHub Actions workflow also verifies previous
regeneration/mentor regressions and refreshes full saved-deck diagnostic
coverage.
