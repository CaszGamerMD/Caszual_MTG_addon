# Menace, combined grants and saddled attack tokens

The original 23-card queue was already cleared in `d42e984`. This follow-up
adds full saved-text diagnostic support for four further submitted cards through
shared grammar, without dispatching on their names:

| Card | Shared handling |
| --- | --- |
| Goblin War Drums | Controlled creatures gain menace; blocker declarations require zero or at least two legal blockers. |
| True Conviction | Multiple keywords joined by `and` compose as independent continuous grants. Double strike and lifelink apply in both combat damage steps. |
| Quilled Charger | Saddled attack boost grants temporary menace through a stack trigger, then expires at cleanup. |
| Bridled Bighorn | Attacking while saddled queues ordinary creature token creation. The Sheep enters normally rather than attacking. |

The blocker policy offers legal pairs for menace and never offers a single
blocker against it. Explicit declarations still accept larger legal groups.
Each blocker must separately satisfy flying, protection and other existing
restrictions, and cannot be reused. Menace is checked at declaration; removing
blockers afterward does not make the attacker unblocked. Removing a source of
granted menace before declaration removes that restriction.

The saddled condition is checked when the creature attacks. Once triggered,
the token ability resolves even if its source leaves or loses saddled status.
Unsupported trailing instructions reject the entire card program. Renamed
fixtures verify that each rule is independent of the four printed names.

Validation includes eleven focused tests. The regression suite also retains
unknown-text rejection on an altered Bighorn, and now arranges the actual
Bitterbloom/Obyra cards directly so policy changes cannot skip its asserted
interaction. Six non-mirror real-deck diagnostics (seeds 1442–1447, up to ten
turns per player) completed or reached a win without runtime questions: 55 land
plays and 33 spells. None of the four new cards was cast in that random batch;
their mechanics are verified by the focused fixtures.

These diagnostics remain ineligible for learning and production. Other cards,
full multiplayer Commander, arbitrary blocking restrictions and requirements,
and live Minecraft integration remain outside this change. The older Java
combat heuristic is unchanged. The policy samples legal groups rather than
searching every possible combat strategy.

Saved batch summary: `training/examples/menace-mounts-summary.json`.

Primary rules reference: Wizards' [Magic Origins release notes](https://magic.wizards.com/en/news/feature/magic-origins-release-notes-2015-07-08)
describe menace's blocking restriction and persistence of an established block.
