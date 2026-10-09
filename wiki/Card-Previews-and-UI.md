# Card Previews and UI

## Large preview in inventories/containers

In standard container screens such as inventories and chests:

- hover an MTG card;
- **hold V** to show a large card preview;
- while holding V, press **F** to switch card faces;
- release V to return to the normal container.

The container stays open and the card is not picked up.

Hidden MTGCard cards are not revealed by this preview.

These keys are fixed in the current version.

## List and Grid views

The Land Catalogue, Token Catalogue and Community Card browsers support a **List/Grid** toggle.

Grid view:

- shows larger card art;
- supports scrolling;
- lets you select a card for a larger preview.

The preference is saved client-side and shared between MTG Companion card browsers.

## GUI scaling

MTG Companion custom GUIs use a common enlarged scaling target:

- preferred Minecraft GUI scale **3**;
- common minimum layout target around **640×430**;
- controls and text are roughly 50% larger than the earlier default presentation;
- card grids reflow to use the available window rather than simply stretching empty space.

This applies to the catalogue/database screens, Deck Builder, Card Counter, Card Hand and Community Collection layout.
