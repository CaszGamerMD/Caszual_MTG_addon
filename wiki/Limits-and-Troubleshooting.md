# Limits and Troubleshooting

## Current limits

### Deck Builder

- Maximum parsed deck size: **500 cards**.
- One automatic commander slot through **First = commander**.
- Deckbox main area is 99 cards when the first card is used as commander.
- Sideboard and Maybeboard are ignored.
- Private Archidekt decks are unsupported.
- Database blocks/Card Store must be within 4 blocks of the Deck Builder.
- Output deckbox must directly touch the Deck Builder and be empty.

### Card Hand

- Maximum **100 cards**.
- Deck Control link must be explicitly selected and within the Hand's link range.
- One Deck Control cannot be claimed by two Hands.
- Random/strict graveyard discards require an MTGCard Graveyard touching the linked Deck Control.

### Catalogue

- Online discovery requires server internet access to Scryfall.
- Results are paged.
- Saved/discovered entries can provide fallback results when online search fails.

### Counter

- Maximum 16 counter types per card.
- Maximum counter value 1,000,000.

## Common problems

### Land/token search shows no new cards

Check that the server can reach Scryfall. Previously saved catalogue entries may still appear even if online discovery is unavailable.

### Archidekt import fails

Confirm:

- URL is a normal `archidekt.com/decks/<id>/...` deck URL;
- deck is public or accessible without login;
- Archidekt is not temporarily rate-limiting requests.

### Deck Builder says a card is missing

Make sure the appropriate database type is within 4 blocks. Regular cards must actually exist in Community Card Collection stock. Lands/tokens can be generated only when their relevant catalogue is linked/discovered.

### Shop missing cannot find a store

Place an actual **MTGCard Card Store block** within 4 blocks of the Deck Builder.

### Deck Builder cannot output

Place an empty MTGCard-compatible deckbox directly against any face of the Deck Builder.

### Card Hand draw does not route

Open the Hand, press **Link Deck Control**, then right-click the exact Deck Control. Verify the Hand is not full.

### Card Hand discard fails

A Graveyard must directly touch the linked Deck Control and must have room.

### Custom Deckbox material did not change

Sneak-right-click the placed Custom Deckbox with a BlockItem. The current implementation schedules a deckbox tick and client render refresh after a confirmed material change.

### Crash on startup: MouseTweaksGuiContainerHandlerMixin was loaded too early

This names a **MTGCard** optional Mouse Tweaks integration mixin, not a Caszual MTG mixin. MTGCard's compatibility plugin may load the Mouse Tweaks handler before the mixin is applied. See [the safe local JAR workaround](../docs/MTGCARD_MOUSE_TWEAKS_FIX.md); it creates a patched copy of your official MTGCard 1.7.0-26.2 JAR while preserving the original. The native fix must be made upstream in MTGCard.

## Version mismatch

Caszual MTG 0.6.0 targets Minecraft 26.2 and MTGCard 1.7.0-26.2. Use matching client/server jars and remove older Caszual MTG copies.
