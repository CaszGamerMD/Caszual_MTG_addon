# MTG Tabletop — multiplayer play surface (experimental)

## Place seats and link your equipment

Each MTG Tabletop block is one seat. Blocks touching at the same height connect; up to 32 tiles share a game. Open the seat you want to claim. Each seat keeps its battlefield cards and owner in the world save.

To play with cards, put your **Card Hand** within eight blocks of your seat. In the Card Hand, **Link Deck Control** by right-clicking your Deck Control; draw, scry, mill and commander interactions use that existing MTGCard setup. An MTGCard **Graveyard** adjoining the Deck Control is used for graveyard and exile storage.

In the Card Hand UI, use **Link Life Point**, then right-click your MTGCard Life Point block (within eight blocks of your Hand). Each tabletop player can link a separate Life Point. This reads live health and turn status from the existing MTGCard group system — no duplicate scoreboard. **Pass Turn** works for the currently active player in a started Life Point game, using MTGCard's regular group progression.

The Card Hand UI also has a **#RRGGBB table color** setting. The tabletop UI uses the full color, and the playmat uses the exact 24-bit RGB value. The surrounding wood frame is independently customizable.

## Play screen

- **Player tabs:** buttons along the top switch the battlefield currently shown. Each shows the player's life total (when linked) and a turn indicator for the active player. The private Hand tray stays yours even when viewing an opponent's field. Opponent hands are never transmitted to the tabletop screen.
- **Large battlefield:** almost the entire screen above the Hand is dedicated to a single player's field. The **Hand**, **GY**, **Exile**, and temporary **Scry** trays each use only a single row as tall as a card.
- **Drag and drop:** drag a card from your private Hand, Graveyard or Exile tray and release it anywhere on the selected battlefield. Drag your existing cards to reposition them. Click a played card to tap or untap it; drag it to move. Use Flip on a selected card to change the physical face of a double-faced card (or conceal a single-faced card). Hold Alt over an eligible card to read it in an enlarged art preview.
- **Commander slot:** the area just left of your Hand tray shows the card from MTGCard's actual **Deckbox Commander slot** (second side slot, #100). Drag to play it. **Cmd Zone** returns a commander originally played from that slot if the slot is empty. The corresponding deckbox item is consumed/restored, not duplicated.
- **Draw ▾ menu:** Draw one, Draw X, Scry X, Mill X and friendly/strict mulligans. Enter X in the adjacent number field. Strict mulligans allow discarding owed cards via Discard mode; finish the mulligan before discarding.
- **Deck ▾ menu:** Shuffle the linked library, Search (open the linked deckbox), Reveal X, or RESET. Reveal shows the top X cards only to the player; send the top one to your Hand or drag it to the battlefield, then shuffle the unused revealed cards onto the bottom of the library. You can also return all revealed cards to the bottom.
- **RESET:** Requires confirmation. Collects the requesting player's cards from this connected battlefield, Card Hand, Graveyard and Exile back into their own deckbox, shuffles the library, and remembers/restores the commander to the Commander side slot. Reset pre-checks capacity; if there are not enough slots it leaves cards where they are and reports why. It does not move opponents' tabletop cards.
- **Library count:** The screen displays the linked Deck Control's remaining library count.
- **World appearance:** a wooden tabletop has an inset colored playmat, leaving a one-pixel wooden edge. A block with cards on its battlefield displays up to four tiny generic, face-down card markers above the mat. These are intentionally not legible actual card art. The playmat now uses a pure-white base texture tinted to the full #RRGGBB value rather than approximating it with one of sixteen wool colors.

## Material-driven wooden tables

The original `caszual_mtg:tabletop` block ID is retained to protect multiplayer seats, battlefield cards, owners, and commander references already saved in worlds. Its **frame wood** now stores the registry ID of the crafting material as a persistent item component and block-entity value. Existing tables without saved wood data default to dark oak.

Craft an MTG Tabletop using **five matching planks/logs/stripped wood blocks**, one green wool block, and two sticks:

```text
Wood   Wood        Wood
Wood   Green Wool  Wood
Stick  (empty)     Stick
```

