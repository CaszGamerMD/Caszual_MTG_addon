# MTG Golem — Goblins and Elves completion, fifth three-cycle pass (2026-11-02)

Scope: seven saved 100-slot decks, experimental standalone parser and simulator
only. Start local SHA `ac25135` / published GitHub `a894518`. No Minecraft mod
changes. `learningEligible=false` remains mandatory.

## Seven-deck audit, refreshed after each tested cycle

| Cycle | Reusable whole-card rule | Motivating deck | Recognized slots | Unique unresolved names |
|---|---|---|---:|---:|
| Baseline | Previous published wave 4 | — | **597/700** | 101 |
| 1 | ETB/attack optional any-number targeted Equipment attachment; no control change | Armory Automaton, Mono Red | **598/700** | 100 |
| 2 | X-card revelation; may place all eligible permanent cards simultaneously, remainder to graveyard | Genesis Wave, Elves | **599/700** | 99 |
| 3 | Attack-triggered +1/+1 counter, combat-damage dN roll, conditional doubling | Sword of Hours, Mono Red | **600/700** | 98 |

Current slot recognition: Lupitas elves **95/100**, Mono Red Gobs **91/100**,
Budget Deck 79/100, faeries 71/100, Getting Wild with Enchantments 100/100,
Garbo Gobbos 100/100, squirrels 64/100. No previously recognized slots lost.

## New runtime and parsing semantics

1. **Multi-Equipment entry/attack:** A single closed grammar accepts printed
   `this creature` and equivalent quoted card-name self references without
   matching any particular card name. Entry and declared attack generate
   independent stack triggers. The controller selects zero or more legal
   target Equipment objects at placement, including equipment under opposing
   control. Resolution verifies the original creature incarnation, target
   Equipment incarnation, targetability, attachment legality and protection.
   The action changes the Equipment's attachment, never controller or owner.
   Unavailable targets fizzle independently; a departing host invalidates
   all attachment attempts. `choose_multi_equipment_targets` is the explicit
   may-choice hook.
2. **Genesis-style X revelation:** A closed Oracle grammar extends the
   existing reusable X-sorcery family. X is selected and paid on casting.
   Spell resolution reveals exactly the top X cards (or all remaining),
   checks each candidate's mana value and permanent type, accepts an optional
   selected subset, places that subset onto the battlefield as one ETB batch,
   and puts the remainder in the graveyard. A diagnostic policy opts to play
   all supported legal permanent candidates; unknown cards can lawfully be
   declined. Basic native lands are also classified as permanent cards.
   A successful full zone transaction must precede replay logging so card
   conservation checks never inspect cards in temporary reveal memory.
3. **Combat die Equipment:** A closed three-line grammar composes the existing
   equipped-attack +1/+1 counter trigger with a new independently resolving
   combat-damage-triggered die operation. Positive damage to either player or
   creature qualifies. Damage split by trample is aggregated into a single
   source event per combat damage step. Each triggered dN is deterministic
   from a dedicated RNG sequence, compares to the *actual* damage after
   replacement/prevention, and adds as many +1/+1 counters as the same live
   creature currently has if the roll is greater than damage or the maximum
   die result. Replacements for added counters apply. It survives Equipment
   leaving after the damage event; absent or reincarnated hosts get no counters.

All three whole-card grammars reject unmodeled clauses and incorrect permanent
types, and tests include previously unseen names and different parameters.

## Verification

- Focused `test_deck_completion_wave5.py`: **6/6 passed**, two tests per
  family covering real cards, unseen names, illegal/extra Oracle text, source
  departure, stack and target timing, controller identity, graveyard and
  battlefield movement, X values, blocker damage and deterministic die rolls.
- Seven-deck `diagnostic_coverage.py`: **600/700**, 98 unique unsupported
  Oracle names, no lost support. `question_batches.py` inventory refreshed.
- Affected regression modules: **30/30 passed**, covering X-spells, Equipment
  counters and attachments, and library search. Full
  `python3 -m unittest discover -s training/tests -q`:
  **1,337 tests in 735.225 seconds; six failures, one skip, zero new failures**.
  The six failing methods match the previous checkpoint exactly: five
  `test_planeswalker_damage.py` methods and
  `test_simulator.py::test_real_deck_report_keeps_runtime_questions`.

## Remaining target decks

- **Mono Red (9):** Squee, Dubious Monarch; Fortune Thief; Howlsquad Heavy;
  Sword of Hearth and Home; Sword of Truth and Justice; Mister Gutsy;
  Raubahn, Bull of Ala Mhigo; Rhuk, Hexgold Nabber; Dissection Tools.
- **Elves (5):** Mosswort Bridge; The Great Henge; Growing Rites of Itlimoc //
  Itlimoc, Cradle of the Sun; Bow of Nylea; Sword of Once and Future.

Suggested next families: Raubahn's ward-life payment and attack attachment,
and The Great Henge's greatest-power generic cost reduction, mana ability
plus life gain, and nontoken creature entry trigger. Henge's mana-gain side
effect must be integrated with automatic payment sources as well as manually
activated mana abilities; accepting just its cost-reduction clause would be
unsafe. Full Commander legality, multiplayer and unresolved Oracle programs
remain explicitly outside the current diagnostic certification.
