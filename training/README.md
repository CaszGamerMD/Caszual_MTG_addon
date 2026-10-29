## New generic card groups: life-gain events, creature sweeps and compound removal

- **Life gain as a separate triggered event.** Whole-text
  `Whenever you gain life, each opponent loses N life.` recognizes and
  compiles Marauding Blight-Priest and equivalent unseen names. Each
  *positive event* creates one trigger per watcher, even when it gains many
  life or life replacements double the amount. Losing life or gaining zero
  does not trigger, and the watcher can leave once its trigger is queued.
  Life gain from Nadier's Nightblade also produces independent abilities on
  the usual stack. See `training/tests/test_life_gain_watchers.py`.
- **Board-wide creature destruction.** Strict sorcery grammar handles
  `Destroy all creatures.`, `Destroy all creatures. They can't be
  regenerated.`, and `Destroy all creatures with toughness 4 or greater.`
  These are represented as a simultaneous, nontargeted destruction event.
  Current toughness is computed at resolution, including counters and
  ongoing anthems; hexproof and protection do not stop nondamage
  destruction, whereas indestructibility does. The current sandbox has no
  activated regeneration rules; regeneration prohibition is not a full
  implementation of external regeneration effects. Damnation and Citywide
  Bust are covered in `training/tests/test_creature_sweeps.py`.
- **Targeted destroy plus ordered token creation.** Generic Oracle wording
  `Destroy target artifact or creature. Its controller creates ...` is
  parsed with a complete token specification, without a card-name branch.
  The creature or artifact must be a legal target at resolution; an
  indestructible target survives but its controller still creates the token
  because the instruction does not say *if it was destroyed*. The target
  controller (not necessarily the caster or owner) creates tokens with the
  standard replacement, enter-trigger and token-action machinery. Bovine
  Intervention is the saved-deck example. See
  `training/tests/test_destroy_and_create.py`.

These additions are diagnostic two-player approximations, not proof of
complete Commander legality. All changes remain solely in the private
experimental GitHub branch; Minecraft integration has not started.

## Further generic parsing: optional search, upkeep and end-step rules

The strict Oracle parser now recognizes three further reusable trigger patterns.
All are represented as normal priority-stack events and must consume their
entire Oracle instructions; unrecognized extra clauses fail closed.

- **Opponent basic-land ETB search**: `When this creature enters, each opponent
  may search their library for a basic land card, put it onto the battlefield
  tapped, then shuffle.` The opponent chooses whether to search; the active
  library stays private. Accepted searches put a real basic land onto the
  battlefield tapped without using a land play and shuffle even if the
  player finds nothing. The ability can resolve if its source leaves.
  This supports Old-Growth Dryads and is tested in
  `training/tests/test_opponent_basic_entry.py`.
- **Optional subtype tutor to hand**: `When this creature enters, you may
  search your library for a [subtype] card, reveal that card, put it into
  your hand, then shuffle.` Subtypes are compared to printed and parsed
  creature/card subtypes, not the card's name. A successful search moves
  the selected physical card from the controller's own library into
  their hand, reveals it and shuffles; declining neither searches nor
  shuffles. This supports Goblin Matron and other wording equivalents.
  See `training/tests/test_subtype_tutor.py`.
- **Optional token creation**: `At the beginning of your upkeep, you may
  create ...` now includes a choice at trigger resolution. When accepted,
  the complete token specification goes through replacement effects,
  enters and token-action triggers. The Creakwood Liege example combines
  this with independent black and green static anthems, each affecting the
  actual created Worms. See `training/tests/test_optional_upkeep_tokens.py`.
- **Land-count intervening-if upkeep**: `At the beginning of your upkeep,
  if you control N or more lands, create ...` checks the land threshold
  both when the ability would trigger and again when it resolves.
  Lands from the simulator's separate mana-battlefield representation are
  included, without counting tapped nonland artifacts. This handles
  Dragonmaster Outcast and combines with token doublers. See
  `training/tests/test_land_threshold_upkeep.py`.
- **Tapped-creature end-step life loss**: `At the beginning of your end
  step, each opponent loses life equal to the number of tapped creatures
  you control.` counts only controlled *creatures*, using their tapped
  status at trigger resolution rather than at trigger time. This handles
  Throne of the God-Pharaoh with the ordinary once-per-end-step stack
  rules. See `training/tests/test_tapped_end_step.py`.

These are **two-player diagnostic rules**, not multiplayer certification.
The default optional-search/token decisions are deterministic prototype
policies, not an oracle for perfect play. The full card coverage audit must
be rerun after these changes before claiming updated totals.
No Minecraft migration has taken place.

## Token-leaves battlefield events

Nadier's Nightblade now compiles its full Oracle wording as a token-leaves
trigger: `Whenever a token you control leaves the battlefield, each opponent
loses N life and you gain M life.` This is intentionally independent of
Mirkwood Bats' "create or sacrifice" rule. Each token exiting produces
one trigger (including during simultaneous removal), regardless of whether
it dies, is exiled, is sacrificed to a previously validated cost, or is an
Aura Role token detached when its host leaves. A non-token permanent does
not trigger it. Source controller is checked from the pre-leave battlefield;
once queued, its trigger can resolve even if the Nightblade has left.

Each trigger goes on the normal priority stack and calls the shared life-gain
handler, so gain replacers and gained-life-this-turn conditions still work.
A token creature sacrificed as a cost can also trigger other ordinary
creature-death abilities; simply destroying or exiling it must never count
as a sacrifice. Normal token graveyard/exile cards cease to exist after
leaving. See `training/tests/test_token_leaves.py`. This is not a
general sacrifice-cost parser; arbitrary sacrifice costs and multiplayer
choices remain pending. The only supported diagnostic match is two-player.

Token replacement now also applies to the **number of Virtuous Role
Aura tokens** created by supported Role triggers. When two Roles from the
same controller would remain on the same host, the ordinary Role
state-based restriction removes the older Role token. That departure
generates an independent token-leaves event; creation still triggers
once for each token before the older Role leaves. The interaction is
covered by `test_doubled_roles_count_creation_then_extra_role_leaves`
in `training/tests/test_token_action_triggers.py`.

