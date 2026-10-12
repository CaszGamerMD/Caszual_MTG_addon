# Custom Deckbox

The **Custom Deckbox** is a normal MTGCard-compatible deckbox with a player-selected panel material.

It retains MTGCard's normal deckbox storage and opening behavior. Caszual MTG only changes the exterior panel appearance and preserves the selected material when the box is broken and placed again.

## Changing the material

1. Place the Custom Deckbox.
2. Hold a vanilla or modded **BlockItem** whose appearance you want.
3. **Sneak-right-click** the placed deckbox.

The main deckbox panels switch to that block's representative texture.

- Survival consumes one block when the material actually changes.
- Creative does not consume the block.
- Reapplying the same material does not consume another block.
- Normal right-click opens the deckbox.

After a material change the block schedules a follow-up tick, resynchronizes the deckbox, and requests a client render refresh so the appearance updates immediately.

## What is copied

Copied:

- representative block texture;
- resource-pack replacement for that texture.

Not copied:

- block shape;
- connected-texture behavior;
- lighting;
- animations/logic;
- physical properties.

Blocks with multiple different faces use a representative texture rather than reproducing every face.

The normal MTGCard dark edging/front detailing stays intact.

## Persistence and integration

The chosen material is stored with the deckbox item/block.

The Custom Deckbox works anywhere an MTGCard deckbox is expected, including:

- Community Card Collection bulk transfer;
- adjacent Deck Builder output;
- normal MTGCard card storage.

The item tooltip shows the currently selected texture material.

## Placed commander card artwork (0.11.0)

Place a custom deckbox with a commander card inside its designated commander slot. When the box is **closed and placed**, the top surface displays the actual artwork of that commander in a small frame. Opening the box hides the display until it closes. It never changes the deckbox's inventory icon or its custom block-texture panels. Standard MTGCard deckboxes receive the same feature.

The artwork uses MTGCard's existing artwork downloads/cache. The deckbox must have a commander card; older Caszual Builder decks that used the first side slot are also supported.
