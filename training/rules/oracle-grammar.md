# Oracle cause-and-effect parsing

`oracle_abilities.py` compiles supported Oracle paragraphs into immutable
`Trigger(event, subject, effect)` and `StaticEffect(subject, power, toughness,
count, condition)` nodes. Names are used for display and exact self-reference
normalization, never to select these behaviors.

“Whenever another Goblin you control enters, each opponent loses 3 life” becomes
an entry event, a same-controller/other-object/Goblin filter, and a lose-life
operation with amount 3. Different names, tribes and amounts use the same code.

## Supported grammar

- Entry and death events; self, other, creature, subtype and controller filters.
- Distinct damage and life-loss operations; optional controller life gain.
- Self-entry scry, with arbitrary positive amounts.
- Continuous numeric bonuses to other matching subtypes you control, bonuses
  counting matching permanents on either battlefield, and bonuses conditional
  on another creature of a specified color you control.
- Multiple supported abilities and keywords on the same card.
- Whole-text rejection when a paragraph, optional clause, intervening condition,
  unsupported effect or “one or more” trigger cannot be fully interpreted.

Obyra, Faerie Seer, Blood Artist, Zulaport Cutthroat, Impact Tremors, Briarberry
Cohort, Squirrel Mob and Squirrel Sovereign now execute through these nodes.
They are regression fixtures, not name-based dispatch cases. Review questions
show parsed ability structures alongside the original Oracle text.

## Remaining migration and limitations

Token creation, upkeep, Kolodin, Zurgo, equipment and saddle attack effects still
use legacy specialized handlers. Activated costs and arbitrary choices need
further nodes and execution support. This is a strict growing grammar, not a
complete natural-language or Magic rules engine.

Scry still keeps viewed cards in order; target-player drain chooses the opponent.
The diagnostic has no complete priority/response stack or multiplayer engine.
Unsupported first-strike/death timing pauses for a retained question. Real-deck
results remain excluded from policy training and live golem deployment.

## Verification

81 tests pass, including unfamiliar names, altered tribes/colors/amounts,
controller and type boundaries, continuous bonuses disappearing when their
conditions end, and unhandled-text rejection. Six distinct real-deck pairings
(seeds 142–147) each completed ten turns per player: 61 land plays, 20 casts and
22 trigger log entries, preserving the previous baseline. Results are in
`examples/oracle-grammar-pool-summary.json`.

## Generic standalone token instructions

Fixed-quantity sorcery instructions now compile through `parse_token_creation`
into a TokenSpec: amount, power/toughness, colors, subtypes, supported keywords
and tapped state. The simulator executes those characteristics, replacing the
former red-1/1-Goblin-only spell path. Unknown names use the same parser. Token
creation finishes its batch before entry triggers resolve. Creature tokens retain
colors/subtypes and enter fresh; tapped tokens remain tapped.

This does not yet migrate the legacy upkeep, death or self-entry token handlers.
Instant timing, X amounts, variable P/T, 0-toughness token state-based actions,
replacement effects, ward and additional instructions remain rejected or flagged.
There is no automatic flashback support. Complete-text parsing prevents a simple
creation instruction from hiding unimplemented additional abilities.

89 regression tests pass, including an unfamiliar spell creating tapped 2/3
blue-black Faerie Rogues with flying. A six-pairing real-deck batch (seed 342) is
recorded in examples/token-grammar-342.json. Five completed ten turns each; one
ended earlier under diagnostic rules. No strategic-learning claim is made.

## Entry-triggered token creation

Self-entry triggers now compose with the same TokenSpec used by standalone
spells. Goblin Instigator's name-specific handler was removed. The event kernel
queues the ability without creating tokens; resolution creates the entire batch
under the trigger controller before resolving the tokens' entry triggers. Parsed
amount, stats, colors, types, keywords and tapped state are preserved. Structured
review data serializes the token descriptor alongside trigger and subject nodes.

90 checks pass, including an unfamiliar summoner creating two tapped 3/4 blue
Drakes with flying for the nonactive player. Repeating token-entry engines and
generic death-token creation remain rejected pending proper stack/loop handling;
upkeep and last-known-power token handlers still require migration. The six
seed-442 pairings are recorded in examples/entry-token-442.json. This is continued
rules implementation, not learned strategy or complete Commander support.

