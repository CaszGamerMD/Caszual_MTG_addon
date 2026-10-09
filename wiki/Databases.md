# Databases

MTG Companion has three database/catalogue blocks. The Land and Token catalogues provide **unlimited free copies** of discovered cards; the Community Card Collection stores **real deposited stock**.

All custom database card browsers support **List/Grid** view and a larger selected-card preview. The List/Grid preference is shared across MTG Companion browsers and remembered client-side.

## Community Land Catalogue

The Land Catalogue searches Scryfall and caches discovered land templates into the world data.

### Search and filters

- Search by card name or Scryfall-style query.
- **All lands / Basics / Nonbasics** tabs.
- **Full art** filter.
- Mana-production filters for:
  - White
  - Blue
  - Black
  - Red
  - Green
  - Colorless
- **All** clears the mana restriction.
- Only **Commander-legal** lands are returned.

The color filter checks both color identity and mana the land can actually produce. For example, selecting only Green excludes White/Green duals and other lands that can produce an unselected colored mana type.

### Taking cards

Select a result, choose a quantity from 1–64, and press **Take selected**. Land copies are generated from the saved catalogue template and do not consume community stock. You need enough empty inventory slots because MTGCard cards receive individual identities and do not simply merge as a normal stack.

### Artwork picker

Select a land and press **Choose artwork**. MTG Companion searches alternate printings for the same card family. Artwork mode does not keep the normal Full Art filter, so alternate-art choices can include non-full-art printings. Select a printing and take it normally.

## Community Token Catalogue

The Token Catalogue works similarly to Lands, but searches MTG token cards.

### Filters

- Name/Scryfall search.
- Optional **Oracle text** search.
- Optional **Power/Toughness** in numeric form such as `1/1` or `2/2`.
- Artwork picker for alternate token printings.

It only accepts cards classified as tokens. Emblems and unrelated token-like objects are not treated as normal tokens.

Token copies are unlimited and free.

## Community Card Collection

This is the shared inventory for regular MTG cards.

Unlike Lands/Tokens, regular cards are **not generated**. They must be deposited first and withdrawals consume real shared stock.

### Direct card actions

- Search stored card names/types.
- Select a card and use **Take selected** to withdraw available copies to your inventory.
- Quantities cannot exceed stored stock.

### Deckbox bulk transfer

The Community Collection has a dedicated deckbox slot.

- Put an MTGCard deckbox or MTG Companion Custom Deckbox in the slot.
- **Deposit contents** moves regular cards into shared storage while leaving lands, tokens and non-card contents alone.
- **Selected into box** withdraws selected stored cards into empty deckbox main slots.
- **Fill box from search** fills the box with matching stored cards until space or stock runs out.
- Closing the screen returns the deckbox to your inventory; if your inventory is full it is dropped for you.

## Online/offline behavior

Land/token discovery requires the server to reach Scryfall. Previously discovered catalogue entries are saved and can still appear if the online search is unavailable.

Card images themselves use MTGCard's image/cache system.
