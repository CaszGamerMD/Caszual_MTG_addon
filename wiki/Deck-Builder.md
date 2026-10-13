# Deck Builder

The Deck Builder's front panel rotates to face the placing player; already-placed blocks retain their original orientation. The Deck Builder assembles decklists from nearby Caszual MTG databases and can scan, assemble, and shop cards automatically from an Archidekt URL.

## Required layout

- Put Land, Token and/or Community Card database blocks within **4 blocks in each direction** of the Deck Builder.
- Insert an MTGCard deckbox in the Builder's output slot, **or** place a deckbox directly adjacent to the Builder. Automatic URL jobs use the inserted box first, otherwise the adjacent box. Existing cards in the box are counted so they are not duplicated.
- A nearby MTGCard **Card Store** within 4 blocks automatically receives remaining card lines from a URL job. If the Builder has an inserted deckbox, the box transfers into the Store's output slot once it is empty.

The builder reports which database kinds it can currently see.

## Import methods

### Text file

Use **Import .txt** or drag a `.txt` file onto the Deck Builder screen.

### Paste list

Use **Paste list** to import from the clipboard.

Accepted examples:

```text
1 Ghave, Guru of Spores
1 Sol Ring
1 Command Tower
10 Forest
10 Plains
10 Swamp
```

Also accepted:

- `4 Card Name`
- `4x Card Name`
- Name-only lines
- Printing suffixes such as `1 Card Name (CMM) 396`
- Blank lines and comments beginning with `#` or `//`
- Commander/Deck/Mainboard headers

Sideboard and Maybeboard sections are ignored. Duplicate identical entries are combined. The parser is limited to **500 cards**.

### Archidekt

Paste a public or unlisted Archidekt deck URL into the URL field and press **Import URL**.

- Main deck only.
- Sideboard and Maybeboard ignored.
- Printing/set/collector information is preserved when Archidekt supplies it.
- Private decks are not supported because Caszual MTG does not request or store Archidekt login credentials.
- A failed URL import does not replace the currently loaded list.

## Automatic Import URL workflow (0.12.0)

After pressing **Import URL** once, the Deck Builder completes these stages automatically:

1. Fetch and save the public/unlisted Archidekt main-deck list (or use a successful six-hour cached list).
2. Scan the connected Land, Token and Community Card databases, resolving missing catalogue names online and storing available/requested status for every card in the Builder.
3. Load available cards into the **inserted deckbox**, or into a directly **adjacent placed deckbox** if the output slot is empty. Existing cards count toward the request; regular Community stock is consumed only after deckbox insertion succeeds. Remaining cards, including any that cannot fit, become the shop list.
4. Prepare the missing cards as a saved MTGCard Card Store cart for the player who started the import. If the output box was in the Builder's slot, transfer it into the Store's dedicated deckbox output slot for purchased cards. An adjacent placed deckbox stays where it is.

The player can **close the GUI or log off** after starting the job. The Builder itself runs the steps and records its stage and shopping list in its block data. Work resumes when its chunk is loaded/ticking, including after a server restart. If the Builder has no deckbox, or the Card Store cannot be found within four blocks, it waits and resumes automatically when the required block appears. If the Store's output already contains a deckbox, remove that box before the automatic handoff can finish.

**No purchases happen automatically.** The missing-card cart waits at the Card Store until you open it and confirm the purchase with normal MTGCard currency. Press **Reset** to cancel a pending job; Reset never ejects or empties a deckbox. For manual `.txt` builds, the original **Check cards**, **Build complete**, **Build available**, and **Shop missing** controls remain available.

## Saved drafts, URL cache and Reset

The Deck Builder now remembers the last successfully imported text or Archidekt URL, the resolved decklist, each card's availability, and the missing-card report **on that block**. Closing the UI does not interrupt a current Archidekt import or background land/name resolution, provided the builder still exists and the server remains running. Reopen it later to see the saved results.

For repeat imports, a successfully resolved Archidekt URL is cached for **six hours**. Opening the builder or selecting the same URL does not need to refetch everything. A failed new URL will leave your previous valid list intact.

Press **Reset** to erase the saved URL/list/results and cancel older background lookup results. Reset does **not** eject or empty the deckbox in the output slot. Removing the block does remove its draft but drops its inserted deckbox.

## Availability checking

After import, every deck entry is shown while availability is checked.

The builder matches against database kinds that are physically linked by proximity:

- Lands from the Land Catalogue.
- Tokens from the Token Catalogue.
- Regular cards from Community Card Collection stock.

Unknown land/token names are resolved asynchronously through MTGCard/Scryfall. Multiple unresolved names are processed concurrently rather than one-by-one.

When a decklist specifies an exact set + collector number, the builder prefers that printing. Another printing of the same name can still satisfy the card, but the row is marked **alternate art**.

## Commander option

**First = commander** is enabled by default.

When enabled:

- Automatic URL builds place a commander-legal first card in MTGCard's official commander slot (slot 100). Manual Build Complete/Available retains its existing behavior.
- That card must be commander-legal.
- The deckbox then has 99 normal main slots, allowing a typical 100-card Commander deck.

Turn the option off for ordinary decks.

## Build buttons

- **Build complete** — refuses to build if anything is missing.
- **Build available** — builds the partial list using everything currently available.

Community Collection stock is consumed during build. Lands and tokens are catalogue-generated and do not reduce stock.

For manual button-based builds, the output deckbox must be empty and stays in the Builder slot. Automatic URL builds may fill a partly filled box and transfer a slotted box to the Card Store if cards are missing.

## Shop missing

For manually imported text lists, press **Shop missing** after checking. Archidekt URL imports prepare the shopping cart automatically when necessary.

Caszual MTG finds the nearest real MTGCard **Card Store block within 4 blocks**, resolves the missing cards, saves them into that player's Card Store cart, and opens the store.

If the decklist specified a set/collector number, that printing is preferred for the store entry.

This prepares the in-game Card Store cart; it does not automatically purchase anything.

## Fullscreen interface (0.11.4)

The Deck Builder uses the full available window with a responsive card list on the left, an independent selected-card preview and **output deckbox slot** on the right, and inventory/hotbar at the bottom. Import, Reset, Check cards and Commander buttons remain across the top. The Build Complete / Build Available buttons sit below the list, never on top of inventory cells. The server-side cached decklist and background resolution features remain unchanged.