## Generic upkeep triggers

The parser now recognizes “At the beginning of your upkeep” and composes it with supported effects (fixed token creation, scry, counters, opponent damage/life loss). It also recognizes mandatory “you lose N life and create …” as a single resolving effect with parsed life loss and token characteristics. Only the active controller's permanents trigger; token entry triggers resolve after the parent ability finishes and after checking game loss.

Bitterblossom and Bitterbloom Bearer now use this grammar; their name-specific parsing, upkeep generation, and importer exceptions were removed. Unknown names, token sizes, counts, colors, subtypes, and keywords use the same execution path. Conditions, optional payments, each-player upkeep, and unknown trailing instructions still reject the entire program. This remains a two-player diagnostic without a full response stack.

Validation: 92 tests pass, including unfamiliar upkeep text, opponent-turn exclusion, repeated upkeeps, and existing lethal-life-loss/token-entry timing tests. Seeds 542–547 ran all six distinct deck pairings: four reached ten turns per player; two ended earlier with a winner. Summary: `training/examples/upkeep-542.json`. These runs are not eligible for policy training.

Rules reference: Wizards’ Double Masters 2022 release notes, Bitterblossom: mandatory life loss is not a payment; token creation still occurs. https://media.wizards.com/2022/downloads/2X2_Release_Notes/EN_MTG2X2_Release%20Notes_20220418.pdf

## Generic death effects

Fixed self-death token creation, death-triggered scry, and death-triggered counters now use the common effect interpreter. Trigger discovery still examines the battlefield before simultaneous deaths. Resolution happens after all dying creatures leave and after game-loss checks; the captured controller receives tokens or scry, and counters apply only to surviving creatures that controller controls. Nonactive-player triggers resolve first; discovery order supplies a deterministic ordering within each controller's triggers.

A whole token batch enters before its entry triggers resolve, including when the first entry trigger ends the game. Scry conservatively retains all cards on top without exposing their identities. Repeating token watchers, variable token counts (apart from the existing Nested Shambler implementation), full priority, and first/double-strike death-trigger interleaving remain unsupported. No new card-name handlers were added.

Validation: 96 tests, including unknown card names and actual combat execution. Six real-deck pairings at seeds 642–647: four reached ten turns per player, two ended with a winner after nine turns each; no new runtime questions. Unsupported cards remain in the question reports and these diagnostic games remain ineligible for training. Summary: `training/examples/death-effects-642.json`.

## Two-color hybrid mana

The shared Java mana planner accepts ordinary two-color hybrid symbols such as `{U/B}`. Each symbol requires one source able to produce either component color; different symbols choose independently. Backtracking preserves constrained colored requirements, commander tax remains generic, and duplicate source IDs are rejected. Card colors still come from metadata, not the mana spent. The diagnostic importer now asks the shared parser whether a cost is supported rather than maintaining its own narrower regular expression.

Glen Elendra Liege now imports and casts in a focused scenario with mixed blue/black sources. Tests verify that all four lands tap and cannot pay again. Java checks cover all-one-color and mixed-color payments, backtracking, unrelated colors, duplicate IDs, insufficient sources, and tax. All 96 Python tests pass. Six distinct deck pairings at seeds 742–747 reached ten turns per player with no runtime questions; unsupported cards remain explicitly recorded and games remain ineligible for training. See `training/examples/hybrid-mana-742.json`.

Still unsupported: `{2/W}`-style costs, Phyrexian costs, snow, X choices, multi-mana sources such as Sol Ring, and floating mana pools. This change does not implement those mechanics or certify a full mod build.

Rules reference: Wizards, War of the Spark Release Notes (hybrid mana choices): https://magic.wizards.com/en/news/feature/war-spark-release-notes-2019-04-19

## Diagnostic mana pools and fixed mana artifacts

The diagnostic now tracks six mana types separately (W, U, B, R, G, C). Its pure payment planner spends floating mana and activates each chosen untapped source at most once, preserving unused production. Colorless pays generic and explicit colorless requirements, but not colored or hybrid-colored symbols. A selected nonnegative X is supported in the low-level payment API; real X cards remain blocked until choices and variable effects are integrated.

