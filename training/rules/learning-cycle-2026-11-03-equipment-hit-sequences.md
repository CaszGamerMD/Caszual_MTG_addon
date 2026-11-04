# Learning cycle — composable Equipment combat-hit sequences

## Newly supported cards

- **Sword of Truth and Justice**: on positive combat damage to a player, the trigger chooses a creature you control during resolution, puts a +1/+1 counter on it, then proliferates. The diagnostic choice proliferates modeled +1/+1 counters on permanents and poison counters on players; proliferate permits choosing any number, so other counter families can be left unselected.
- **Sword of Hearth and Home**: on positive combat damage to a player, the trigger may target up to one creature you own, including one currently controlled by an opponent. If the chosen target is still legal on resolution, it is exiled, then a basic land is searched for; the creature returns under the trigger controller's control and the land enters untapped. If the optional target is declined, the basic-land search still resolves.

## Shared implementation

Both cards compose through the existing Equipment combat-hit stack program. The new operations are generic clause-level instructions, not name checks. The parser lowercases captured clauses so capitalized sentence continuations such as “Put both cards…” compile consistently. Owned-creature targets record object identity and are rechecked at resolution; ward triggers are queued when applicable. Token ownership is recorded when tokens enter the battlefield so “you own” does not collapse into “you control.”

## Focused validation

- Sword of Truth and Justice: 4 focused tests passed locally.
- Sword of Hearth and Home: 4 focused tests passed locally, covering real and renamed Oracle text, unknown trailing text rejection, an owned creature controlled by an opponent, target invalidation, untapped land entry, and declining the optional target.
- Full regression and branch-wide deck coverage are still being checked on the published branch; no training-eligibility gate is changed.