These are experimental standalone rules, not Minecraft integration.

## Optional basic-land search after exile; per-token triggers

Path to Exile now has a strict complete-text interpretation for
`Exile target creature. Its controller may search their library for a
basic land card, put that card onto the battlefield tapped, then shuffle.`
Target legality is checked at casting and resolution; exiling does not count
as destroying or dying and works on indestructible creatures. The **target
creature's controller** chooses whether to search, independent of who cast the
spell. The default diagnostic policy searches if a basic is available; it can
be overridden by a future agent decision policy. An accepted search uses
the affected player's **private** library, chooses a genuine basic land,
places it tapped without spending their land play, and shuffles that library
deterministically. It can legally find nothing; a declined search does not
shuffle. A target that has become illegal gets no exile or land search.
`training/tests/test_exile_basic_search.py` covers these cases and fails
closed on extra unknown instructions. This adds only the *specific* optional
search instruction, not general library search/land tutoring.

Mirkwood Bats introduces a reusable token-action trigger rule:
`Whenever you create or sacrifice a token, each opponent loses N life.`
Each **actual** token created (after doubling/replacement) independently
triggers; each token sacrificed after paying a validated cost independently
triggers. A destroyed or exiled token is **not** a sacrifice. The live
battlefield sources are snapshotted at trigger time; their triggers resolve
on the existing stack even if the source leaves. Normal created creature
and Aura Role tokens use the shared event. An internal
`sacrifice_token` helper executes a previously validated token-sacrifice
cost, including creature-death triggers, but is **not a free player action**;
legal sacrifice ability/cost grammars still need implementing. The diagnostic
two-player backend models each opponent as the other seat and does not
claim full multiplayer coverage. See
`training/tests/test_token_action_triggers.py`.

The experimental training rules still have not been migrated to Minecraft.

## Creature exile with last-known-power life gain

The Swords to Plowshares Oracle-language pattern
`Exile target creature. Its controller gains life equal to its power.`
is now a targeted-removal operation distinct from destruction.
It checks legal creature targets on cast and again at resolution;
indestructibility does **not** prevent exile, while opposing hexproof
still restricts targeting. The creature's power is read at resolution
before it leaves the battlefield, including live buffs. After exile,
its controller receives a genuine life-gain event, including active
life-gain replacement effects and gained-life-this-turn tracking.
Real non-token cards move to their owner's exile zone; tokens cease
to exist when leaving the battlefield. The prototype still chooses the
command-zone option for an exiled commander. Exiling does not emit a
"dies" event. See `training/tests/test_exile_creature_life.py`.

This strict instruction does not imply support for Path to Exile's
optional land search or other arbitrary exile replacements. No work
has been moved into Minecraft.

## Typed instant removal: artifacts and enchantments

