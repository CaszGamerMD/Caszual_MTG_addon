# Play-test questions: seed 242

Six distinct real-deck pairings ran with a ten-turn-per-player limit. Four
completed that window, two ended earlier under the incomplete diagnostic rules.
95 distinct unsupported cards appeared in hands or discards. These are card
coverage gaps, not 95 runtime crashes. Runtime questions are retained separately
in each match's rulesProgress. Complete before/after summaries and the encountered
card queue are committed in examples/questions-242.json.

## Addressed

The generic Oracle parser now understands “Creatures you control get +N/+M” and
“Other COLOR creatures you control get +N/+M.” No card names select these effects.
Glorious Anthem can be imported as a playable diagnostic enchantment. Glen
Elendra Liege's separate blue and black bonuses parse and stack for multicolored
creatures, but its hybrid casting cost remains unsupported, so it is not playable.
Tests check controller boundaries, self exclusion, bonuses ending when the source
leaves, changed numeric amounts, and rejection of extra unhandled text.

Official ruling: https://magic.wizards.com/en/news/feature/double-masters-2022-release-notes-2022-06-24

## Remaining questions and implementation work

- Sol Ring: mana abilities that produce multiple mana require a persistent mana
  pool; a tapped source must not be counted as two independently reusable sources.
- Mirkwood Bats: creation/sacrifice events must be distinct from entry/death events.
- Peregrin Took: token replacement needs atomic event batches and must not recurse.
- Cloudshift and Path to Exile: legal targets, ownership, exile/new-object identity,
  optional library search, shuffling, and response windows need implementation.
- Cabal Slaver: combat-damage events need a player subject and discard choice.
- Liege: hybrid payment must choose legal color alternatives without double spending.

The same seeds were rerun after the parser change. Outcomes/turn counts were
unchanged; the shuffled matches did not establish strategic improvement. 84
regression checks pass. These diagnostics still do not update learned policy
weights or control live Minecraft golems.

## Generic counter and keyword follow-up

The parser now supports “put N +1/+1 counters on each creature you control” as
an entry-trigger effect, and “(Other) (COLOR) creatures you control have KEYWORD”
as a continuous grant for the supported combat keywords. This covers Cathars'
Crusade and Bloodmark Mentor through text parsing. Granting a keyword requires
matching type/color/controller, and ends when the source leaves. Counter effects
select controlled creatures at resolution and include the entering creature if
it is still present. Death-trigger counter effects remain rejected until their
resolution path is implemented. Extra unhandled clauses reject the entire card.

87 checks pass, including unfamiliar names and changed counter amounts. The six
seed-242 pairings were rerun; their summaries are in
examples/counter-keyword-242.json. These are still incomplete diagnostic games.
Token replacement, multi-mana production, sacrifice costs, hybrid payment and
exile/return effects remain open; no policy learning is claimed.
