# Original 23-card work queue

Three resolved through reusable parsing: Honor of the Pure (capitalized color selector), Radiant Summit (generic two-basic-land condition and printed mana pair), Empty the Warrens (whole-text fixed-token sorcery plus storm).

| Card | Status / required mechanics |
|---|---|
| Akroma's Memorial | Protection, combined keyword grants, artifact static effects |
| Basilisk Collar | Implemented in diagnostic: equip costs, stack targeting, deathtouch/lifelink grants |
| Brightfield Glider | Implemented: generic saddled attack condition and temporary stats/keywords |
| Cabal Slaver | Implemented: generic subtype combat-damage filtering and deterministic legal discard |
| Captain's Claws | Equipment and tapped attacking token placement |
| Cloudspire Coordinator | Turn history, variable activated token creation, crew/saddle contribution replacement |
| Empty the Warrens | Implemented in diagnostic simulator |
| Ephemerate | Instant priority, exile/return object identity, rebound |
| Flowering of the White Tree | Legendary selectors and ward payments |
| Goblin Chainwhirler | Implemented for diagnostic player/creature boards: simultaneous damage and death triggers |
| Haazda Marshal | Multiple attackers and attack-group conditions |
| Heliod, God of the Sun | Implemented in diagnostic: generic devotion, conditional creature type, vigilance, paid enchantment-creature token activation |
| Honor of the Pure | Implemented in diagnostic simulator |
| Hopeful Eidolon | Implemented in diagnostic: alternate Bestow cost, Aura stack type, grants, target-loss fallback and same-object creature transition |
| Krenko, Tin Street Kingpin | Implemented in diagnostic: counter then current-power token creation |
| Lifelink | Implemented in diagnostic: Aura targeting, lifelink grant and cleanup |
| Lumen-Class Frigate | Station activation and counter thresholds |
| Muxus, Goblin Grandee | Implemented in diagnostic: generic reveal/filter by printed type/mana value, simultaneous entry, random bottom order, resolving subtype-count attack bonus |
| Radiant Summit | Implemented in diagnostic simulator |
| Ruinous Ultimatum | Implemented in diagnostic: opponent nonland sweep, indestructible and simultaneous death-trigger discovery |
| Shadowspear | Equipment, activated ability removal and duration |
| Skyknight Vanguard | Tapped attacking tokens and multiple-attacker combat |
| Untethered Express | Implemented: composable crew plus generic attack-triggered self counters |

Validation: 114 tests pass. Seed 1142 rerun increased spells cast from 3 to 4 and reduced original encountered unsupported cards from 23 to 20. No runtime questions. See `training/examples/questions-23-after.json`. Remaining cards reject whole-card execution; no partial abilities are silently enabled.

Storm support is limited to fixed-token sorceries without targets or other rules. Copies resolve separately before the original and finish each token batch before entry triggers. Copies are not cast and do not increase later storm counts. Full priority/counterspell interaction remains unavailable.

Reference: https://magic.wizards.com/en/news/feature/modern-horizons-2-release-notes-2021-06-04

Attack follow-up: 116 tests cover these two cards, unfamiliar names and amounts, unsaddled non-triggering, persistent counters, temporary flying/stat cleanup, and simulator state roundtrips. Seventeen original cards remain blocked; this is not complete Magic support.

Combat-damage follow-up: generic subtype watchers discard only after positive player combat damage. The damaged player chooses their last card deterministically, without a hidden-hand observation by the attacking AI. Empty hands do nothing. Damage and death triggers use controller ordering together; first/double-strike interleaving remains a blocking question. 117 tests cover normal damage and zero damage in addition to prior regressions.

Power-token follow-up: the whole attack instruction composes self-counter addition with parsed token characteristics and a current-power count. Self references normalize full and Oracle short names without behavior dispatch. Tokens resolve as a batch before their entry triggers and are not declared attackers. Full response windows and source departure while a trigger is on the stack remain unavailable in this diagnostic. Focused tests cover real Krenko and an unfamiliar 2/3 flying Drake producer, prior counters, repeated attacks, and rejection of unparsed trailing text. Sixteen original cards remain blocked.

Sweep follow-up: a whole-text opponent-nonland destruction grammar now covers Ruinous Ultimatum and unfamiliar names. The single-target destroy path shares batch death discovery. Lands (including land creatures) and indestructible permanents survive; the caster’s permanents are untouched. Blood Artist sees simultaneous deaths even if it dies; Nested Shambler uses its power before a dying anthem leaves. Fifteen original cards remain blocked. Full cascading state-based actions and regeneration remain outside the current model.

Attachment follow-up: Basilisk Collar and Lifelink now compile using whole-text attachment grammars. Thirteen original cards remain blocked. Equipment with additional triggered/activated abilities, Bestow, and tapped attacking token creation are not silently enabled.

Board-damage follow-up: Goblin Chainwhirler now compiles through a generic fixed-damage trigger grammar with First strike retained. Twelve original cards remain blocked. Planeswalker objects and loyalty are not yet supported by the simulator; this is not full coverage of that portion of the card text.

## Repeated creature state-based checks

Added cascading creature deaths from lost toughness bonuses, deferred all waiting death triggers until those batches finish, and preserved ordinary-combat damage marks through the turn. This is shared rules infrastructure, not an additional completed card: 12 original cards remain completely blocked, with Goblin Chainwhirler still partial pending planeswalker loyalty damage. See `state-based-actions.md` for scope and limitations.

## Devotion, filtered library entry and Bestow

Heliod, Muxus and Hopeful Eidolon now compile all printed instructions using reusable grammar. Nine original cards remain completely blocked, plus Chainwhirler's pending planeswalker portion. Unsupported creatures revealed by Muxus produce a human-review question before the batch moves. See `devotion-library-bestow.md` for validation and explicit boundaries.
