# Priority-stack foundation

The diagnostic now has a two-player LIFO stack with unique object IDs, priority ownership, consecutive passes, and one-object resolution. New actions reset pass counts. After resolution the active player regains priority. Two passes on an empty stack return an advance signal. A counter primitive removes a specific stack object without resolving it. Public stack metadata excludes effect payloads and private cards.

Supported entry/upkeep/death effects routed through the common trigger resolver are placed in APNAP controller order. Within a controller's batch the existing deterministic discovery resolution order is retained. Newly generated entry triggers wait until their parent effect finishes; they then sit above older pending objects. Mana abilities still bypass the stack. The game logs stack placement, passes, and resolution. Automated play passes automatically; manual-priority tests can hold resolution and alter the public game state. Turn stepping refuses to skip pending manual stack objects.

Krenko-style counter-then-power-token effects now defer both operations until resolution. A live source gets the counter first and its resulting current power determines the token count. If it leaves, departure records last-known power and resolution creates tokens without adding a counter to the departed source. Repeated/full and short Oracle self references still select no name-specific behavior.

Validation: 122 tests pass, covering LIFO order, two-pass requirements, wrong-player rejection, reset after a response, a countered object, empty-stack advance, APNAP placement, deferred Krenko resolution, and source removal with last-known power. Seed 1142 completed without runtime questions and recorded two stack placements, four priority passes, and two resolutions. Summary: `training/examples/stack-1142.json`.

## Still pending

This is an ability-stack foundation, not a complete stack implementation. Casting ordinary spells still resolves through the existing direct path; actual instant response actions, target validation, counterspell cards, full state-based-action loops, and first/double-strike damage windows remain unavailable. Some legacy attack triggers still execute immediately. The counter primitive is tested engine infrastructure, not a playable counterspell. Manual mode is a test/API mode and is not yet exposed as policy response choices. Live Minecraft actions are unchanged.

Rules reference: Wizards Comprehensive Rules 117.3b, 117.4, 405 and 603: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf

## Spell-stack integration

Casting now pays costs and moves the original card from hand/command zone onto the stack. It reaches the battlefield or graveyard only on resolution. Card conservation includes stacked originals and the currently resolving original; copies do not count as physical cards. The chosen X remains in the stack payload. Creature entry triggers are queued above older stack objects after the creature resolves. Storm copies are separate resolving spell objects and are not cast.

Supported untargeted draw/life instants preserve Instant metadata at import. The priority API exposes only the priority holder's own hand, public state, legal affordable instant responses, and passing. Wrong-player and sorcery responses reject before payment. `priority_observation` and `act_priority` expose those choices for a controller; automatic games still pass by default, so this is not a trained instant-response policy. Manual API tests cast an opponent instant over a sorcery and resolve them separately in LIFO order, with correct mana, life, graveyard and card conservation.

Validation: 124 tests pass; seed 1142 replay completed without runtime questions. See `training/examples/spell-stack-1142.json`. Still missing: targeted response spells, counterspell cards, flash casting for all supported permanents, comprehensive state-based actions, and full combat priority windows. Storm copy creation is queued directly at casting rather than through a separately counterable storm trigger. This remains a diagnostic simulator; live Minecraft actions are unchanged.

## Targeted counterspell responses

Whole-text Instant grammars now recognize “Counter target spell.”, “Counter target creature spell.”, and “Counter target noncreature spell.” Each legal response names a stable stack-object ID. Abilities are excluded from spell targets, and unanimated Vehicles are noncreature spells on the stack. Timing, payment and target checks happen before the card moves or mana is spent. Resolution rechecks the same ID; if it is gone, the counterspell has no effect and goes to the graveyard. Countered originals go to their controller/owner's graveyard (ownership changes are not supported); commanders use the diagnostic's automatic command-zone choice. Countered copies cease without adding a physical card. None of the countered spell's effects execute.

Tests cover an ordinary counter, filtered target rejection without payment, target disappearance, strict rejection of additional clauses, and countering a counterspell so the original resolves. Automated games still pass priority by default; this adds legal responses through the existing priority API. Conditional tax counters, exile replacements, uncounterability, ability counters and multi-target spells are not enabled. No partially parsed counterspell is allowed.

Rules references: Wizards Comprehensive Rules, countering and illegal targets:
https://media.wizards.com/2025/downloads/MagicCompRules%2020250919.pdf
https://media.wizards.com/2025/downloads/MagicCompRules%2020251114.pdf

## Automated priority decisions

The automatic stack drain now asks the priority holder's frozen policy to choose among legal responses and passing, through the same own-hand/public-state Observation boundary. It records choices and target IDs. A reentrancy guard keeps response casting from recursively draining the stack. Response selection resets passes through normal cast handling; after resolution priority returns to the active player.

Baseline response features give opposing spell targets positive value and friendly spell targets a strong negative value, so the default policy counters an opponent rather than its own spell. Supported draw/life instants use their existing features and mana cost; known self-decking draw responses are excluded. This is a simple deterministic heuristic, not strategy learned from real games and not a prediction of whether every opponent spell should be countered. Priority-pass decisions carry complete zero feature vectors so classroom training aggregation remains valid.

Validation: 131 tests, including automatic counterspell use, an automatic two-player counter exchange that saves the original spell, and earlier priority/conservation regressions. Six distinct real-deck pairings at seeds 1242–1247 completed without runtime questions (four ten-turn windows and two earlier wins). No supported instant responses occurred in that random batch; focused tests provide the direct behavioral evidence. Summary: `training/examples/responses-1242.json`. Targeted removal, blink, equipment, and the original unresolved card queue remain unfinished.