Wood choices use the same vanilla/modded compatibility logic as chairs. The texture changes on the wooden top border, sides, and legs, while the colored felt mat and miniature card markers remain separate. Sneak-right-click an existing table with any eligible wood to swap its frame texture (consumes one block in survival). Pick-block and table drops preserve the selected wood.

## Wooden chairs

Chairs are now **material-driven**, like Caszual Additions' material-based storage models. Craft the single **Custom Wood Chair** using **six copies of the same wood block**, in the original 3×3 chair pattern `P  / PPP / P P`.

The recipe accepts **planks, logs, stripped logs, wood blocks, stems, stripped stems and hyphae**, including appropriately tagged or named modded wood blocks. The crafted chair remembers the exact block ID (for example `minecraft:oak_log`, `minecraft:stripped_oak_log` or `minecraft:oak_planks`) and uses that block's texture. Its inventory model and placed appearance follow the stored ID. Right-click the placed generic chair with a new wood block to reskin it, consuming one block in survival. Pick-block and drops preserve the wood data.

The twelve retired wood-specific chair IDs and their assets are now removed. Only `caszual_mtg:material_chair` remains. Back up your world and replace any old chair variants before upgrading: retired blocks already placed in a world will not resolve after removal.

Right-click a chair with:
- **Wool:** add a cushion matching the wool's color.
- **Leather:** add a brown leather cushion. Right-click again with a dye to recolor it.
- **Paper:** add an automatic playmat-matched cushion. When placed beside an MTG Tabletop at the same level, the cushion uses that table's exact #RRGGBB playmat color, including later changes from the linked Card Hand.

Chairs have a slab-height (8 pixel) seat. Right-click without upholstery material to sit; dismount normally to stand up. Cushions are currently consumed on application. Seat mounts are cleared when riders leave or when chairs are removed.

## Limitations

Still experimental: no full stack/priority engine, card-specific rules, team-specific commander targeting, or drag-to-cross-tab automatic seat switching. Seat ownership is persistent; it is not yet transferable from within the UI. Full multiplayer in-game QA is recommended before a long Commander session. The current world model shows approximate card count rather than card-accurate layout.

## Battlefield creature statistics and counters

Creature cards display a legible **power/toughness plaque** in the lower-right corner of the card, even if the card is tapped sideways. Double-faced cards use the active face's statistics, and numeric +1/+1 and −1/−1 counters adjust the displayed values. Hidden cards do not reveal their statistics.

**Right-click your own face-up battlefield card** to open its counter editor. Presets are available for +1/+1, −1/−1, loyalty, and charge, or type a custom counter name; use +1/−1, Set total or Remove. Counters are stored in the underlying MTG card data and display as compact stacked badges on the battlefield. Opponents cannot change counters on cards they do not own.

## Token tray

Use **Tokens ▾** at the top of the tabletop UI to open or close the token tray. The left column is your private set of **up to 32 stored token templates**. On the right, search the same shared token catalogue as the Caszual Token Database; previous results are available offline, and new Scryfall results load asynchronously. Select a search result and choose **Add selected** to store it. Select a saved token, then **Play selected** to create a copy on your active battlefield tile, or drag the token from the tray onto a battlefield position. The original template remains available for future plays.

The tray contents persist with your claimed tabletop seat; other players have their own trays. The tray can also accept one of your existing token cards from the battlefield using the **Return to tray** context action. Removing a template does not remove tokens already on the battlefield. When resetting a deck, token cards vanish from the battlefield without being erroneously shuffled into the library.

## Quick-send from battlefield

