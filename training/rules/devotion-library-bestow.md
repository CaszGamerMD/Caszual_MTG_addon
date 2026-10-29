# Devotion, filtered library entry, and Bestow

This diagnostic rules increment enables all printed abilities on three more cards from the original queue through shared parsers. It does not add card-name behavior branches. Nine original cards remain completely blocked; Goblin Chainwhirler still lacks planeswalker loyalty damage. These are simulator changes, not live Minecraft golem integration or evidence of learned strategy.

## Devotion and mana-costed token abilities

Heliod, God of the Sun composes indestructible, a devotion threshold, an other-creature vigilance grant, and a mana-costed enchantment-creature-token instruction. Devotion counts colored symbols in controlled permanents' printed mana costs, including the God itself. It does not count colors, production text, activation costs, or opponents' permanents. Hybrid and Phyrexian symbols containing the selected color contribute one each. The creature-type condition is recalculated for targeting, attack/block eligibility, damage, death checks, and entry triggers. Losing creature type removes creature attachments without making the God leave the battlefield.

The generic token activation pays its printed colored/generic cost, enters the stack, and retains the activating player's priority. It can be used on the opponent's turn with priority and does not require the permanent to be a creature or to tap. Removing its source does not cancel the queued ability. Created tokens retain their enchantment/creature types, color, subtype, power and toughness, and have no mana cost. The policy sees affordable activations in main-phase and priority decisions. Free or unparsed activation text is rejected rather than risking an unbounded action loop.

## Reveal/filter and simultaneous entry

Muxus, Goblin Grandee composes a fixed-number reveal/filter instruction with a subtype-count attack bonus. Its reveal uses printed creature types, subtype, and printed mana value. All matching cards enter together, so entering watchers see the other entrants. Nonmatching revealed cards are put on the bottom in a seeded random order. Public logs show revealed card identities and which cards entered; no unexposed library identities or bottom order are added to observations. A short or empty library simply reveals the available cards and does not constitute a failed draw.

If a qualifying card has unknown mana value or unsupported rules, the diagnostic flags a runtime question before moving the revealed batch. It does not silently omit the qualifying creature, discard its abilities, or continue an invented game. Split, transforming, modal, and other non-normal card layouts remain conservative/unknown for this filter. The attack bonus counts other controlled permanents of the parsed subtype on resolution, applies only to its surviving source, and expires at cleanup. A departed source does not receive a bonus.

## Bestow and attachment transitions

Hopeful Eidolon compiles with a keyword-only creature mode, alternate Bestow cost, and a fixed enchanted-creature bonus/keyword grant. Both casting modes are offered. The Bestow spell is a noncreature Aura on the stack, including for creature/noncreature counterspell filters. If its target is illegal when it resolves, it resolves as an enchantment creature instead. Successful Aura entry does not falsely trigger creature-entry watchers.

When its host leaves or stops being a creature, Bestow ends and the same permanent becomes a creature without leaving/reentering, resetting counters, changing control, or resetting how long it has been controlled. It does not reattach later. Its normal mana cost and mana value remain unchanged by the alternate cost. Simultaneous sweeps use the pre-sweep creature types, so a bestowed Eidolon is not counted as a dying creature in that batch. Additional Bestow triggers, Flash casting, arbitrary attachment restrictions, protection/ward, copying and full type-changing layers remain outside this strict grammar.

## Validation

Focused tests exercise real card text, unfamiliar names/amounts/colors/subtypes, unsupported trailing text, payment and priority, source departure, devotion at entry, simultaneous entry watchers, empty libraries, unknown selected cards, Bestow target loss, attachment termination, and simultaneous sweeps. All 182 tests pass. Six distinct deck pairings completed ten turns per player with no runtime questions; five Heliod activations occurred. Muxus and Bestow branches were exercised by focused tests rather than these randomized games. Full-suite and real-deck replay summaries are recorded in `training/examples/devotion-library-bestow.json`.

Rules references: Wizards Theros release notes (devotion, Gods and Bestow), https://magic.wizards.com/en/news/feature/release-notes-2013-09-16 ; Comprehensive Rules (mana value, entry triggers and simultaneous events), https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf . Global simulator limits, including one attacker/blocker, still apply.
