# Commander Golem — experimental prototype

This page documents a **work-in-progress Commander opponent** on the `experiment/commander-ai-golem` branch. It **does not yet implement the complete Magic Comprehensive Rules**; do not use it as a rules referee or with valued physical inventories.

## Setup

1. Place a **Caszual MTG Tabletop** with an **unclaimed seat tile** immediately adjacent to a **Caszual MTG chair**.
2. Craft the **Commander Golem** (iron ingots, carved pumpkin, redstone), or take it from the functional creative tab. Use it on the chair to spawn the seated iron golem.
3. Place a **new, empty, unclaimed Card Hand** within five blocks of the table.
4. Place a **Deck Control** within three blocks of that Hand. Place or link a dedicated MTGCard deckbox to that control. **Do not use a human player's Deck Control/deckbox.**
5. Load exactly **99 main-deck cards** and **one eligible commander** in the deckbox's MTGCard Commander slot (slot 100). No partner pairing yet.
6. Place a dedicated MTGCard **Life Point** counter within five blocks of the table and name its display **Commander Golem**. Add that life counter to the same turn/play group as the human players, and start the game with 40 life.
7. Right-click the golem with an empty hand to see its status. The golem can reserve its own unclaimed Hand, link its Deck Control, and link the named Life Point when all resources are available.

Keep a player within 32 blocks while testing. AI decisions run on the server once a second around online players and do not force-load chunks.

## Current first-pass automation

- Persistent, scaled-down, stationary iron golem; real adjacent tabletop seat and dedicated Card Hand/deckbox.
- Refuses to use existing claimed player Hands or already-claimed table seats.
- Basic 100-card Commander deck size, singleton, and five-color identity checks; one commander; banned-card rejection when a card provides that legality metadata.
- Draws an opening seven into its own Hand, without publicly revealing the cards.
- Watches its designated Life Point's active turn, untaps its own tabletop cards, draws one, plays at most one land from hand, then passes turn.
- Exposes game status by interacting with the NPC. Opening-hand / turn state is persisted on the entity, avoiding repeated draws every server tick.
- Rule model groundwork for 40 starting life, one land play per turn, phases, commander tax, and 21 commander combat damage.

## Not yet implemented (intentionally disabled)

**This prototype cannot yet play full Commander.** It currently casts only a safe subset of simple creatures using basic one-mana sources and performs the limited defender-confirmed combat described below; it does *not* handle arbitrary spells, full mana rules, the stack or priority, triggered/replacement effects, advanced combat, partner commanders, complete mulligans, or all multiplayer rule exceptions. Commander tax is used for simple commander creature casts, but commander combat damage remains unsupported by the automated attacker. Partner/Background commanders and special deck exceptions are unsupported. Unknown actions are **not** silently allowed.

The goal for the next stage is a server-authoritative legal-action enumerator and game state machine (priority windows, mana costs, zones, targeting, combat), followed by deterministic AI scoring. Start with a constrained beginner deck and test under survival multiplayer with backups.

## Development

Run `./gradlew clean build` with Java 25. The Gradle `check` task includes `verifyCommanderGolem`; the branch's GitHub Actions workflow also builds and uploads test artifacts. This is an experimental branch only; do **not** merge it into `main` until the rules and game integration are verified.

## October 18 experimental tabletop updates

- The **Token Tray** now displays artwork thumbnails for stored and searched tokens. Hold **Alt** over a token result for a large preview.
- Search by **name**, **Oracle text contains**, and an exact numeric **P/T** such as `1/1`. Filters are applied to Scryfall results and cached catalogue fallback; invalid P/T input is rejected.
- **Target ▾** opens targeting mode. Select your own battlefield card as the source, change seat tabs if needed, then click a card to announce it as the target. **Target Player** targets the currently viewed seat, and **Clear Target** removes your declaration.
- Targets appear as red card borders / player-seat tabs, blue source highlights and public announcements; cards sharing a battlefield show a dotted target connector. Declarations expire after 20 seconds. All viewers poll the same server-authoritative markers.
- The golem now announces when it casts supported creature cards, using the same mechanism.
- **Important:** target indicators currently declare *intent*. They do not automatically validate or resolve spells, blocks, attacks, targets, priority, or the stack.

## Experimental attacking and blocking

The golem can now **declare one supported creature attack** against an online player who occupies another seat on its connected table and has a Life Point block in the same game group. The attack pauses its turn until the defender responds. The attacking card and defending player are highlighted for everyone; pending attacks survive server restarts.

To respond, open **Target ▾** on your table while you are the defender. Choose **Take Hit** to accept unblocked damage. To block, first click an untapped creature you control on your battlefield to select it as the source, then choose **Block Source**. The server checks flying/reach and simultaneous damage for its tiny supported subset, and refuses resolution when a required Graveyard is missing/full rather than deleting physical cards. After a resolution, the golem resumes and passes its turn.

**Experimental constraints:** one attacking non-commander creature and at most one blocking creature; only ordinary numeric P/T and recognized passive keywords (flying, reach, haste, vigilance, defender). Unsupported activated, triggered, replacement, prevention, first-strike, trample, deathtouch, lifelink and other effects are **not** interpreted. There is no functional stack/priority window or general targeting spell engine yet. This is **not** full legal Commander combat and is not suitable for competitive or valuable saved games.

## Full Commander readiness gate

The game is **not yet ready to be described as fully playable under the Magic Comprehensive Rules**. To close that gap, a real game/rules kernel must own all zones, the stack, priority, targeting legality, mana abilities, state-based actions, replacement effects, continuous effects, triggers, multiplayer combat, commander identity/damage, and the loss/win conditions. Human actions and golem actions should both be legal actions supplied by that same kernel; the visible Minecraft tabletop should be only the presentation/synchronization layer.

A credible candidate is the maintained open-source Java **Card-Forge/forge** project (`https://github.com/Card-Forge/forge`), which already plays Commander against its AI. However Forge is **GPL-3.0**, while this mod is **MIT**, so code/dependency distribution and the boundary of any separated rules companion must be reviewed before implementation. Do not simply copy or package Forge into this mod and silently retain MIT licensing.

An integration spike should first prove one deterministic **headless** two-player Commander match in the chosen rules engine, then bind each engine zone/card to a unique physical MTGCard item ID without duplication. Follow with a legal-action RPC boundary, serialized game snapshots/resume, human prompts for priority/target/block choices, 3–4-player testing, and replayable test fixtures for game completion. The current simple-card pilot can serve as a safe fallback, not as a substitute for the full engine.

### Test acceptance criteria (not yet met)

1. Play and finish 100 complete two-player matches with decks containing creatures, instants, sorceries, artifacts, enchantments, planeswalkers, activated/triggered abilities and removal.
2. Play 100 complete multiplayer Commander matches with priority passing, stack responses, combat, commander tax and 21 commander-damage elimination.
3. Verify player-private zones, card identity, undo/rollback on invalid actions, crash/restart recovery, token ownership, and no item loss or duplication.
4. Match observable resolutions against a trusted rules engine/reference; zero unexplained illegal transitions before shipping as a real opponent.

**Installation safety:** keep this experimental JAR and worlds separate from your normal multiplayer setup. Avoid valuable saved decks until a full integration/game-restart test passes.
