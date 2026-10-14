# Deckbox Rack

A two-model-pixel-thick, six-model-pixel-deep shelf which holds **five MTGCard deckboxes** and displays each as a small 3D model of its actual deckbox item.

## Placement

- Place on a floor to make a short shelf, or click the side of a block to mount it on a wall.
- Its shape and facing adapt to the clicked face.
- As of **0.11.3**, the supporting shelf is a slim **2-pixel-high, 6-pixel-deep wooden ledge**. The miniature deckboxes have been lowered an additional 0.75 model pixels so their bases meet the top surface visually, fully supported by the shelf in every rotation. The visible collision matches the narrower ledge, and the dark-oak trim meets the spruce plank without overlapping surfaces.
- Right-click with an MTGCard deckbox to insert it into the first open position.
- Right-click empty-handed to open its five-slot inventory and take or rearrange deckboxes. **Hover over each deckbox** for its normal item tooltip, including the deckbox name and applicable saved metadata.

The miniatures are genuine item/block models, including Custom Deckbox appearances (when their item model supports that material). They use the modern Minecraft block-entity render-state system rather than overlapping static proxy cubes.

## Breaking or moving

Mining the rack drops **one Deckbox Rack item containing its five stored deckboxes**. You can move it without emptying it; placing it again restores all five positions and their associated MTGCard external storage references. Back up the world as usual before major mod upgrades.

## Recipe

```text
Spruce Slab  Iron Bars  Spruce Slab
              Spruce Planks
```

## Card Store and Deck Builder

The Deck Builder and Card Store each have their **own deckbox slot** for directly receiving cards. Move a filled deckbox from either block to a rack to store it.

The new commander artwork preview appears **only on deckboxes placed in the world**. Miniature deckbox items displayed by this rack retain their normal item model.
