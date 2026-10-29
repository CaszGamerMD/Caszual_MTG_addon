# Final seven original cards: shared rules support

The original 23-card queue is now clear in the diagnostic simulator: all seven remaining cards compile their full saved Oracle instructions, including unfamiliar names with the same mechanics. Unsupported trailing instructions still reject the whole program. This does not mean the four submitted decks or the full Magic rules are completely supported.

| Card | Shared handling |
|---|---|
| Akroma's Memorial | Combined artifact keyword grants; color protection for damage, blocking, targeting and attachments |
| Captain's Claws | Equipment bonuses/equip; equipped-creature attack triggers; tapped attacking tokens |
| Cloudspire Coordinator | Entry scry; tap costs and summoning sickness; resolution-time entry history; Pilot crew/saddle contribution bonus |
| Ephemerate | Owned creature targeting; blink/new object identity; exile; one-shot rebound casting permission |
| Haazda Marshal | Simultaneous declarations; count only declared attackers; ordinary lifelink token creation |
| Lumen-Class Frigate | Sorcery-speed station activation; separate charge counters; current/last-known power; threshold anthems and creature/keyword status |
| Skyknight Vanguard | Flying plus stack-based attack-triggered tapped attacking token creation |

## Group combat and protection

Diagnostic games use simultaneous attack declarations, distinct blocker assignments, and simultaneous damage across the combat. Explicit APIs accept any legal group and multiple blockers per attacker. The policy offers selected legal groups/maps rather than doing exhaustive strategic search. It still has no access to opponents' hands or library order.

Attacking tokens join the combat but are not declared attackers and do not cause their own attack triggers. Haazda's threshold uses only the declared group. Marshal's created token enters normally and does not join combat. Tokens created after their source leaves still resolve from the stack.

Separate first-strike/double-strike damage steps re-read surviving objects and current abilities. Blocked status persists if a blocker leaves; trample can carry damage through. Damage, lifelink and deathtouch are applied simultaneously, then deaths and waiting triggers are processed. Multi-block trample assigns lethal damage before excess, with positive deathtouch assignments requiring one damage. Protection prevents damage after assignment, so it does not reduce the lethal assignment needed for trample. Commander damage uses stable physical-card identity across blinks.

Protection filters targeted spells and equipment even when their controller owns the protected creature. It forbids blockers of the protected colors, prevents their damage, and removes illegal attachments during state-based checks. It does not stop untargeted destruction. The older Java combat evaluator remains a heuristic/subset; group-combat execution handles these new interactions in Python.

Crew and saddle now pay their tap costs, enter the stack, and apply their effects only when resolving. Defensive crew decisions are offered during priority before blocker declaration, not after the window closes. Pilot bonuses are applied only when paying crew/saddle costs; they do not change combat power or the power used for station.

## Station and turn history

Spacecraft in the supported flat station layout track charge counters separately from +1/+1 counters. Frigate's threshold of two charges supplies its other-creature anthem; twelve charges enables its 3/5 creature status, flying and lifelink. Becoming a creature does not restart its control duration, and being newly cast still limits attacking unless it has haste. Station can use a fresh helper because its cost taps another creature rather than using that helper's own tap ability.

Station adds counters when its ability resolves using current helper power, or last-known power if the helper left. Negative power adds no counters. An existing noncreature helper has no power. A blinked station is a new object with zero charge counters and does not receive the old object's queued counters. This grammar does not implement all Planet/Spacecraft layouts, alternate station contributions or arbitrary additional threshold text.

Entry history records each entry's controller, subtypes and turn, including entries before Coordinator appeared. A Mount/Vehicle with both subtypes counts once. The count is evaluated at resolution. The tap ability respects summoning sickness and haste, can be used with priority on either player's turn, and resolves even after its source leaves. Pilot tokens carry a separate contribution modifier, not a printed power increase.

## Blink, ownership and rebound

Physical card identity is separate from battlefield object identity. Blink returns a fresh object with a new object ID, no counters, no marked damage and no old attachments; it also leaves combat. Old targeted spells and queued station effects cannot affect the returning object. Equipment remains unattached; ordinary Auras leave with illegal attachments; Bestow can end without changing the physical card's identity. Returned creatures go to their physical owner's control. Card conservation includes exile and resolving spells.

A token exiled this way cannot return. A successful rebound spell cast from hand is exiled rather than put in the graveyard and schedules one delayed trigger at its controller's next upkeep. The casting permission is limited to that trigger and that exiled card. A successful second cast is free and ends in the graveyard. Countering/failing the first spell does not schedule rebound; countering the delayed trigger leaves the card exiled. The deterministic policy can decline if there is no chosen legal non-token target, and there is no repeated chance on later turns. Beginning-of-upkeep triggers are snapshotted together before rebound can blink any source.

## Validation and boundaries

227 tests pass, including 25 focused tests for the seven cards and cross-rule interactions. Existing brittle seeded-game snapshots were replaced with rule assertions where group combat legitimately changed damage and game length. The Bitterbloom/Obyra replay still verifies actual life changes and token effects rather than assuming a game lasts ten turns.

Twelve real-deck diagnostic games use all four submitted decks with no mirrors. They run up to ten or twenty turns per player, stopping on a win. All complete their window or end in a win, with no runtime questions. The saved review distinguishes cards cast in random games from mechanics covered by explicit fixtures; Ephemerate's rebound cases are verified by focused tests rather than those twelve games.

Other unsupported cards in the four decks remain flagged and unplayable. These matches are not training eligible, policies remain frozen, and no live Minecraft golem behavior was changed. Full multiplayer Commander, attacks against planeswalkers/battles, all continuous-effect dependencies, arbitrary replacements/prevention, advanced combat keywords, extra combats and all card programs remain outside this diagnostic. Clearing this original queue is not a claim of full Magic compliance.

Review: `training/examples/final-seven-review.html` and `training/examples/final-seven-summary.json`.

Primary references:
- Station thresholds, power at resolution and last-known power: https://magic.wizards.com/en/news/feature/edge-of-eternities-release-notes
- Saddle, attack conditions and Aetherdrift mechanics: https://magic.wizards.com/en/news/feature/aetherdrift-release-notes
- Ephemerate, new objects, attachments and rebound: https://magic.wizards.com/en/news/feature/marvel-super-heroes-release-notes
- Combat, protection, priority and zone changes: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf
