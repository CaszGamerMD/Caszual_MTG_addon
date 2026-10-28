# Original 23-card work queue

Three resolved through reusable parsing: Honor of the Pure (capitalized color selector), Radiant Summit (generic two-basic-land condition and printed mana pair), Empty the Warrens (whole-text fixed-token sorcery plus storm).

| Card | Status / required mechanics |
|---|---|
| Akroma's Memorial | Protection, combined keyword grants, artifact static effects |
| Basilisk Collar | Equip costs, attachment targets, granted abilities |
| Brightfield Glider | Implemented: generic saddled attack condition and temporary stats/keywords |
| Cabal Slaver | Implemented: generic subtype combat-damage filtering and deterministic legal discard |
| Captain's Claws | Equipment and tapped attacking token placement |
| Cloudspire Coordinator | Turn history, variable activated token creation, crew/saddle contribution replacement |
| Empty the Warrens | Implemented in diagnostic simulator |
| Ephemerate | Instant priority, exile/return object identity, rebound |
| Flowering of the White Tree | Legendary selectors and ward payments |
| Goblin Chainwhirler | Simultaneous creature damage, marked damage and state-based actions |
| Haazda Marshal | Multiple attackers and attack-group conditions |
| Heliod, God of the Sun | Devotion, conditional creature type, activated token creation |
| Honor of the Pure | Implemented in diagnostic simulator |
| Hopeful Eidolon | Bestow and Aura attachment/type transitions |
| Krenko, Tin Street Kingpin | Sequential attack effects, counters then last-current power token count |
| Lifelink | Aura targeting and attached ability grants |
| Lumen-Class Frigate | Station activation and counter thresholds |
| Muxus, Goblin Grandee | Library reveal/filter, mana value, multiple entries, temporary attack stats |
| Radiant Summit | Implemented in diagnostic simulator |
| Ruinous Ultimatum | Simultaneous destruction, indestructible and full death/SBA processing |
| Shadowspear | Equipment, activated ability removal and duration |
| Skyknight Vanguard | Tapped attacking tokens and multiple-attacker combat |
| Untethered Express | Implemented: composable crew plus generic attack-triggered self counters |

Validation: 114 tests pass. Seed 1142 rerun increased spells cast from 3 to 4 and reduced original encountered unsupported cards from 23 to 20. No runtime questions. See `training/examples/questions-23-after.json`. Remaining cards reject whole-card execution; no partial abilities are silently enabled.

Storm support is limited to fixed-token sorceries without targets or other rules. Copies resolve separately before the original and finish each token batch before entry triggers. Copies are not cast and do not increase later storm counts. Full priority/counterspell interaction remains unavailable.

Reference: https://magic.wizards.com/en/news/feature/modern-horizons-2-release-notes-2021-06-04

Attack follow-up: 116 tests cover these two cards, unfamiliar names and amounts, unsaddled non-triggering, persistent counters, temporary flying/stat cleanup, and simulator state roundtrips. Seventeen original cards remain blocked; this is not complete Magic support.

Combat-damage follow-up: generic subtype watchers discard only after positive player combat damage. The damaged player chooses their last card deterministically, without a hidden-hand observation by the attacking AI. Empty hands do nothing. Damage and death triggers use controller ordering together; first/double-strike interleaving remains a blocking question. 117 tests cover normal damage and zero damage in addition to prior regressions.