Whole Oracle instructions of the form `{T}: Add {C}{C}.` (including fixed colored/mixed sequences) import as mana artifacts when Artifact is the only card type. No card-name dispatch is used. Additional costs, restrictions, conditional text, and other abilities reject the entire source. Newly cast noncreature artifacts can tap immediately. Sol Ring is now usable in diagnostic matches. This Python pool extension is not yet wired into the live Minecraft Java actions.

Unused mana survives repeated actions in one main phase, then empties at simulated step/phase boundaries for both players. The internal land-decision stage is part of first main, not a separate phase; playing a land during second main keeps that phase. Cast logs and public state include remaining pools. Planning failures do not change pools or tap sources.

Validation: 102 tests pass. The new planner agrees with Java payment results on 250 combinations of single-mana sources and costs. Focused tests cast the real Sol Ring, spend its output across two spells, preserve the leftover, reject colored payment and malformed symbols, and verify cleanup. Six distinct deck pairings (seeds 842–847): four reached ten turns per player, two ended earlier, no new runtime questions. Sol Ring was cast three times across two matches. Reports remain diagnostic, not training eligible. Summary: `training/examples/mana-pool-842.json`.

Rules reference: Wizards Comprehensive Rules, mana and step/phase boundaries: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf

## Chosen-X sorceries

A whole-text grammar now composes a mana cost containing X with fixed-characteristic “Create X … creature tokens”, “Draw X cards”, or “You gain X life”. Each affordable nonnegative X is an explicit candidate with its own value and score; repeated X symbols use the same chosen value and each contributes that much generic mana. Colored and fixed generic costs still apply. Cast and decision logs record `xValue`; resolution substitutes that value into the effect without altering the original card placed in the graveyard. X=0 is supported. The draw policy excludes choices that knowingly exceed its remaining library.

Goblin Offensive from the real deck imports through the generic grammar. No card names select behavior. Other X cards remain blocked in full: Awaken the Woods needs land-creature token mana and summoning sickness; Wildwood Scourge needs entry counters and counter-event triggers; Stonecoil Serpent needs entry counters and protection from multicolored. Variable power/toughness, targeting, instant priority, alternative costs, and definitions of X supplied by additional rules text are not silently approximated.

Validation: 108 tests pass, including fixed costs, repeated X, zero X, token characteristics, draw/life substitution, and Sol Ring paying an X spell while retaining surplus. Six distinct real-deck pairings (seeds 942–947): five reached ten turns per player, one ended earlier, no new runtime questions. None of these six random matches cast an X spell, so direct X coverage comes from focused tests and the recorded `training/examples/x-focused.json` scenario. Pool summary: `training/examples/x-spells-942.json`. This remains diagnostic only, not live Java golem integration or strategy training.

Rules reference: Wizards Comprehensive Rules 107.3 and casting procedure: https://media.wizards.com/2026/downloads/MagicCompRules%2020260417.pdf

## Land-creature tokens

The reusable token grammar now preserves an optional land card type alongside creature, including for fixed counts, triggered creation, and X sorceries. Awaken the Woods imports with its reminder text removed by the existing reminder parser. Tokens retain both Land and Creature, Forest and Dryad, and remain nonbasic. Their intrinsic mana ability follows their basic land subtype; token color alone does not grant production. Fresh land creatures cannot tap for mana or attack unless they have haste; the controller's next untap removes freshness. Used sources tap once, and tokens that leave no longer produce mana.

Mana-source discovery is shared between payment and the available-X budget. Land creatures also count for the diagnostic's supported conditional land-entry checks, with subtype metadata preserved. This does not enable arbitrary land cards with creatures' abilities or general landfall triggers; unsupported text remains rejected.

Validation: 112 tests pass. Focused Awaken the Woods tests cover X=2, land/creature types, nonbasic status, no immediate mana or attacks, next-turn payment, source tapping, source removal, haste, and subtype-dependent color. Six distinct pairings at seeds 1042–1047 produced three ten-turn windows and three earlier wins, without runtime questions. None cast Awaken the Woods in that batch; direct coverage is from focused tests. Summary: `training/examples/land-tokens-1042.json`. Live golem integration remains pending.

