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

The first runnable version provides a deterministic classroom sandbox. It reuses the mod's Java card parser, mana planner and damage resolver through a local subprocess. It does not duplicate those rules in Python. The two actual Commander decks remain blocked until their unsupported effects and the complete game backend are implemented. No live Minecraft entities are exercised by this tool.

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

Policies carry a sandbox scope marker and are not loaded into live golems. The actual supplied decks never enter this simplified sandbox. A fully legal engine remains the next required integration.

GitHub Actions runs the checks, audits both real decks, generates a public replay and exercises three generations. Download the `commander-training-review` artifact for HTML/JSON review files and checkpoint history. The regular mod check also runs the simulator's regression suite.


### Included review examples

- [Short completed sandbox replay](examples/short-sandbox-replay.html): a complete synthetic match with an eight-life start for a compact demonstration. This is separate from the 40-life training baseline.
- [Both real decks: rules questions](examples/deck-review.html): the initial 133-item audit with card text and answer-note controls.
- [First three-generation training report](examples/first-training-run.json): three self-play games and 48 paired evaluation games; all candidate policies tied the champion, so none was promoted.

Generated HTML embeds only the public replay and uses lossless packing to reduce file size. JSON reports retain the expanded, readable event format. CI validation runs start fresh; continuing a training campaign requires retaining its output directory, not just launching another CI run.
