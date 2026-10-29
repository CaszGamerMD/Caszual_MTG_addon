# Legendary selectors, ward, temporary ability loss, and loyalty damage

This increment enables Flowering of the White Tree and Shadowspear through generic parsers and completes the previously missing planeswalker portion of Goblin Chainwhirler's damage instruction. Seven cards in the original 23-card queue remain completely blocked. This is diagnostic simulator support; full Magic rules, learned strategy and live Minecraft entity integration remain unfinished.

## Legendary bonuses and ward

Selectors distinguish legendary and nonlegendary creatures and retain controller/creature restrictions. Flowering grants the appropriate disjoint bonuses and a separate mana ward instance to each legendary creature. Intrinsic `Ward {cost}` also compiles. Unsupported extra text and nonmana ward costs reject the whole program.

When a supported hostile spell targets a warded creature, each ward instance becomes a separate stack object above that spell. The caster retains priority. Ward payments happen when the ward trigger resolves, using the current mana pool and untapped sources. The current deterministic policy pays if possible; otherwise ward counters the targeted stack object. A countered physical spell goes to its owner's graveyard or chosen commander destination, while a countered ability does not move its source. An absent original stack object does not consume payment. Removing the ward-granting permanent does not cancel an already triggered ward ability. Friendly targeting and untargeted effects do not trigger ward.

The existing targeted spell paths are connected. A generic stack-target helper also supports ability frames, but future hostile targeted activated/triggered abilities must explicitly call it when implemented. Multiple-target spells, retargeting and uncounterable spells remain unsupported. The removal heuristic includes currently visible ward costs and avoids knowingly spending a spell when its ward cannot be paid; this is a heuristic, not learned strategy. Public permanent state exposes ward costs.

## Shadowspear and ability ordering

The equipment grammar composes fixed bonuses, keyword grants, equip cost and a paid instruction removing hexproof/indestructible from opposing permanents until end of turn. Activation is available with priority, requires no tap or attachment, pays its mana cost immediately, and resolves independently of its source. Opposing permanents are selected on resolution, not activation; the effect does not target and does not trigger ward. The automated policy gives redundant queued activations low value rather than repeatedly spending all mana on the same pending removal.

Permanent entry, attachment, temporary grants and ability-loss effects carry timestamps through simulator/kernel roundtrips. Earlier printed/static/attachment grants are suppressed by a later loss. A later grant can restore an ability; a new permanent does not inherit the earlier loss. Reattaching equipment gives its grants a new timestamp, while resolving equip onto the same unchanged host does not. Cleanup expires losses and temporary grants. This handles the supported keyword effects, not the complete continuous-effect layer/dependency system.

Hexproof is now represented as a public noncombat ability. Enemy targeting is checked both when casting and when resolving supported removal, Aura and Bestow spells. Own spells can target their controller's hexproof creatures. Untargeted damage and sweeps ignore hexproof. Hexproof is not passed to the older Java combat subset as an invented combat keyword. Removing indestructible also updates combat characteristics and triggers state-based checks against damage already marked.

## Planeswalker damage

Planeswalker objects carry printed starting loyalty and current loyalty independently of creature +1/+1 counters. Board damage applies life loss, creature damage marks and planeswalker loyalty removal as appropriate, counting each affected permanent once for damage/lifelink even if it has both types. A creature planeswalker receives both damage marks and loyalty loss from that one damage event. Loyalty cannot fall below zero.

Zero-loyalty planeswalkers leave during state-based checks even with indestructible. Noncreature planeswalkers do not produce creature-death triggers. Missing/variable loyalty and unparsed planeswalker abilities remain blocked. The focused Chainwhirler tests use the actual Chainwhirler Oracle text against explicit planeswalker fixtures; full planeswalker loyalty activations, combat attacks against planeswalkers, animation/type layers, prevention, replacement effects and arbitrary real planeswalker cards are not enabled by this infrastructure. Creature-planeswalker combat remains outside the supported gameplay scope.

## Validation

The new focused suites cover Flowering's selectors, separate ward payments/countering, vanished source/original spell, unfamiliar names/costs, real Shadowspear, hexproof at cast and resolution, printed/static/temporary/attachment grants before and after removal, cleanup, source departure, damage already marked, Chainwhirler damage to planeswalkers, indestructible at zero loyalty, dual-type damage and lifelink, and unknown loyalty abilities.

All 202 tests pass. Six distinct real-deck pairings completed ten turns per player without runtime questions. Those randomized games did not exercise the newly added ward/payment, ability-loss or board-damage branches; the focused suites supply that coverage. Full-suite and six-pairing real-deck results are recorded in `training/examples/ward-ability-loss-loyalty.json`. Random deck play is supplementary; it need not draw/cast every new card. These matches are not training eligible, and unsupported cards outside the original queue still remain in the submitted decks.

Primary rules references:
- Ward and multiple instances: https://magic.wizards.com/en/news/feature/strixhaven-school-mages-and-commander-2021-edition-release-notes-2021-04-16
- Shadowspear, later entrants and later grants: https://magic.wizards.com/en/news/feature/teenage-mutant-ninja-turtles-release-notes
- Planeswalker damage: https://magic.wizards.com/en/news/feature/foundations-mechanics
- Dual-type planeswalker damage: https://magic.wizards.com/en/news/feature/war-spark-release-notes-2019-04-19
- State-based actions and timestamps: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf
