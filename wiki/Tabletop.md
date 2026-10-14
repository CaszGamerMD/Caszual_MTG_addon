# MTG Tabletop — multiplayer play surface (experimental)

## Place seats and link your equipment

Each MTG Tabletop block is one seat. Blocks touching at the same height connect; up to 32 tiles share a game. Open the seat you want to claim. Each seat keeps its battlefield cards and owner in the world save.

To play with cards, put your **Card Hand** within eight blocks of your seat. In the Card Hand, **Link Deck Control** by right-clicking your Deck Control; draw, scry, mill and commander interactions use that existing MTGCard setup. An MTGCard **Graveyard** adjoining the Deck Control is used for graveyard and exile storage.

In the Card Hand UI, use **Link Life Point**, then right-click your MTGCard Life Point block (within eight blocks of your Hand). Each tabletop player can link a separate Life Point. This reads live health and turn status from the existing MTGCard group system — no duplicate scoreboard. **Pass Turn** works for the currently active player in a started Life Point game, using MTGCard's regular group progression.

The Card Hand UI also has a **#RRGGBB table color** setting. The tabletop UI uses the full color, and the block in the world uses the closest of 16 wool colors.

## Play screen

- **Player tabs:** buttons along the top switch the battlefield currently shown. Each shows the player's life total (when linked) and a turn indicator for the active player. The private Hand tray stays yours even when viewing an opponent's field. Opponent hands are never transmitted to the tabletop screen.
- **Large battlefield:** almost the entire screen above the Hand is dedicated to a single player's field. The **Hand**, **GY**, **Exile**, and temporary **Scry** trays each use only a single row as tall as a card.
- **Drag and drop:** drag a card from your private Hand, Graveyard or Exile tray and release it anywhere on the selected battlefield. Drag your existing cards to reposition them. Click a played card to tap or untap it; drag it to move. Use Flip on a selected card to change the physical face of a double-faced card (or conceal a single-faced card). Hold Alt over an eligible card to read it in an enlarged art preview.
- **Commander slot:** the area just left of your Hand tray shows the card from MTGCard's actual **Deckbox Commander slot** (second side slot, #100). Drag to play it. **Cmd Zone** returns a commander originally played from that slot if the slot is empty. The corresponding deckbox item is consumed/restored, not duplicated.
- **Draw ▾ menu:** Draw one, Draw X, Scry X, Mill X and friendly/strict mulligans. Enter X in the adjacent number field. Strict mulligans allow discarding owed cards via Discard mode; finish the mulligan before discarding.
- **Deck ▾ menu:** Shuffle the linked library, Search (open the linked deckbox), Reveal X, or RESET. Reveal shows the top X cards only to the player; send the top one to your Hand or drag it to the battlefield, then shuffle the unused revealed cards onto the bottom of the library. You can also return all revealed cards to the bottom.
- **RESET:** Requires confirmation. Collects the requesting player's cards from this connected battlefield, Card Hand, Graveyard and Exile back into their own deckbox, shuffles the library, and remembers/restores the commander to the Commander side slot. Reset pre-checks capacity; if there are not enough slots it leaves cards where they are and reports why. It does not move opponents' tabletop cards.
- **Library count:** The screen displays the linked Deck Control's remaining library count.
- **World appearance:** a wooden tabletop has an inset colored playmat, leaving a one-pixel wooden edge. A block with cards on its battlefield displays up to four tiny generic, face-down card markers above the mat. These are intentionally not legible actual card art. The world playmat uses the closest of Minecraft's 16 wool colors to the Card Hand's full RGB setting.

## Wooden chairs

Twelve standard wood types are available: oak, spruce, birch, jungle, acacia, dark oak, mangrove, cherry, bamboo, crimson, warped and pale oak. Craft a chair from six matching planks in the pattern `P  / PPP / P P`. Right-click the placed chair with:

- **Wool:** add a cushion matching the wool's color.
- **Leather:** add a brown leather cushion. Right-click again with a dye to recolor it.
- **Paper:** add an automatic playmat-matched cushion. When placed beside an MTG Tabletop at the same level, the cushion follows that table's felt color, including later changes from the linked Card Hand.

Chairs have a slab-height (8 pixel) seat. Right-click without upholstery material to sit; dismount normally to stand up. Cushions are currently consumed on application. Seat mounts are cleared when riders leave or when chairs are removed.

## Limitations

Still experimental: no full stack/priority engine, card-specific rules, team-specific commander targeting, or drag-to-cross-tab automatic seat switching. Seat ownership is persistent; it is not yet transferable from within the UI. Full multiplayer in-game QA is recommended before a long Commander session. The current world model shows approximate card count rather than card-accurate layout.
