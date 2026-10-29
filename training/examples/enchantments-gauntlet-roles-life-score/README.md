# Ellivere: Roles and life-score gauntlet

Future gauntlets use remaining life total as the score after each player has
completed ten turns. The higher score wins; equal scores are ties. Normal game
wins or draws reached before the limit take precedence, including commander
damage wins at positive life. Rules-blocked games never receive score wins.
`turnLimit` counts games adjudicated at the limit and overlaps wins/losses/ties.
Those outcome categories plus blocked games sum to the game count.

## Shared card programs added

| Card | Handling |
| --- | --- |
| Ellivere of the Wild Court | Entry/attack triggers target another controlled creature and create a Virtuous Role on resolution. Each enchanted controlled creature dealing combat damage generates a separate draw trigger. |
| Sixth Sense | The Aura grants the enchanted creature an optional combat-damage draw ability. The creature's controller controls it. |
| All That Glitters | Count controlled artifacts and enchantments, counting each permanent once even if it has both types. |
| Ethereal Armor | Count controlled enchantments dynamically, including itself; grant first strike. |
| Helm of the Gods | Equip and dynamic enchantment-count power/toughness bonus. Equipment alone does not make a creature enchanted. |

These are whole-program grammars. Unknown names with the same instructions
compile; unsupported trailing instructions reject the card. Virtuous is a
predefined token specification, not a handler dispatched on Ellivere's name.
Other Role types, arbitrary Aura triggers and replacement/continuous-effect
dependencies are not enabled by this change. Keen Sense remains unsupported;
its all-damage trigger is different from Sixth Sense's granted combat ability.

Role triggers choose legal targets when placed on the stack and recheck them
on resolution. An unattached/illegal-target trigger creates no Role. Roles
enter attached, are noncreature colorless Enchantment — Aura Role tokens, and
count themselves toward their own bonus. The newest Role of one controller
replaces older Roles of that controller on the same host as a state-based
action. Different controllers' Roles may coexist. Leaving/blinking the host
removes the Aura tokens. A queued trigger can survive its source leaving.

Combat draw discovery uses the battlefield at damage time, including a source
that dies in that damage step. Each double-strike damage step is separate.
Optional draws expose accept/decline choices to the frozen policy; an empty
library is declined by default. Mandatory empty-library draws still lose.

## Forty-game verification

The same focal snapshot, four opponents, seeds 5189995–5190034 and ten turns
per player are retained, with five first starts per side in each matchup.

| Opponent | Wins | Losses | Ties | Win rate |
| --- | ---: | ---: | ---: | ---: |
| Budget Deck / Kolodin | 3 | 7 | 0 | 30% |
| faeries / Obyra | 3 | 7 | 0 | 30% |
| Garbo Gobbos / Zurgo | 4 | 5 | 1 | 40% |
| squirrels / Chatterfang | 8 | 2 | 0 | 80% |
| Total | 18 | 21 | 1 | 45% |

Twenty games reached the score limit. The other twenty ended under ordinary
game rules. Zero runtime questions/pauses occurred. Every new card was cast:
Ellivere 31 casts, Sixth Sense 6, All That Glitters 4, Ethereal Armor 4, and Helm
of the Gods 6. The batch recorded 49 Role creations and 66 draw-trigger
resolutions, alongside focused rule fixtures.

The focal deck's supported count is 38/100 (including its commander), leaving
62 unsupported card programs. Across the five decks, 252 distinct unsupported
program questions remain. The old gauntlet remains an untouched historical
snapshot; its results use different score rules and cannot be directly
compared as a measure of rules improvement or learning.

`summary.json` includes score outcomes, normal engine results, seating, seeds,
and exact engine source hashes. `questions.json` retains the reduced queue.
`replays.json.gz` retains all forty packed public replays plus their score
adjudications. The base commit plus source hashes identify changes tested from
a working tree before the reporting commit. All results remain diagnostic and
ineligible for learning/production; live Minecraft integration is unchanged.

Primary reference: Wizards' [Wilds of Eldraine release notes](https://magic.wizards.com/en/news/feature/wilds-of-eldraine-release-notes)
define Virtuous Roles, same-controller Role replacement, and different-controller
Role coexistence.
