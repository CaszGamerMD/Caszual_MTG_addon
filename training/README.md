# Commander self-play deck intake

## Imported deck

- Source: https://archidekt.com/decks/14850373/budget_deck
- Commander: Kolodin, Triumph Caster (one card).
- Main deck: 99 cards, retaining quantities and double-faced card identities.
- Excluded: 12 cards tagged Maybeboard; exclusion overrides other included categories.
- The JSON fixture includes the source's Oracle data for rules-coverage work. It is an intake snapshot, not a deck certified playable by the current pilot.
- The text fixture contains only the commander and main deck.

## Pending deck

https://archidekt.com/decks/5254666/garbo_gobbos returned HTTP 404 for both the page and deck API on October 27, 2026. No commander or cards were inferred from the deck name. An accessible link or exported list is needed.

## Rules required before training this matchup

Kolodin's deck requires more than passive creature combat: Vehicles and crew, Mounts and saddle, temporary type changes and haste grants, enters/attack/end-step triggers, token creation/copying, counters, equipment and Auras, continuous team buffs, lifegain conditions, targeted removal/exile, blink, scry, transforming/modal double-faced cards, and mana sources producing multiple mana.

Examples from the imported snapshot:
- Kolodin grants haste to Mounts/Vehicles, saddles entering Mounts, and animates entering Vehicles until end of turn.
- Fortune, Loyal Steed combines scry, saddle and delayed combat-end blink.
- Ocelot Pride combines first strike/lifelink with ascend and conditional end-step token creation/copying.
- True Conviction grants double strike/lifelink to the team.
- Throne of the God-Pharaoh causes end-step life loss based on tapped creatures.

Do not run training that silently drops these effects. A completed legal-match engine and coverage audit are prerequisites to meaningful self-play.

## Intended learning boundary

Two independent agents receive separate observations: their own hand, legally known information and public zones. Opposing hands and unknown library order remain hidden. Both use the same frozen policy checkpoint during a match, with independent private decision state. Post-match learning may update a shared persistent policy. Saved improvements must be evaluated against prior checkpoints across fresh shuffles and both starting seats before promotion. These are requirements; the self-play runner and learning system are not implemented by this intake.