**Shift + right-click** one of your battlefield cards to return it to the appropriate zone without opening the counter editor. Commanders (including cards matching the seat's remembered commander) return to the linked deckbox Command Zone, tokens return to your persistent Token Tray, and other cards go to the linked Graveyard. The server checks card ownership and destination capacity before removing the card, so a missing/occupied Commander slot, a full Token Tray or an unavailable/full Graveyard leaves the card on the battlefield. Normal right-click continues to open the counter editor.

## Temporary token copies and token-search improvements

Right-click one of your face-up battlefield cards and select **Create Token Copy**. A new token copy appears beside that card with the same card art and printed characteristics but no copied counters. Copies have a **TOKEN COPY** label. They may be tapped, moved or given new counters while on the battlefield, but when moved to the hand, graveyard, exile or token tray they cease to exist, rather than becoming a permanent deck or tray card. Reset also removes them without restoring them to the library or command zone.

The token drawer now automatically searches when opened. Token search results are displayed directly from the token catalogue (eight per page), so you no longer depend on the global token cache being populated first. Search pagination is aligned with the catalogue's 40-card batches; the global cache remains an offline fallback. Select a result and choose **Add selected** to save it into the tray, or select a saved template and drag/play it onto the battlefield.

## Counter cleanup when leaving the battlefield

Every MTG counter and counter-icon marker is cleared when a card actually **leaves the battlefield**, including return to hand, graveyard, exile, the commander slot, the token tray, deck reset, and cards dropped by breaking the table. The removal preserves the card's identity, face, artwork and unrelated metadata. Moves or taps within the battlefield retain counters. If a destination is full or unavailable, no move occurs and the battlefield counters remain intact.

The Scry screen's **Cancel** action also works without a linked Card Hand and discards the scry selection without changing the library order.

## Free positioning and confirmed private-hand zone changes

Cards dragged across the battlefield now keep the point at which they were grabbed rather than snapping their top-left corners to the mouse. Their saved normalized coordinates remain precise and are not quantized to any grid.

To send a card from **Hand** to **GY** or **Exile**, first select the card and click the corresponding zone button. The screen then displays an explicit **CONFIRM GY** or **CONFIRM EXILE** and a **Cancel** button. The server checks the selected card identity, the destination and capacity before removing it from Hand. The existing To GY and Exile Card buttons still work directly for cards already on the battlefield.

**Reveal Hand** toggles your private cards' visibility to other players at your connected tabletop until you turn it off. While revealed, the hand tray has a conspicuous **red border and warning text**. Other players can switch to your seat tab to inspect and scroll through a read-only copy of your visible cards; they cannot move your cards. Cards are never sent to opponents unless you expressly opt in, and snapshots are only included in connected tabletop replies.

## On-table revealed hands and battlefield zoom

When someone enables **Reveal Hand**, a prominent red-framed strip appears **directly on that person's own battlefield tab**, for everyone at the connected table (including the owner). Its cards can be viewed and Alt-enlarged but not manipulated by opponents. When the owner hides their hand, the strip and public data disappear. Their seat tab is highlighted red while revealed; the owner also keeps the red warning around their own private hand tray. Wheel-scrolling the strip shows additional cards.

**Mouse-wheel over your own battlefield** to scale all cards on that table together in five-percent increments from **45% to 180%** of the original size. This per-seat setting is persisted in the world and shared to all viewers, so everyone's layout matches. The active size is displayed at the top-right of the board. Wheel-scrolling the private hand, token tray or a revealed-hand strip still scrolls those areas instead; other players cannot change your battlefield card size.

## Public deck reveals (not scry)

Using the tabletop **Reveal X** action on your Deck Control broadcasts the revealed card artworks and identities to **every player who is viewing the same connected table**. They appear in a gold-bordered strip on the revealing player's battlefield tab. Scroll over the strip to navigate a large reveal, or hold **Alt** to inspect a card. Everyone sees the live reveal until it is resolved (Top to Hand, Top to Field, or Rest to Bottom), at which point the public strip disappears. Other players cannot manipulate the revealed cards. **Scry stays private** and is never included in this public feed. Session validation checks the revealing seat's linked Deck Control before sharing anything.

## Custom Deck Control and Custom Graveyard

**Custom Deck Control** and **Custom Graveyard** are separate Caszual blocks in the creative tab. They reuse the *original MTGCard block entities*, so library order, shuffling, linked deckboxes, menus, 100-slot graveyard, 100-slot exile, hoppers and saved contents continue to use the native mechanics. Existing vanilla MTGCard blocks are not changed. Both devices retain the familiar MTGCard body/status details, with customizable wood trim: **sneak + use any placeable block on the device** to copy its material into the panels (including modded wood). As with Custom Deckbox, these material selections are saved in the world's block-entity data.

Craft the Custom Deck Control with a standard MTGCard stone Deck Control plus oak planks; craft the Custom Graveyard with a standard MTGCard Graveyard plus oak planks. These recipes convert **items**, not placed blocks containing cards. Do not break a filled device simply to change its look; use the material-selection interaction instead.