Rules reference: Wizards Comprehensive Rules 302.6, 305.6, 305.8, and 702.10: https://media.wizards.com/2026/downloads/MagicCompRules%2020260619.pdf


## Global tribal lords and landwalk (2026-10-29)

A whole-text pattern now compiles “Other [plural creature type] get +N/+M
and have [basic land type]walk” into independent continuous stat and keyword
grants. Unlike “creatures you control”, the grant applies to matching creatures
of **both** controllers while excluding only the originating lord. Goblin
King is a real-deck fixture; renaming the card, changing the subtype, amount,
or basic land type uses the same code. Unknown inflections and extra rules
still reject the complete card.

The diagnostic's group-combat blocker legality now checks landwalk *at
blocker declaration*: if a defending player controls any land with the matching
basic land subtype, no creature can block that attacker. A nonbasic Mountain
Forest dual still satisfies mountainwalk; the attacking player's own Mountain
does not. If the grant or qualifying land leaves before blockers are declared,
the restriction disappears. The policy uses the same legality routine as the
manual blocker action, including for menace and flying combinations. These are
not full land type-changing effects or general 2026 Commander rules support.

Coverage tests: `training/tests/test_landwalk_lords.py`.


## Multiple-tribe keyword grants (2026-10-29)

The parser now composes “Tribe A you control and Tribe B you control
have [known keyword(s)]” as two independent continuous effects.
Caterwauling Boggart's Goblin/Elemental menace grant works without
matching its card name. Creatures of either or both types gain the
keyword; opposing and unrelated creatures do not. Removing the source
ends the grant. Blocking legality is checked again at declaration,
so menace cannot force extra blockers after its source has left.

The same mechanism accepts unfamiliar names, different creature types
and combinations of known keywords. Unknown wording or extra clauses
still reject the whole program. Tests: `training/tests/test_multi_tribe_grants.py`.


## Faerie anthem with shroud (2026-10-29)

Scion of Oona's “Other [subtype] creatures you control get +N/+M”
and “Other [plural subtype] you control have [keyword]” now compose
as strict independent continuous effects, including unfamiliar
creature types and stats.

Shroud is not hexproof. Any targeted creature spell, Aura, Equip
activation or Virtuous Role trigger is illegal if its target currently
has shroud, even when the spell or ability comes from the same
controller. Previously attached equipment stays attached; shroud
does not prevent combat or untargeted effects. Losing Scion ends
both grants, so later targets become legal. This remains the
diagnostic rules subset, not blanket support for all target kinds.

Regression: `training/tests/test_shroud_grants.py`.


## Blocker-power evasion (2026-10-29)

Full-text “This creature can't be blocked by creatures with power N or
greater” now compiles as a numeric block-declaration restriction.
The existing group-combat legality routine compares the defender's
**current** power at declaration, including active buffs and debuffs,
not printed power. It updates the agent's block options and rejects
illegal manual assignments. Beloved Princess is the real-deck fixture;
unfamiliar card names and different thresholds use the same grammar.

This is deliberately limited to power-threshold blocking; it is not
protection, hexproof, shroud, or an arbitrary evasion parser. Focused
tests: `training/tests/test_blocker_power.py`.


## Goblin-style combat-damage hand deployment (2026-10-29)

A full Oracle grammar recognizes "Whenever this creature deals damage
to a player/an opponent, you may put a [subtype] creature/permanent card
from your hand onto the battlefield." Goblin Lackey and Warren
Instigator use this rule without their names selecting the behavior.
The event is queued at damage, survives removal of its source before
resolution, and chooses an eligible card from the controller's own
hand only **when the trigger resolves**. It enters without being cast,
and its entry triggers can go onto the stack normally. No mana cost is
paid. Declining is legal. An attacker blocked before dealing player
damage causes no such trigger.

Double strike causes independent player-damage events and therefore
two triggers, each with a separate resolution and choice. The current
diagnostic activates this family on combat damage to the opposing
player; handling other noncombat player-damage events is pending.
Unknown extra Oracle clauses reject the entire card instead of
ignoring their remainder.

Coverage: `training/tests/test_put_from_hand_damage.py`.
