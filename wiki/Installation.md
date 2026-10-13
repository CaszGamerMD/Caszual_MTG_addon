# Installation

## Requirements

Caszual MTG 0.12.0 requires:

- Minecraft **26.2**
- Fabric Loader **0.19.3+**
- Fabric API **0.161.0+26.2+**
- Java **25+**
- MTGCard **1.7.0-26.2**

## Install

1. Install Fabric for Minecraft 26.2.
2. Put MTGCard, Fabric API, and `caszual-mtg-0.12.0.jar` in the `mods` folder.
3. Install the same mod versions on the server and on every player client.
4. Restart Minecraft/server.

Remove any old `mtgcompanion-*.jar` and older Caszual MTG jars from the mods folder; install only the new `caszual-mtg-0.12.0.jar`. The mod ID and block/item IDs have changed to `caszual_mtg`, and content placed under the old ID is not migrated. MTGCard itself is still required.

## Creative tab

Caszual MTG places its functional blocks/items into Minecraft's **Functional Blocks** creative tab:

- Community Land Catalogue
- Community Token Catalogue
- Community Card Collection
- Deck Builder
- Card Counter
- MTG Staff
- Custom Deckbox
- Card Hand
- Deckbox Rack
- Staff Rack

See [Recipes](Recipes.md) for survival crafting.

## Optional Caszual Additions integration

Install **Caszual Additions 0.1.1 or newer** alongside Caszual MTG to use the shared Caszual Creative tab and **Barrel of Caszual Fun**. All ten addon items are provided through the cross-mod `caszual_additions:caszual_content` item tag. The barrel is creative-mode only; reopen an existing one to discover newly installed items. Caszual MTG does not require Caszual Additions to run.

## Automatic Deck Builder requirements (0.12.0)

For automated Archidekt URL builds, keep an MTGCard deckbox in the Builder output slot, or place one directly adjacent. Land/Token/Community databases are scanned within four blocks. Put a real MTGCard Card Store within four blocks to receive missing-card shopping lists. A slotted deckbox transfers to the Card Store output when that slot is empty, even if the build was complete; an adjacent placed deckbox does not transfer. The Builder block must be present and its chunk loaded/ticking for background progress; the initiating player may close the GUI or disconnect. Purchasing the saved Card Store cart remains a manual action.
