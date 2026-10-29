# Ellivere gauntlet: 40 diagnostic games

Source: https://archidekt.com/decks/5189995/getting_wild_with_enchantments_fix_land_count

The snapshot imports one Ellivere of the Wild Court commander and 99 main-deck
cards, including 28 lands. Sideboard, Maybeboard and excluded categories are
omitted; no cards or land counts were changed.

Each of the four previously saved opponents plays ten games against this deck,
five starting first and five second. Each player has a maximum of ten turns.
Seeds are 5189995–5190034, with frozen policies. Games stop early on a win.
Unfinished games are turn-limit outcomes, not draws, losses or life-total wins.

| Opponent | Ellivere wins | Ellivere losses | Turn limit | Wins / all 10 games |
| --- | ---: | ---: | ---: | ---: |
| Budget Deck (Kolodin) | 0 | 4 | 6 | 0% |
| faeries (Obyra) | 0 | 2 | 8 | 0% |
| Garbo Gobbos (Zurgo) | 0 | 6 | 4 | 0% |
| squirrels (Chatterfang) | 0 | 0 | 10 | 0% |
| Total | 0 | 12 | 28 | 0% |

These numbers describe this incomplete-rules diagnostic, not the real deck's
strength. Only 33 of Ellivere's 100 cards are currently playable by the engine;
its commander and 66 main-deck cards remain unsupported. Opponent coverage is
62/100 for Budget, 46/100 for faeries, 56/100 for Garbo Gobbos and 34/100 for
squirrels. Chatterfang is also unsupported. Unsupported cards were retained
and flagged, never replaced or treated as blank playable cards. Results do
not update learning or production policies.

There were zero runtime questions/pauses and 257 distinct unsupported card
program questions across the five decks, of which 67 occur in Ellivere's deck.
Zero runtime questions means the engine safely skipped known unsupported
programs; it does not mean complete rules coverage. Questions are deduplicated
by card identity and rules text and retain all deck occurrences. The encounter
list records known unsupported cards left in hand/discarded at game end plus
unsupported commanders; it does not claim a complete history of every card
seen via scry or other library effects.

Initial priorities by encounter-game count in the focal deck:

| Card | Games flagged |
| --- | ---: |
| Ellivere of the Wild Court | 40 |
| Sixth Sense | 12 |
| Spirit Link | 12 |
| Griffin Aerie | 10 |
| Nyx Herald | 10 |
| Path to Exile | 10 |
| Transcendent Envoy | 10 |

`summary.json` retains every game's seed, seating, outcome, life totals and
coverage. `questions.json` retains Oracle instructions, blocking questions,
deck membership and encounter-game IDs. `replays.json.gz` contains all forty
packed public replays and can be decoded with `gzip` and `json`; replay data
does not expose private hands/library order.

Reproduce from repository root:

```sh
python training/gauntlet.py \
  --focal training/decks/5189995-enchantments.json \
  --opponents training/decks/14850373-budget-deck.json \
    training/decks/27521806-faeries.json \
    training/decks/5254666-garbo-gobbos.json \
    training/decks/8321184-squirrels.json \
  --games 10 --turns 10 --seed 5189995 \
  --out training/reports/enchantments-gauntlet
```
