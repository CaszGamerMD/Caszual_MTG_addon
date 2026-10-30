# Paired teaching decks: Mono Red Gobs vs. Lupitas elves

These are user-supplied **Commander teaching decks**, built to feel like mirrors.
They are not literally the same cards, and their goals should not be forced
to tie. The AI should understand their common strategic *objective* while
discovering each deck's distinctive resource and payoff path.

## Verified source snapshots

- [Mono Red Gobs](https://archidekt.com/decks/14509839/mono_red_gobs)
  — **Krenko, Mob Boss**, 100 active cards, 38 lands, 25 creatures,
  19 equipment, 53 nonland cards with printed mana value <=3.
  Fixture: \`training/decks/14509839-mono-red-gobs.json\`.
- [Lupitas elves](https://archidekt.com/decks/14435337/lupitas_elves)
  — **Marwyn, the Nurturer**, 100 active cards, 37 lands, 31 creatures,
  7 equipment, 48 nonland cards with printed mana value <=3.
  Fixture: \`training/decks/14435337-lupitas-elves.json\`.

The Elf page lists **24 maybeboard copies**, excluded from its 100 active cards.
"Tokens" is a custom *mainboard* category in these Archidekt decks;
it is NOT itself a sideboard section. The live importer has a regression
test to prevent that accidental exclusion.

## Baseline comparison (no simulated wins claimed)

From 500 deterministic independently shuffled 7-card hands, using
the **same proxy** for each deck (2–4 lands plus at least two nonlands with
printed mana value <=3):

| Metric | Gobs | Elves |
|---|---:|---:|
| 3-land opening | 31.2% | 25.0% |
| 0–1-land opening | 15.2% | 18.6% |
| Playable opening proxy | 76.2% | 72.4% |
| Average lands in seven | 2.72 | 2.62 |

This opening proxy does **not** verify colored mana, available play patterns,
reasonable mulligans, or that a card is supported by the rules engine.
A few percentage points of difference do not prove or disprove balance.

Snapshot diagnostic card coverage was **53/100 playable** for Gobs and
**47/100 playable** for Elves. There are 47 and 53 unsupported copies,
respectively. **Marwyn is unsupported** as a commander.
**Do not run or interpret match win-rate comparisons as deck strength until
these blockers are resolved.** Diagnostic coverage is not full MTG legality.

## Shared goal, distinct journeys

The first compositional rules-to-strategy engine infers **tribal swarm** for
both decks, with combat damage as a shared likely goal.

- Goblins: token generation, lots of equipment, attacks and direct damage.
- Elves: mana-producing creatures, card-draw engines, board-wide amplifiers
  and finishing attacks.

This distinction must come from the cards' actual effect roles
(\`produces\`, \`needs\`, \`blocks\`), **never a Goblin-specific or Elf-specific
script**. The real-deck regression tests check that both reach the same
combat objective along distinct routes. A future learned AI must adjust
the route during play based on real cards drawn and the public board.

## Rules-and-strategy development gates

1. Preserve the imported exact 100-card mainboards as regression fixtures.
   Re-import only when a newer live deck snapshot is intentionally wanted.
2. Prioritize general rule families shared by many unsupported cards.
   Particularly important: **Marwyn's Elf-entry +1/+1 counters and scaling
   mana ability**, legal equipment attachment and bonuses, token entry/attack
   triggers, creature-mana activated abilities, and multi-creature amplifiers.
   Don't hard-code commander/card identities as a shortcut.
3. For a strategy card, distinguish **printed effect interpretation** from
   **rules-compiled executable effect**. Plans based on unsupported effects
   are tentative, not confirmed combos.
4. Once both decks have sufficient validated rules coverage, compare
   matched-seed games with both seats using the same adaptive AI,
   alternate who starts, include wins, losses, ties and real win turns.
   Separate actual game-rules wins from turn-limit life-score judgments.
5. For a teaching experience, also measure early meaningful actions,
   opening consistency, interaction/responses, stalled turns, recoverability,
   and decision explanations. Never artificially force 50/50 by manipulating
   shuffles, legal moves or opponent hidden information.
6. Promote neither training outcomes nor Minecraft integration while the
   full rules backend and evaluation gates remain incomplete.

## Reproduction

\`\`\`bash
python training/import_mirror_decks.py
python training/report_mirror_teaching.py --samples 500
python -m unittest discover -s training/tests -p test_mirrored_teaching_strategy.py -v
\`\`\`

The importer uses Archidekt's public deck API and fails visibly if unreachable.
The reporter checks both real decklist profiles and exact simulator card
coverage; it never manufactures a game score for unsupported cards.
