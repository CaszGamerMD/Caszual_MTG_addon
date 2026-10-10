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

### Basic Full Art lands still show one printing each

Use **Caszual MTG 0.8.1** on the client and server. In the Land Catalogue, select **Basics** and **Full art**; the results now show different illustrations for the same land names. Choose a specific card and click **Choose artwork** to browse distinct Full Art alternatives. Use **Next** to explore beyond the first page. An active server connection to Scryfall is needed to retrieve new artwork.


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

### 0.6.1 startup exception: MTGCard block entities are not yet initialized

If Minecraft crashes during `caszual_mtg`'s `main` entrypoint with
`MTGCard's block entities are not yet initialized`, this is a **0.6.1
initialization-order regression**. Caszual MTG attempted to validate
MTGCard's registrations before MTGCard's own entrypoint had run.

**Fix:** install **Caszual MTG 0.6.2** on the client and server.
Validation is now delayed until after client/server initialization; if
MTGCard still has not registered its entities, the addon logs a warning
rather than terminating startup. No world edits or block replacement
are required.

### Error: Invalid block entity mtgcard:deckbox or mtgcard:card_store

**Caszual MTG 0.6.2** verifies that MTGCard's native Deckbox, Warped Deckbox, Card Store, and other native block-entity types recognize their registered block states. It repairs missing valid-block associations without replacing block entities, changing block IDs, or deleting card storage. It also stops Caszual MTG from calling MTGCard's block-entity init routine directly.

If Jade reports `Invalid block entity mtgcard:deckbox` or Minecraft crashes with `Invalid block entity mtgcard:card_store`, back up the world, replace older Caszual MTG JARs with **0.6.1 on both client and server**, and restart both. You do not need to break or replace the Deckbox or Card Store.

Jade may be the first mod to read the bad block entity but is not necessarily the cause. If the error continues after updating, send the full `latest.log` with mod versions; a different MTGCard version, an unregistered block, or a second mod interfering with registration may need a separate fix.

## Version mismatch

Caszual MTG 0.6.2 targets Minecraft 26.2 and MTGCard 1.7.0-26.2. Use matching client/server jars and remove older Caszual MTG copies.
