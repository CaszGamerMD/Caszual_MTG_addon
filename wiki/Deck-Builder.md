# Deck Builder

The Deck Builder assembles decklists from nearby MTG Companion databases and writes available cards into an adjacent MTGCard deckbox.

## Required layout

- Put Land, Token and/or Community Card database blocks within **4 blocks in each direction** of the Deck Builder.
- Put an **empty MTGCard deckbox** directly touching one of the six faces of the Deck Builder.
- A nearby MTGCard **Card Store** within 4 blocks can receive missing-card lists.

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
- Private decks are not supported because MTG Companion does not request or store Archidekt login credentials.
- A failed URL import does not replace the currently loaded list.

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

- The first available copy of the first decklist entry is placed in MTGCard's first commander/side slot.
- That card must be commander-legal.
- The deckbox then has 99 normal main slots, allowing a typical 100-card Commander deck.

Turn the option off for ordinary decks.

## Build buttons

- **Build complete** — refuses to build if anything is missing.
- **Build available** — builds the partial list using everything currently available.

Community Collection stock is consumed during build. Lands and tokens are catalogue-generated and do not reduce stock.

The output deckbox must be empty.

## Shop missing

After **Check cards**, press **Shop missing**.

MTG Companion finds the nearest real MTGCard **Card Store block within 4 blocks**, resolves the missing cards, saves them into that player's Card Store cart, and opens the store.

If the decklist specified a set/collector number, that printing is preferred for the store entry.

This prepares the in-game Card Store cart; it does not automatically purchase anything.