Naturalize and Nature's Chant use the same strict instruction,
`Destroy target artifact or enchantment.`, interpreted in the sandbox
through a typed permanent-target enumerator. Legal targets include
artifacts, enchantments and artifact creatures (including one's own),
but not ordinary creatures. Hexproof, protection, ward, indestructibility
and target legality at resolution are evaluated through existing shared
rules rather than an on-cast permanent deletion. The destruction moves
the permanent through its normal graveyard/state-based pathway, and
the spell uses normal priority and stack resolution. Nature's Chant
retains its green/white hybrid mana requirement.

The whole-text import only activates this removal for the exact supported
instruction with a supported cast cost. It does not silently treat extra
clauses or other removal words as blanks. Noncreature artifact lands with
unusual continuous abilities, regeneration and broader exile/search
removal interactions remain outside the diagnostic's general rules.
See `training/tests/test_targeted_removal.py`.

This remains standalone experimental training code. No Minecraft
integration has been performed.

## Token-doubling and subtype-effect progress

Strict Oracle grammar now accepts reusable token-creation replacements:
Doubling Season (effect-created tokens under its controller), Parallel Lives
(tokens under its controller), and Primal Vigor (tokens for either player).
One replacement operation applies once per source to a **single creation
event**, before any of its tokens enter. Multiple doublers multiply rather
than recursively retrigger each other. Spell-created and triggered tokens
share the same logic, including their ordinary enter-the-battlefield
triggers. This currently creates creature tokens within the diagnostic
engine's token model; it does not imply arbitrary noncreature token support.

Counter replacements now distinguish `+1/+1 counters on creatures` from
`any counters on a permanent you control`. Primal Vigor affects +1/+1
counter events on both players' creatures, while Doubling Season affects
effect-generated counters of any type on its controller's permanents,
including supported noncreature Spacecraft charge counters. Beginning
planeswalker loyalty counters and counter payments are not treated as
effect-generated counters. See
`training/tests/test_token_replacements.py`.

A subtype-aware spell-cost filter additionally supports Goblin and Rogue
spell discounts from Frogtosser Banneret and Goblin Warchief. Printed
creature subtypes are consulted even when the existing Java card parser
handles a spell without an EventDefinition. Goblin Warchief's live haste
grant and Goblin Chieftain's other-Goblin stat/haste anthem share the
existing static-effect engine and disappear with the source. Regression
checks are in `training/tests/test_subtype_rules.py`. Creature-wide
keyword grants deliberately remain separate to preserve older effects.

`training/diagnostic_coverage.py` now writes a separate per-deck JSON
coverage report at `training/reports/diagnostic-coverage.json`, printed
in the GitHub training workflow and saved in its report artifact.
The full Java rules audit is **not** the same as diagnostic parse coverage:
neither is proof of complete Magic rules or training eligibility.

No code from these experimental rules has been moved into Minecraft.

## Hydra-style Aura counter growth

The reusable attachment-event grammar now also recognizes
`When this Aura enters, put a +1/+1 counter on enchanted creature.`
and
`At the beginning of your upkeep, double the number of +1/+1 counters on
enchanted creature.`
The former queues an enter trigger; the latter queues an upkeep trigger
that reads the attached creature's **actual counter count when the ability
resolves**, then puts that many counters on it. The new counters are subject
to active replacement rules (such as Hardened Scales and Branching Evolution),
so doubling an existing 2 counters with Hardened Scales gives 5 total,
not 4. Empty and removed Auras cannot apply their pending instructions;
zero counters cannot become positive via a doubling instruction.
`training/tests/test_aura_counter_growth.py` covers these scenarios,
including renamed Oracle-text equivalents and fail-closed extra clauses.

This supports Hydra's Growth in the **standalone diagnostic simulator**
without adding any code to Minecraft.

## Attached creature upkeep growth

Forced Adaptation now supplies a reusable Aura-trigger grammar:
`At the beginning of your upkeep, put N +1/+1 counters on enchanted creature.`
The Aura's currently enchanted creature is resolved when the ability resolves,
not guessed from a prior target. An Aura that leaves or has no current legal
enchanted creature does not place counters, and reattachment before resolution
redirects the instruction to its current host. Hardened Scales and Branching
Evolution apply to the placed counters through the same generic replacement
handler. The compiler supports different positive integer counts, rejects
unparsed remainder text and does not dispatch on a card name.
`training/tests/test_enchanted_upkeep.py` verifies timing and composition.

This remains an **experimental standalone rules-system enhancement**, not
Minecraft golem behavior.

## Generic creature +1/+1 counter replacements

Hardened Scales and Branching Evolution now compile as whole-card Oracle
replacement rules rather than card-name switches. Positive +1/+1 counter
events on creatures controlled by the source's controller gain one additional
counter or receive twice as many counters, respectively. Zero-counter events
remain zero, opposing creatures are unaffected and live removal of a
replacement source immediately removes its modifier. Separate replacement
effects can stack: the current deterministic engine selects a legal
maximum-counters ordering (additions before doublers).

Shared counter-event handling now covers triggered self-counter placement,
bulk placement on friendly creatures, counter-then-token attack effects and
direct attack counters. Coverage checks are under
`training/tests/test_counter_replacements.py`; generic counter patterns
beyond those whole clauses, including token doubling and replacement of
non-creature permanent counters, remain unsupported. The implementation
is restricted to the offline diagnostic training system, not Minecraft.

## Generic spell-discount grammar

The diagnostic engine recognizes whole-clause rules of the form `[type or
color] spells you cast cost {N} less to cast.` Supported filters currently
include colors, artifact, enchantment, creature, instant, sorcery,
planeswalker, Aura and Equipment, as well as two-part disjunctions such as
`Artifact and enchantment`. Reductions from separate battlefield permanents
stack and apply **only to the generic mana component** of the spell's total
cost, including commander tax, never to colored or hybrid mana symbols.
The chosen X value is retained while payment accounts for the reduction.
Activated abilities and ward payment are not spell costs.

Examples imported by Oracle text: Emerald Medallion, Pearl Medallion,
Jukai Naturalist, Starnheim Courser, Transcendent Envoy and Danitha
Capashen, Paragon. These include Aura-or-Equipment alternatives and
multiple independent discounts that disappear when their sources leave. Their names are
not dispatched in the parser. Unparsed extra instructions reject the full
card; `training/tests/test_spell_reductions.py` exercises the grammar,
payment planning, color restrictions and tax behavior. The work remains
**offline simulator code only** and does not migrate the AI to Minecraft.
Some rare additional-cost interactions remain outside the diagnostic engine.

## Life addition and source-controlled replacement ordering

Angel of Vitality now parses as a composition of three reusable pieces:
flying, `gain that much life plus N instead`, and `this creature gets
+P/+T as long as you have N or more life`. The additive effect applies
once to each **positive** gain event (not life loss or zero life). It is
relative to the replacement source's controller, including life gained
from lifelink and other triggered abilities. The stat bonus updates
immediately as the creature's controller crosses the threshold.

Where additive and doubling replacements coexist, the current deterministic
pilot chooses a **legal maximal-gain order**, addition before multiplication.
That is an explicit decision policy, not a Magic rule requiring this order.
A future agent may choose any other legal ordering when appropriate. See
`training/tests/test_additive_lifegain.py` for renamed-card and combined
replacement regressions.

These changes remain local to `training/` and are not wired to Minecraft.

## Continuing unresolved-card work: damage Auras, life replacement and entry rules

The strict Oracle grammar now accepts three additional damage-Aura programs:
Spirit Link (`Whenever enchanted creature deals damage, you gain that much
life.`), Keen Sense (optional controller draw when the enchanted creature
damages an **opponent of the Aura controller**), and Armadillo Cloak (combining
the same damage-life trigger with an attachment bonus and trample).
The damage event kernel collects actual positive damage from supported regular
combat, first/double strike, grouped combat, and supported noncombat player
and board-damage abilities. A trigger is queued on the existing priority stack,
and it can resolve after the Aura leaves. A prevented/zero-damage event does
not trigger. This still does not claim arbitrary card text or all damage
redirection/replacement interactions are handled.

Boon Reflection and Rhox Faithmender now compile a generic gain-life replacement
of `twice that much`. Two independent doublers multiply the gain by four,
before it updates life totals and gained-life-this-turn history. Opposing
players' gains are unaffected. Other life-gain replacement wording and
ordering choices are deliberately not inferred.

Authority of the Consuls now compiles two independent clauses: creatures
controlled by opponents enter tapped if the source already exists, and
opposing creature entries trigger the source controller's lifegain.
Simultaneously entering sources do not retroactively apply tapped-entry
replacements. The same trigger wording works with unfamiliar card names.

Regressions: `test_damage_auras.py`, `test_life_replacements.py`,
`test_opponent_entry.py`. These additions are to the **offline, experimental
rules simulator only**. No production Minecraft golem code has been migrated.
Old stored gauntlet totals and outstanding-card counts are historical and
**must not be presented as a fresh coverage audit** until tests and the
gauntlet are rerun.

## Conditional life rules: end-step tokens and continuous effects

Two additional Oracle-language families are implemented without card-name
dispatch. `At the beginning of your end step, if you gained N or more life this
turn, ...` uses **total life actually gained that turn** (not net life
change) and queues the parsed effect on the priority stack. Combat lifelink,
spell lifegain, and supported triggered lifegain contribute to that history.
The recorded amount resets at the start of each turn; only the active player's
end-step abilities are examined. Griffin Aerie is the imported fixture, but
the threshold, token characteristics, and effect are parsed from its text.

`As long as you have N or more life, this creature gets +P/+T and has
[keywords].` evaluates against the **current controller's life total** on
every stats/keyword query. Losing life can remove the bonus immediately,
and regaining life restores it; Serra Ascendant is the imported fixture.
Unfamiliar names with equivalent language are accepted, while unparsed
additional instructions still make the card unsupported.

Regressions live in `training/tests/test_end_step_lifegain.py` and
`training/tests/test_life_threshold_stats.py`. The engine is still a
restricted diagnostic, not a Commander rules-complete or live golem runtime.
Old published gauntlet numbers and coverage counts are retained as historical
baselines; they have **not** been revalidated against this change.

## Cast-trigger grammar (Sythis and unfamiliar matching cards)

The Oracle compiler now recognizes `Whenever you cast a/an [type] spell, ...`
for spell-type filters (any spell, creature, noncreature, artifact, enchantment,
instant, sorcery and planeswalker). The event is checked against the **printed
spell types** at the time of casting and against the trigger source's controller.
Cards need not be identified by name. Trigger instances enter the existing
priority stack above the spell and remain there if the spell is countered or
the triggering permanent leaves. Trigger effects may compose supported ordered
instructions such as `you gain 1 life and draw a card`; resolution and
failed-draw checks occur in written order.

`Sythis, Harvest's Hand` is the first imported regression example. The
test suite also covers unknown names and rejects unknown trailing Oracle
instructions rather than granting partial support. These are **diagnostic
simulator rules**, not live golem behavior or a claim that other unresolved
cards are playable. Complex cast restrictions, cost reduction, modal choices
and unrecognized effect clauses remain unsupported.

# Commander self-play deck intake

## Land and attachment language batch

Ten more queued cards now resolve through shared land-entry, mana, and attachment grammar.
The [retained forty-game benchmark](examples/enchantments-gauntlet-land-equipment/README.md)
records 26 wins, 14 losses, and 0 ties, with no runtime questions. All-deck unique
unsupported cards fall from 209 to 199; the enchantment deck has 31 remaining.


## Faster question resolution workflow

Sync the experimental branch before choosing the next batch to avoid duplicating concurrent rules work. Refresh current parse coverage without playing games:

```bash
python training/question_batches.py --decks training/decks/*.json --focal-id 5189995 --out training/reports/question-batches-current.json
```

The report ranks candidate language families by affected focal cards, all affected cards, then observed card-game encounters when available. Repeated clause templates normalize self references and numeric parameters; recognized Python components are marked separately. Families overlap and do not promise a number of newly supported cards. Inspect full Oracle text and implement composable rules, then exercise unfamiliar combinations and unknown-clause rejection. Use focused tests while implementing, followed by the full suite and one gauntlet for a completed batch. Gauntlets now save `question-batches.json` automatically.

The [synchronized benchmark](examples/enchantments-gauntlet-question-batches/README.md) records current coverage and results. `test_unseen_language_matrix.py` checks 32 filter/effect combinations across seven spell type sets and both controllers.


## Entry lifegain and combined anthem update

Ajani's Welcome and Spidersilk Armor now use shared whole-text rules.
The [new forty-game batch](examples/enchantments-gauntlet-entry-life-anthems/README.md)
records 18 wins, 21 losses and 1 tie; focal unsupported cards fall from 62 to 60.

## Gauntlet scoring and enchantment rules update

Future `gauntlet.py` runs decide a completed turn-limit game by **remaining
life total**: higher wins, equal scores tie. Normal wins/draws take precedence;
blocked games are not scored. Reports retain ties, tie rate, score metric,
ordinary engine outcome and score adjudication separately. `turnLimit` is a
reason count overlapping wins/losses/ties, not an extra outcome category.

Ellivere, Sixth Sense, All That Glitters, Ethereal Armor and Helm of the Gods
now compile through shared enchantment/attachment programs. See
[`examples/enchantments-gauntlet-roles-life-score/README.md`](examples/enchantments-gauntlet-roles-life-score/README.md)
for rule boundaries, validation and the retained forty-game batch. The previous
gauntlet is preserved unchanged with its original unresolved-window semantics.


## Imported deck

- Source: https://archidekt.com/decks/14850373/budget_deck
- Commander: Kolodin, Triumph Caster (one card).
- Main deck: 99 cards, retaining quantities and double-faced card identities.
- Excluded: 12 cards tagged Maybeboard; exclusion overrides other included categories.
- The JSON fixture includes the source's Oracle data for rules-coverage work. It is an intake snapshot, not a deck certified playable by the current pilot.
- The text fixture contains only the commander and main deck.

## Second imported deck

- Source: https://archidekt.com/decks/5254666/garbo_gobbos
- Commander: Zurgo Helmsmasher (one card).
- Main deck: 99 cards.
- Excluded: 19 sideboard/maybeboard cards. Explicit Sideboard exclusion overrides the site's includedInDeck flag, per the user's instruction.
- Successfully retrieved on retry on October 27, 2026. Both training decks now have JSON Oracle snapshots and commander/main-deck text exports.

Zurgo requires forced attacks, turn-dependent indestructible, damage-history-dependent death triggers, and +1/+1 counters. Its deck adds tribal continuous effects, token replacement (Divine Visitation), creature-enter life loss (Impact Tremors), token-enter/leave life loss (Mirkwood Bats), creature mana/sacrifice abilities, storm, X costs, board wipes and modal choices, tutors, cost reductions, and land type changes (Blood Moon). These effects need implementation or a complete rules engine before legitimate self-play.

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

Two independent agents receive separate observations: their own hand, legally known information and public zones. Opposing hands and unknown library order remain hidden. Both use the same frozen policy checkpoint during a match, with independent private decision state. Post-match learning may update a shared persistent policy. Saved improvements must be evaluated against prior checkpoints across fresh shuffles and both starting seats before promotion. The simulator below implements these boundaries in a restricted sandbox; full-deck self-play still requires a legal rules backend.

## Simulator and review tools (0.12.6)

The first runnable version provides a deterministic classroom sandbox. It reuses the mod's Java card parser, mana planner and damage resolver through a local subprocess. It does not duplicate those rules in Python. The actual Commander decks remain blocked from valid training until their unsupported effects and the complete game backend are implemented. No live Minecraft entities are exercised by this tool.

Requirements: Python 3.10+ and a JDK 17+ on PATH (the mod build still requires Java 25). No Python packages or network access are needed to run the tools after checkout.

From the repository root:

```sh
python3 -m unittest discover -s training/tests -v
python3 training/simulator.py audit
python3 training/simulator.py simulate --demo --seed 42 --starter 0
python3 training/simulator.py train --demo --generations 3 --evaluation-seeds 8
```

Audit creates `training/reports/deck-review.json` and a standalone HTML review file. The simulator creates `training/reports/demo-replay.json` and a standalone HTML replay. Open the HTML directly on a phone or desktop; there are no external assets, analytics or server dependencies. The reusable `viewer.html` can open any generated JSON report. It supports previous/next event, autoplay, a turn jump, a scrubber, a searchable play log, life/hand/library counts, public battlefield and graveyard, and a questions tab.

### Questions, not guesses

Every unsupported imported card produces a stable, deduplicated blocking question with its card name, Oracle text, deck context and missing rule. Multiple faces, unsupported costs, triggers and conditional abilities are not silently stripped. Deck structure and missing full-game capabilities are also flagged. An unsupported runtime stage or card pauses the sandbox and produces a question; that match is ineligible for learning.

The initial audit has 133 unique blocking review items (including the full-backend requirement). Budget Deck has 33 supported card copies and 67 unsupported copies; Garbo Gobbos has 26 supported copies and 74 unsupported copies. These counts include the commanders. They describe the current parser subset, not legal match coverage.

Human answers can be written in the viewer and downloaded as review notes. Notes alone never enable a rule or mark a failed match as training data. Implementation and regression tests must close the capability gap. Re-auditing the same JSON output preserves existing answer notes by question ID.

### Independent agents and retained learning

Each agent receives an immutable observation containing its own hand and the public state, plus its legal action menu. The opposing hand and either library's card order are never included. The public replay also omits private draws and library order. A replay's seed is for human reproduction, and is not supplied to the agents.

Both agents use frozen copies of the shared policy throughout a self-play match. Only after completion are both agents' action-feature experiences pooled. The initial learner uses evolutionary changes to general decision weights, influenced by the winning/losing agents' feature averages; it is not a neural network or route/script memorization. Candidate policies are evaluated against the retained champion across fresh shuffle seeds with the candidate controlling each seat. Wins rank first, then total turns in winning games; losing quickly gives no reward. Blocked and timed-out matches give no reward and cannot justify promotion.

Only candidates that beat the champion in the paired evaluation are retained. Ties preserve the champion. Checkpoints, rejected candidates, public replays and generation history persist under `training/runs/demo/`. Rerunning the command resumes the next generation. An authoritative state.json atomically commits the champion and generation history together, so interrupted readable exports can be recovered on resume. Resume requires the same seed and evaluation settings. This is a single-process runner, not a concurrent training service. Benchmark promotion is experimental and based on a small sample, not evidence of a strong Magic opponent.

### Declared sandbox limits

The synthetic demonstration decks are not the user's lists and are not represented as legal Commander decks. The turn model starts at 40 life, draws on each turn, allows one land and supported spells, resolves at most one attacker/one blocker, discards deterministically to seven, and ends on zero life or failed draw. It has no priority/response stack, commanders, mulligans, multiple attackers/blockers, upkeep triggers, team continuous effects or card-specific replacement effects. It is a testbed for privacy, self-play orchestration, retained policy evaluation and log review.

Policies carry a sandbox scope marker and are not loaded into live golems. The submitted decks may run only in the explicitly limited, non-training diagnostic described below. A fully legal engine remains the next required integration.

GitHub Actions runs the checks, audits both real decks, generates a public replay and exercises three generations. Download the `commander-training-review` artifact for HTML/JSON review files and checkpoint history. The regular mod check also runs the simulator's regression suite.


### Included review examples

- [Short completed sandbox replay](examples/short-sandbox-replay.html): a complete synthetic match with an eight-life start for a compact demonstration. This is separate from the 40-life training baseline.
- [Both real decks: rules questions](examples/deck-review.html): the initial 133-item audit with card text and answer-note controls.
- [First three-generation training report](examples/first-training-run.json): three self-play games and 48 paired evaluation games; all candidate policies tied the champion, so none was promoted.

Generated HTML embeds only the public replay and uses lossless packing to reduce file size. JSON reports retain the expanded, readable event format. CI validation runs start fresh; continuing a training campaign requires retaining its output directory, not just launching another CI run.

## Real-deck diagnostic: ten turns per player

Run `python3 training/simulator.py diagnose --seed 42 --turns-per-player 10` to shuffle and draw from all 99 actual main-deck cards for both saved lists. Commanders begin in their respective command zones; Kolodin and Zurgo can now be cast in this limited diagnostic. This diagnostic deliberately keeps unsupported cards in the physical library and hand as unplayable objects; it does not substitute a vanilla effect or manufacture legal decisions. The two-player starting player skips the first turn's draw. This is an incomplete diagnostic, not a Commander game or eligible training data.

A narrow diagnostic-only land extension recognizes Command Tower using the actual commander's color identity, checklands by basic land subtype, the two-other-lands entry condition, and the two-basic-lands condition on Smoldering Marsh. These do not imply support in the live Minecraft golem. The full audit questions remain open for the live game and full backend.

The original seed-42 baseline completed ten turns for each player with both at 40 life and no spells cast because their commanders were then unsupported. One unsupported card was discarded during cleanup; this is a sandbox decision and should not be treated as a trained Magic strategy.

The replay is saved in `examples/real-decks-10-turns.html`, including the public event log, two deck names and commanders, plus all blocking review questions. The complete JSON output includes the cards remaining in each hand for **post-run human inspection**. Neither agent receives its opponent's private hand or this post-run report. The diagnostic never changes the retained training checkpoint.

## Type-aware event prototype: Kolodin and Andúril

`card_events.py` is a separate, focused rules prototype. It reads actual card types, creature subtypes, legendary status and Oracle text; records entry and attack events; and handles the following interactions in isolation:

- Kolodin grants your Mounts and Vehicles haste while controlled. A Mount entering while Kolodin is already present becomes saddled until end of turn; a Vehicle entering becomes an artifact creature until end of turn. Existing Mounts/Vehicles do not retroactively receive those entry triggers when Kolodin enters later.
- Mounts are already creatures; saddle is a status. Crew and saddle tap other untapped creatures of enough total power, including freshly entered creatures. Saddle is restricted to sorcery timing.
- Andúril's equip ability costs two generic mana and targets a creature you control. Its attached creature gets +3/+1. On attack, it creates two tapped 1/1 white Spirit creature tokens with flying; they enter attacking if the equipped creature is legendary and the equipment controller is also the attacking player.
- Brightfield Mustang untaps and receives a persistent +1/+1 counter when it attacks while saddled. End-of-turn cleanup removes saddle/animation but not counters, and Equipment detaches from a Vehicle when it stops being a creature.

Regression tests use actual card metadata from the supplied deck and reject unsupported additional rules instead of ignoring them. A small event trace is saved as `examples/kolodin-anduril-events.json`.

Kolodin, Zurgo, supported Mounts/Vehicles, crew/saddle and Goblin Instigator now feed the limited real-deck diagnostic. Andúril remains isolated until multiple attackers and its token combat are integrated. The prototype resolves events immediately; it does not yet implement the stack, response windows, full attack/block choices or combat damage for multiple attacking creatures. It is **not connected to the Minecraft golem**; cards remain in the full-game review queue until those gaps are resolved.


## Latest ten-turn real-deck diagnostic

Both commanders can be cast from the command zone, including accumulating commander tax and the selected return-to-command-zone option. The diagnostic tracks combat damage from each commander toward the 21-point loss condition. Zurgo's haste, forced attack, indestructible on its controller's turn and the combat death-counter case are modeled. Kolodin's subtype entry triggers and haste and supported crew/saddle feed the turn runner. Goblin Instigator and exact whole-text Goblin-token sorceries (including Dragon Fodder) create actual 1/1 red Goblin token objects; tokens cease to exist after leaving the battlefield.

Seed 42, ten turns each: Kolodin's player ended at 24 life, with 14 damage from Zurgo; Zurgo's player remained at 40. Zurgo cast Dragon Fodder, made two Goblins and attacked with them, then cast Zurgo. Kolodin was cast four times and blocked Zurgo repeatedly; the total casting cost rose from two mana to four, six and eight due to commander tax. Zurgo gained four +1/+1 counters. [Replay](examples/real-decks-progress.html), [summary](examples/real-decks-progress-summary.json).

This is still an incomplete diagnostic: it resolves triggers automatically, has at most one attacker and blocker, cannot cast Andúril yet, and leaves unfamiliar cards unplayable and flagged. In particular, 133 full-game audit questions remain open, with partial diagnostic support marked explicitly. Both policies act independently; this result is not a valid Commander match and cannot update the shared training checkpoint. It is not connected to live Minecraft entities.

Rules references: https://magic.wizards.com/en/rules and https://magic.wizards.com/en/formats/commander


If the same partial diagnostic continues, Zurgo wins on its eleventh turn with 25 commander damage while Kolodin's player has 13 life. This outcome depends on unsupported cards remaining unplayable and the simplified combat model; it is not a prediction of a real game or evidence of learning.


## Four-deck pool and non-mirror matchmaking

The pool also contains **faeries** (Obyra, Dreaming Duelist) and **squirrels** (Chatterfang, Squirrel General), each with one commander and 99 main-deck cards. The faeries snapshot had no excluded sideboard/maybeboard cards; squirrels excluded 16. Category exclusion takes precedence over the site included flag, preserving the earlier request.

    python3 training/simulator.py diagnose --seed 42 --turns-per-player 10
    python3 training/simulator.py pool-diagnose --matches 6 --seed 42 --turns-per-player 10

The single diagnostic randomly selects an ordered pair from the supplied pool. A batch randomly orders distinct pairings and randomly assigns their player seats; a batch cannot request more than the number of possible distinct unordered pairs. Identical deck IDs or the same complete commander/main-deck list are deduplicated even if copied or renamed. Direct diagnostic and generic simulator entry points also reject a mirror. Given the same snapshots and seed, the selection and shuffles are reproducible.

Six seed-42–47 diagnostics exercised all six pairings among the four decks. Two ended early through commander damage; four reached ten turns for each side. These are incomplete diagnostics, not evidence of relative deck strength. The summary is in examples/four-deck-pool-summary.json; each generated diagnostic includes its selected deck IDs, source commander, seed, review questions and full event replay.

The four-deck audit currently has 265 unique full-game blocking review questions. Some cards have limited diagnostic-only support; audit coverage is not equivalent to a legal match engine. The random real-deck games remain ineligible for learning until those gaps are resolved.

The synthetic demo now uses two distinct sample decks too. To prevent mixing incomparable evaluations, its new checkpoints use training/runs/distinct-demo/ and record the distinct-decks-v2 environment. Earlier mirror-demo data is preserved in its previous directory; it is not overwritten or presented as a new benchmark. A request to resume an older incompatible state is rejected rather than silently mixing results. These synthetic tests do not train on the four real decks.

### Squirrel rules and resumed sample training

The limited real-deck diagnostic recognizes Squirrel Mob and Squirrel Sovereign from the saved Oracle snapshot. Mob counts other Squirrel permanents on either side; each Sovereign gives other Squirrels its controller controls +1/+1. These continuous effects update when permanents enter or leave. They do not implement Chatterfang's replacement effect, its activated ability, or a complete multiplayer rules engine. Unknown cards remain review questions and these games are not eligible for learning.

All six distinct deck pairings were rerun for up to ten turns per player; results are in `examples/squirrel-rules-pool-summary.json`. Three sample-deck training generations were evaluated with 16 games each; all candidates tied the champion and none was promoted. `examples/sandbox-checkpoint.json` preserves that sample run's state. To resume it in a fresh checkout, copy it to `training/runs/distinct-demo/state.json`, then run `python3 training/simulator.py train --demo --generations 3 --evaluation-seeds 8`. The checkpoint is for the synthetic environment, not the real decks or live Minecraft golems.

### Rules-focused play tests: deaths and creature entries

Blood Artist, Zulaport Cutthroat, Nested Shambler and Impact Tremors now have limited diagnostic support. See [death-and-entry lessons](rules/death-and-entry.md) for answered rules questions, official sources, regression scenarios and remaining timing gaps. The review UI shows validated diagnostic rulings separately from human notes; full-game questions stay open. Runtime questions raised during play are now retained alongside the initial audit.

The six-pairing seed-142 batch is saved in `examples/death-rules-pool-summary.json`. Each match includes `rulesProgress`: playable card-copy coverage (including commander), lands played, spells cast, trigger log entries, runtime questions and unsupported cards encountered. These measure implemented rules being exercised, not strategic learning or relative deck strength. Real-deck diagnostics still do not update the shared policy.


## Faerie entry, color and scry diagnostic

The limited real-deck diagnostic recognizes Obyra, Dreaming Duelist's actual Oracle text, Flying and its entry trigger: whenever another Faerie controlled by Obyra's controller enters, the opponent loses one life. Obyra does not trigger on its own entry or an opponent's Faerie. Imported creatures retain their actual creature subtypes and colors instead of being reduced to a generic creature. This allows Briarberry Cohort to get +1/+1 exactly while its controller has another blue creature, with the bonus removed immediately when the condition ends.

Faerie Seer's real entry ability is supported: the controller scries up to two cards. The current diagnostic policy makes the legal conservative choice to leave all looked-at cards on top in their existing order. The log does not expose card identities or library order; scrying an empty library does not count as a failed draw. The policy does not yet evaluate rearrangements or put cards on the bottom.

The same six non-mirror seed-42–47 matchup diagnostics were rerun. In match 3 (Zurgo vs Obyra), the Obyra player cast Obyra, Briarberry Cohort and Faerie Seer; both Faerie entries triggered Obyra, and Faerie Seer scried. Inspect examples/faerie-rules-replay.html and examples/faerie-rules-pool-summary.json. The five other matches were also rerun. This is still a partial automatic-resolution diagnostic: flash response timing, priority and the stack, many other abilities, multiplayer combat and the full Chatterfang rules remain unsupported. These results do not train or replace the shared policy and are not complete Commander games.


## Faerie upkeep, tokens and life loss

The diagnostic supports the exact current imported text for Bitterblossom and Bitterbloom Bearer. On their controller's upkeep, the controller loses one life and creates the appropriate 1/1 flying Faerie token: black Faerie Rogue for Bitterblossom, blue-black Faerie for Bitterbloom Bearer. Obyra watches each allied Faerie permanent entering, including a Kindred Faerie enchantment such as Bitterblossom and the new tokens. Token types and colors remain available for later effects.

The upkeep ability creates its token before the loss check. If its controller loses at that point, pending later Obyra triggers do not resolve in this two-player diagnostic. Tests cover that edge case. Trigger resolutions are still automatic, not a priority/stack implementation, and flash is only cast in the AI main phase. The agent currently keeps all cards on top when it scries.

A targeted real-deck seed-3 diagnostic of Faeries versus Kolodin completed ten turns each: Bitterbloom Bearer created eight upkeep Faeries, and Obyra triggered on four of the later entries. See examples/faerie-upkeep-replay.html. All six non-mirror pairings were also rerun; examples/faerie-upkeep-pool-summary.json contains the resulting life totals. These diagnostics are incomplete and do not change any training checkpoints or the live golem.

### Oracle cause-and-effect grammar

[Oracle grammar](rules/oracle-grammar.md) documents the new reusable trigger,
filter, effect and continuous-bonus nodes. Eight previous card-specific behaviors
now execute from parsed Oracle text. Unknown remainders reject the whole program;
renamed cards and altered types/amounts are covered by regression tests. More
specialized legacy handlers remain to be migrated. Review questions now expose
the parsed nodes, while full-game eligibility remains blocked.

### Seed-242 question-driven play tests

[Question log](rules/questions-242.md) records the six-match batch, 95 encountered
unsupported cards, the generic anthem grammar added in response, and remaining
mana, token-event and zone-change work. Before/after summaries are committed in
`examples/questions-242.json`. Parsing Liege's text does not enable its unsupported
hybrid cost. There are now 84 regression checks.

### Generic counters and keyword grants

Entry-trigger effects can now put a parsed number of +1/+1 counters on each
controlled creature. Continuous effects can grant one supported combat keyword
to creatures filtered by controller, color and “other.” Cathars' Crusade and
Bloodmark Mentor use these generic paths. There are 87 regression checks;
`examples/counter-keyword-242.json` records the rerun of the six deck pairings.

### Generic token spell parsing

Fixed creature-token instructions now parse quantity, stats, colors, subtypes,
keywords and tapped status instead of assuming red 1/1 Goblins. Complete-text
validation keeps additional unsupported abilities blocked. See
[rules/oracle-grammar.md](rules/oracle-grammar.md) for scope and remaining token
work. There are 89 regression checks and a new six-pairing seed-342 summary.

### Entry token triggers

Self-entry token triggers now compose generic event filters with TokenSpec.
Goblin Instigator no longer has a name-specific implementation. Tokens are created
at resolution, with the trigger's controller and parsed characteristics. There
are 90 regression checks and a six-pairing seed-442 diagnostic summary. Repeating
token engines, replacement effects and general stack timing remain flagged.

### Generic upkeep follow-up

Upkeep token engines now compile from Oracle text rather than Bitterblossom/Bitterbloom card names. Parsed mandatory life loss and token creation finish together before game-loss checks; new entry triggers follow afterward. Conditions and optional payments remain unsupported. Validation: 92 tests and six distinct real-deck pairings (seeds 542–547), capped at ten turns per player; four reached the cap and two ended earlier with a winner. See `examples/upkeep-542.json` and `rules/oracle-grammar.md`. This is diagnostic rules coverage, not learned strategy.

### Generic death-effect follow-up

Death triggers now compose with fixed self-death token creation, scry, and counters through the common effect interpreter. Tests cover source departure, controller ownership, surviving recipients, hidden library information, and completing token batches before lethal entry triggers. Validation: 96 tests; seeds 642–647 ran six distinct real-deck pairings (four full ten-turn windows, two nine-turn wins). See `examples/death-effects-642.json`. These are rules diagnostics, not learned strategy.

### Hybrid mana follow-up

Ordinary two-color hybrid costs now work through the shared Java payment planner and diagnostic importer, including a focused Glen Elendra Liege cast. Payments backtrack across available sources without spending a source twice and retain commander tax. Validation: Java mana checks and 96 Python tests pass; all six distinct pairings at seeds 742–747 reached ten turns per player without runtime questions. See `examples/hybrid-mana-742.json`. Sol Ring, floating pools, and other unsupported cost types still need implementation.

### Mana pools and fixed mana artifacts

The Python diagnostic now parses unconditional fixed-output mana artifacts, including Sol Ring, and retains unused mana until the step/phase ends. Colorless can pay generic or colorless requirements. Cast logs record mana sources and the remaining pool. All 102 tests pass, including 250 comparisons with the Java single-mana planner. Seeds 842–847 ran six unique deck pairings with no new runtime questions; Sol Ring was cast three times. See `examples/mana-pool-842.json`. The live Java actions still need pool integration, and X-card decisions/effects remain unsupported even though selected-X payment is tested.

### Chosen-X sorceries

The diagnostic now chooses and logs X for whole-text token creation, draw, and life-gain sorceries. Goblin Offensive works through this reusable grammar. Fixed costs, repeated X symbols, X=0, and Sol Ring leftovers are tested. All 108 tests pass. Seeds 942–947 produced five complete ten-turn windows and one earlier win, with no runtime questions; no X spell was cast in that random batch. Direct coverage is recorded in `examples/x-focused.json` and the tests. `examples/x-spells-942.json` contains the batch summary. Other X-card abilities remain flagged; live golem integration is still pending.

### Land-creature tokens

Awaken the Woods now works through the generic X/token grammar. Land-creature tokens preserve types, gain basic-land-type mana abilities, and obey summoning sickness and haste. Payment and X-budget enumeration share source discovery. All 112 tests pass, including a focused cast and next-turn mana payment. Seeds 1042–1047 produced six matches without runtime questions, but none cast Awaken the Woods; see `examples/land-tokens-1042.json`. This is diagnostic simulator support, not live golem integration.

## Opening seven, friendly mulligans and tempo rule (2026-10-29)

The simulator deals opening hands as **seven cards at once** (one
`opening_hand` event, rather than seven separate draw actions).
Each agent privately inspects its seven for **three or four lands**
and **two distinct proactive spells costing at most three mana**
that could both be played in the first three turns. The evaluator
checks color requirements, lands entering tapped and whether two spells
would overspend the same turn's mana. Target-dependent cards like
removal and Auras are not treated as dependable first-turn development.

Rejected hands are **shuffled back into the library in full** and
replaced with **seven fresh cards, with no penalty**. To prevent a deck
with impossible opening criteria from looping forever, the simulator
permits up to **16 free redraws**, then keeps the last seven. The
public replay logs each redraw and keep decision; private hand-analysis
scores are not serialized. Both-hand identities remain restricted to
the explicitly omniscient diagnostic spectator replay.

The main-phase agent also receives a modest bonus for legal proactive
development rather than passing through an otherwise empty turn.
This is not a mandatory cast rule and does not override mana, legality
or strongly negative action utilities. These are experimental simulator
policies, not changes to official Commander mulligan rules.

**Opening hand fallback:** after six free redrawn hands, an opening with
2–5 lands and at least one mana-payable early development spell may be kept.
The ideal remains 3–4 lands and two distinct spells on a three-turn
schedule; this relaxed rule prevents unrealistic 16-mulligan loops in
partially supported decks.


## Additional unseen Oracle programs: blink controller and flashback (2026-10-29)

The experimental diagnostic now accepts the **complete** one-instruction
instant pattern "Exile target creature you control, then return it/that card
to the battlefield under your/its owner's control", with optional standalone
**Rebound**. A parsed return destination keeps a creature's *physical owner*
distinct from its new *controller*. This supports **Cloudshift** without
hard-coding the card's name, and retains **Ephemerate**'s existing
owner-return/rebound behavior. Legal targeting, temporary state reset, new
object identity and token non-return use the existing blink implementation.

A reusable token-sorcery pattern now composes fixed-characteristic
"Create ..." with a standalone **Flashback {mana cost}** line. The full
printed cost is used from hand; the flashback cost is paid when casting
from the controller's graveyard at sorcery timing. The same physical card
moves to exile after resolution or if countered, and cannot flash back
again from exile. Legal graveyard casts are included in the agent's
decision candidates. **Chatter of the Squirrel** and renamed/token-variant
fixtures exercise this grammar. Additional unrecognized instructions
reject the *whole* program instead of being silently ignored.

These are deliberately narrow, testable rule families: flashback
on other spell-effect families, delayed blink, optional targets,
alternate casting timing, multiplayer control replacement, and arbitrary
Oracle language remain unsupported. Matches are diagnostic only and
do not change the live Minecraft golem or training eligibility.

Regression tests: `tests/test_blink_variants.py` and
`tests/test_flashback.py`.
