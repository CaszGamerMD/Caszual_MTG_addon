# MTG Tabletop (experimental)

A shared multiplayer card battlefield for **Minecraft 26.2 / Fabric**.

## Connect seats

Place MTG Tabletop blocks directly north, south, east or west of one another at the same height. Up to 32 connected tiles are presented in one interface. Each tile is an individual seat; opening an empty tile claims it for the player. The green felt surface joins into one large battlefield. Tile ownership and cards are saved to the world.

To play, the seat owner must place a **Card Hand** within eight blocks of their seat and link that Hand to an MTGCard **Deck Control** using the Card Hand's existing link command. An MTGCard **Graveyard** directly touching the Deck Control supplies the Graveyard and Exile zones. One block can be used alone as a single-player table.

## Controls

- The upper half shows the shared battlefield. Select a card from the lower Hand, then click any open area of the upper battlefield to place it.
- Select an already-played card, then click its new position. Only the card's owner can move, tap, turn face-down, return, graveyard or exile the card.
- The lower half contains **Hand**, **Graveyard**, **Exile** and temporary **Scry** tabs. A selected zone card can return to Hand or be placed onto the table.
- The sidebar displays the **real remaining library count**. Draw, mill, shuffle and scry buttons operate through the linked Deck Control. Draw deposits cards directly into the Card Hand. Mill deposits cards directly in Graveyard, refusing when there is insufficient room.
- Scry 1 or 3 shows the top cards **privately**. Click scry cards to mark them for the bottom; unmarked cards remain on top. Resolve preserves the order within each side. Cancel leaves the library unchanged.
- A card placed face-down is sent as a hidden placeholder to other players, never as the actual item data.
- Break a tile to drop all cards currently stored on it; each tile saves its cards and seat owner separately. Normal world backups preserve the game state.

**Experimental boundaries:** no custom turn engine, stack priority, counter automation, optional life totals, card rotation animations, selecting a new owner for an occupied seat, or per-opponent spectator permissions yet. Tabletop synchronization uses frequent server snapshots while open. The UI is designed for Minecraft 26.2 and still needs testing in-game on a multiplayer server.
