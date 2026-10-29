# Land and attachment language batch

Ten formerly unsupported cards now compile through shared Oracle rules:

- Blossoming Sands and Graypelt Refuge: tapped entry and queued lifegain.
- Temple of Plenty: tapped entry and queued scry (existing legal keep-all policy).
- Drowned Catacomb: basic land type checks accept both “a” and “an”.
- Fortified Village and Auntie's Hovel: optional subtype reveal from the controller's own hand; revealed card stays there. Current policy reveals the first legal card.
- Overgrown Tomb: optional life payment before entry; current policy declines if payment would leave zero life. Payment is neither damage nor life gain.
- Golgari Rot Farm: tapped entry, two mana from one tap, and a non-targeting return-land trigger. Choice occurs on resolution, returns to the owner, and can return the source itself.
- Sword of Vengeance: keyword lists with or without an Oxford comma.
- Darksteel Plate: source indestructibility remains separate from the equipped-creature grant.

Lands participate in the shared battlefield event kernel. Playing a land queues entry triggers but is not a cast. Simple land programs consume every clause; unsupported clauses still reject the complete card. Tests cover unfamiliar names, changed numeric/color parameters, replacements, timing, ownership, optional choices, and mana output.

Forty games: ten per saved opponent, alternating starting seats, seeds 5189995–5190034, ten turns per player. Higher remaining life wins at the turn limit; equal life ties; ordinary outcomes take precedence.

Result: 26 wins, 14 losses, 0 ties (65% wins). Thirteen games reached the score limit; no games blocked and no runtime questions. Unique unresolved cards across five decks fell from 209 to 199. Focal enchantment coverage rose from 65 to 69 of 100 cards (31 unresolved).

These are incomplete-rules diagnostic results, not full Commander deck-strength measurements. The retained summary includes exact simulation source hashes. The upstream public replay-state fix at 20d6397 was integrated after this captured run; existing captured replays use the earlier serializer. This reporting-only merge does not change gameplay rules.

Validation: all 483 unit/integration tests passed, including 13 focused land and attachment cases.
