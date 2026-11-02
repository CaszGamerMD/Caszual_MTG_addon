# MTG Golem — Goblins and Elves completion, fourth four-cycle pass (2026-11-02)

Scope: independent seven-deck **standalone diagnostic Oracle parser**, branch
`experiment/commander-ai-golem`, starting local commit `9c71404`. No Minecraft
mod changes. The parser's safety gate remains **`learningEligible=false`**.

## Seven-deck coverage (100 saved slots each)

Audited all seven JSON teaching decks at baseline and after each complete
grammar/runtime/test cycle. A recognized slot is *diagnostic parser coverage*,
not proof of Commander game legality.

| Cycle | Complete, name-independent Oracle family | Motivating card(s) | Recognized slots | Unique unsupported names |
|---|---|---|---:|---:|
| Baseline | Published checkpoint from prior pass | — | **592/700** | 105 |
| 1 | Equipped creature gains menace/mobilize X equal to its power; tapped attacking Warriors and delayed sacrifice | Infantry Shield (Mono Red) | **593/700** | 104 |
| 2 | Granted mana-plus-`{Q}` untap activated ability, cost and temporary P/T | Umbral Mantle (Elves, squirrels) | **595/700** | 103 |
| 3 | Aura ETB draw; loses abilities; creature type/color and base P/T set by active Aura | Kenrith's Transformation (Elves) | **596/700** | 102 |
| 4 | Equipment scales by creatures with base power **or** toughness 1; optional ETB tribe attach | Sword of the Squeak (Mono Red) | **597/700** | 101 |

Current decks: **Lupitas elves 94/100**, **Mono Red Gobs 89/100**,
Budget Deck 79/100, faeries 71/100, Getting Wild with Enchantments 100/100,
Garbo Gobbos 100/100, squirrels 64/100. There were no losses among previously
recognized slots. The two-card-slot gain for Umbral Mantle is one unique
Oracle card appearing in two different saved decks.

## Rules semantics and proof of generalized parsing

- **Mobilize Equipment:** A complete two-line Equipment grammar with an
  equipped-creature keyword grant and a parameterized Equip mana cost. Each
  declared attacker produces one trigger for each attached source; the Warrior
  count uses the attacker's *live* power at resolution or its last-known power
  if it has left. Creates tapped/attacking **red 1/1 Warriors** and schedules
  their exact object IDs for sacrifice at the next end step; sacrifices use
  the stack and normal creature-death processing. Removing Equipment after
  triggering does not erase the pending ability.
- **Untap Equipment:** Complete grammar for a granted `{mana}, {Q}` P/T boost.
  The equipped creature's controller owns and pays the activation, subject
  to summoning sickness and available mana. The host must be tapped and
  untaps **as a cost** before a stack frame exists. The pump resolves for
  that same creature incarnation even if Equipment has left, then expires
  during cleanup. Novel names, costs and boost amounts were tested.
- **Creature-transforming Aura:** Complete three-line grammar for `Enchant
  creature`, independent ETB `draw a card`, and a change to a configurable
  color, subtype and base P/T with all abilities lost. The draw trigger goes
  onto the stack and survives source departure. Battlefield snapshots apply
  the type/color/base-stat change continuously and suppress printed keywords,
  static, triggered and activated programs until Aura departure; the printed
  definition remains intact in every zone. Later Equipment grants are
  timestamped separately and counters/equipment bonuses remain effective.
  Detachment restores printed characteristics without altering the Card.
- **Base-one Equipment:** Complete three-line grammar parameterizes the
  per-creature +P/+T, the list of entry-trigger creature types and Equip cost.
  It counts each *controlled creature* whose effective **base** power or
  toughness equals 1, once even if both equal 1; +1/+1 counters do not change
  the count. Eligible tribal entry emits an optional trigger. At resolution
  the creature and source must still be present; the controller may decline
  via the simulator decision hook. Auto-attaching changes the bonus live.
- All four grammars consume the entire post-reminder Oracle text and refuse
  unsupported extra clauses and wrong types. No card-name-specific acceptance
  shortcuts were added.

## Verification

- Focused suite:
  `python3 -m unittest discover -s training/tests -p test_deck_completion_wave4.py -q`:
  **8/8 passed**. Each family has two tests: real saved card and interaction,
  plus renamed or parameterized examples and fail-closed unknown text.
- `training/diagnostic_coverage.py` and `training/question_batches.py --decks
  training/decks/*.json --focal-id 5189995 --out
  training/reports/question-batches-current.json` were regenerated after each
  family. Final inventory: **597/700**, 101 unique unresolved names, no
  previously recognized cards lost, `learningEligible=false`.
- First full `training/tests` regression: **1,331 tests in 678.243 seconds,
  seven failures, one skip**. Six match the prior checkpoint exactly (five
  planeswalker-damage tests and one real-deck runtime-question report test).
  The seventh revealed that a new controller restriction accidentally affected
  an older Equipment that can auto-attach to an opposing creature. The two
  trigger families are now differentiated by the `requireOwn` event flag;
  `test_granted_equipment_abilities.py` is **5/5 passing**, including the exact
  failing scenario. The final full-suite rerun on the repaired source:
  **1,331 tests in 671.235 seconds; six failures, one skip, zero new failures**.
  Its six failing methods are exactly the six from the prior published pass.

## Remaining completion queue (next steps)

- **Mono-Red (11):** Squee, Dubious Monarch; Fortune Thief; Howlsquad Heavy;
  Sword of Hearth and Home; Sword of Hours; Sword of Truth and Justice;
  Mister Gutsy; Raubahn, Bull of Ala Mhigo; Armory Automaton;
  Rhuk, Hexgold Nabber; Dissection Tools.
- **Elves (6):** Mosswort Bridge; The Great Henge;
  Growing Rites of Itlimoc // Itlimoc, Cradle of the Sun; Bow of Nylea;
  Genesis Wave; Sword of Once and Future.

Next candidate families: **Squee's self-graveyard alternative cast cost** on
Mono-Red, and **The Great Henge's greatest-power spell reduction, tap mana/life,
and nontoken entry counters/draw** on Elves. Both need more runtime than lexical
recognition. The parser is a two-player diagnostic; multiplayer targeting,
replacement dependencies and the still-unsupported Oracle programs block
production Commander training. Do not turn on self-play training from this
coverage report.
