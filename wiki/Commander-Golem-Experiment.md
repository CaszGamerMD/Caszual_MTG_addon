# Commander Golem — experimental prototype

This page documents a **work-in-progress Commander opponent** on the `experiment/commander-ai-golem` branch. It **does not yet implement the complete Magic Comprehensive Rules**; do not use it as a rules referee or with valued physical inventories.

## Setup — explicitly linked Card Hand

1. Place a **Caszual MTG Tabletop** with an unclaimed seat immediately beside a **Caszual MTG chair**.
2. Place a **Commander Golem** item on the chair. It now appears as a small, original **Brass Squire–inspired copper-and-green-eyed voxel robot**, with an oversized domed head and sword. The underlying golem is invisible but retains its normal interaction hitbox and seat ownership.
3. Place an empty **Card Hand** close to the table. **New Hands start unlinked, with no primary gameplay player.** The person placing it is its manager, not automatically its primary.
4. Right-click the Hand and select **Links / Primary**, then **Link all — first of each**. Close the UI and right-click the first Deck Control, Life Point and MTG Table you want linked, in **any order**, all within eight blocks of the Hand. The first of each device type is saved and later clicks of that type work normally. This mode closes after all three links are set. Individual link buttons, Clear all links, and Cancel link mode are also available.
5. Reopen **Links / Primary**. Click **Select Golem — click it**, close the screen, and right-click the seated Golem. This explicitly sets the Hand's primary identity to the Golem UUID. For a human Hand instead, type an **online player's exact username** and select **Set Primary Player**. The original manager can still adjust links and sharing even if the golem/player is primary.
6. Put a physical deckbox next to the dedicated Deck Control; load 99 main-deck cards and an eligible commander in its Commander slot. Place the linked Life Point in the same MTGCard play group as the humans and start at 40 life.
7. Right-click the Golem to view its status. Check the Hand's three links and selected primary if it is still waiting.

Existing, previously saved Hands retain their administrative owner and legacy tabletop discovery until you explicitly relink them; newly placed Hands do not auto-discover or auto-claim nearby devices. No Hand may be silently stolen by the golem. Keep a player within 32 blocks for AI testing; no chunks are force-loaded.

**Visual model:** the copper/brass 3D body is a custom item model carried by a synchronized, non-interactive ItemDisplay. On reload, it is restored if missing, and detached old displays are cleaned up. The original iron golem remains the server-side NPC for player clicks, rather than replacing it with another kind of mob.

## Pod connection, turn order and card draws

The Commander Golem participates through **MTGCard's real Life Point pod**, not an independent timer. Its Card Hand must have explicit links to **the Golem's MTG Table seat, a Deck Control with an adjacent deckbox, and the Golem's own Life Point counter**, and the Hand's primary identity must be that particular golem.

1. Set up the human players' Life Point counters in a single MTGCard pod (play group).
2. Set up the Golem's Card Hand in **Links / Primary**, assign **Select Golem**, and link **MTG Table**, **Life Point**, and **Deck Control**. Keep its deckbox adjacent to its Deck Control, with 99 main-deck cards plus one legal commander.
3. Choose **Connect to nearby Pod** in the Hand setup screen (or right-click the Golem). If there is exactly one pod belonging to another seat on the connected table, and that pod has not started, the golem's linked Life Point will be added to its turn order. If multiple pods or a started pod exist, use MTGCard's Life Point pod menu to select the correct one manually.
4. Before game start, the Golem shuffles its real Deck Control library and draws seven cards into its own Card Hand **once**. Start the MTGCard pod normally. The Golem waits for the starting-player selection animation to finish, then acts only when **its actual pod Life Point** occupies the active turn index.
5. At the start of each Golem turn, the server untaps its battlefield cards and takes exactly one library card into its Hand. It tries a land drop, simple supported creature spells paid with its own untapped mana lands, and a commander creature when legal in the narrow experimental rules subset. It passes using MTGCard's normal pod progression or pauses for a human combat response. An empty deckbox commander slot after casting no longer stops later turns or draws.

**Troubleshooting:** Right-click the Golem to see pod name, member count, turn state, life, cards in Hand, and library size. If no pod is detected, use **Connect to nearby Pod** before starting the game. A saved Card Hand that still points to an unrelated player or table will not be hijacked by the Golem. Verify the Deck Control is linked to a physical deckbox and that the Golem's starting deck is a supported 100-card Commander deck.

**Limitations:** The golem is still an experimental simple-card pilot; it cannot play arbitrary Commander cards, respond through the full stack/priority system, or use all Magic mechanics. Real in-game complete-pod testing remains outstanding.

## Current first-pass automation

- Persistent, scaled-down, stationary iron golem; real adjacent tabletop seat and dedicated Card Hand/deckbox.
- Refuses to use player Hands or table seats not explicitly linked and assigned to its own golem identity.
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


## Turn/card support update (0.12.1)

The AI now recognizes balanced parenthetical reminder text without discarding actual ability clauses. Basic-land reminders and named unconditional enters-tapped lands are understood. Missing mana costs are rejected; only explicit zero costs are treated as free.

During its main phase the golem can also pay for whole-text, untargeted draw (one through seven cards) and simple lifegain instants/sorceries. Physical spell cards move to the adjacent Graveyard; mana sources tap, drawn cards enter the private Hand, and lifegain updates the linked Life Point. A missing/full Graveyard or insufficient hand/library space prevents the action. Unsupported additional clauses, targets, variable costs and drawbacks are never ignored. Draw spells can supply creatures for the same main phase.

This remains an automatic-resolution prototype, with no priority/response stack. It does not understand arbitrary Oracle text, triggers, replacement effects, activated abilities or all Commander rules. Parser checks are not a real multiplayer game acceptance test.
