# MTG Tabletop — multiplayer play surface (experimental)

## Place seats and link your equipment

Each MTG Tabletop block is one seat. Blocks touching at the same height connect; up to 32 tiles share a game. Open the seat you want to claim. Each seat keeps its battlefield cards and owner in the world save.

To play with cards, put your **Card Hand** within eight blocks of your seat. In the Card Hand, **Link Deck Control** by right-clicking your Deck Control; draw, scry, mill and commander interactions use that existing MTGCard setup. An MTGCard **Graveyard** adjoining the Deck Control is used for graveyard and exile storage.

In the Card Hand UI, use **Link Life Point**, then right-click your MTGCard Life Point block (within eight blocks of your Hand). Each tabletop player can link a separate Life Point. This reads live health and turn status from the existing MTGCard group system — no duplicate scoreboard. **Pass Turn** works for the currently active player in a started Life Point game, using MTGCard's regular group progression.

The Card Hand UI also has a **#RRGGBB table color** setting. The tabletop UI uses the full color, and the block in the world uses the closest of 16 wool colors.

## Play screen

- **Player tabs:** buttons along the top switch the battlefield currently shown. Each shows the player's life total (when linked) and a turn indicator for the active player. The private Hand tray stays yours even when viewing an opponent's field. Opponent hands are never transmitted to the tabletop screen.
- **Large battlefield:** almost the entire screen above the Hand is dedicated to a single player's field. The **Hand**, **GY**, **Exile**, and temporary **Scry** trays each use only a single row as tall as a card.
- **Drag and drop:** drag a card from your private Hand, Graveyard or Exile tray and release it anywhere on the selected battlefield. Drag your existing cards to reposition them. Click a played card to select it for Tap, Flip, To Hand, To GY, Exile Card, or Cmd Zone actions.
- **Commander slot:** the area just left of your Hand tray shows the card from MTGCard's actual **Deckbox Commander slot** (second side slot, #100). Drag to play it. **Cmd Zone** returns a commander originally played from that slot if the slot is empty. The corresponding deckbox item is consumed/restored, not duplicated.
- **Library actions:** Draw, Draw 7, Scry 1/3, Mill/5 and Shuffle route through the linked Deck Control. Scry is kept private until resolved. The deck counter shows the actual remaining cards.
- **World appearance:** a block with cards on its battlefield displays up to four tiny generic, face-down card markers. These are intentionally not legible actual card art. Card identities stay in saved server data and the tabletop GUI.

## Limitations

Still experimental: no full stack/priority engine, card-specific rules, team-specific commander targeting, or drag-to-cross-tab automatic seat switching. Seat ownership is persistent; it is not yet transferable from within the UI. Full multiplayer in-game QA is recommended before a long Commander session. The current world model shows approximate card count rather than card-accurate layout.
