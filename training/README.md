# Commander self-play deck intake

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
