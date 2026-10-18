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

**This prototype cannot yet play full Commander.** It currently does *not* resolve or cast spells, pay mana, maintain the stack or priority, respond to opponents, attack or block, apply damage, make card-specific choices, process triggers or replacement effects, handle mulligans or command-zone changes, or complete multiplayer turn-based rules enforcement. The rule-model methods for tax and combat damage are not integrated into gameplay. Partner/Background commanders and special deck exceptions are unsupported. Unknown actions are **not** silently allowed.

The goal for the next stage is a server-authoritative legal-action enumerator and game state machine (priority windows, mana costs, zones, targeting, combat), followed by deterministic AI scoring. Start with a constrained beginner deck and test under survival multiplayer with backups.

## Development

Run `./gradlew clean build` with Java 25. The Gradle `check` task includes `verifyCommanderGolem`; the branch's GitHub Actions workflow also builds and uploads test artifacts. This is an experimental branch only; do **not** merge it into `main` until the rules and game integration are verified.
