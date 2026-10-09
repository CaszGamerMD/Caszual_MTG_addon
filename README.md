# Caszual MTG 0.7.0 — expanded test build

## Documentation

The current feature wiki/documentation is maintained in [`wiki/Home.md`](wiki/Home.md). It covers installation, recipes, every block/item, Deck Builder behavior, Card Hand mulligans/privacy, the Custom Deckbox, Card Counter, MTG Staff, UI controls, multiplayer/storage behavior, and troubleshooting.

A separate addon for Minecraft **26.2 Fabric**, built against **MTGCard 1.7.0-26.2**.

## Install

Put `caszual-mtg-0.7.0.jar` in the `mods` folder on both the server and every player's client, replacing any old `mtgcompanion-*.jar`. Keep MTGCard installed. Requires Java 25, Fabric Loader 0.19.3 or newer, and Fabric API 0.161.0+26.2 or newer. Restart Minecraft/server.

## What's new in 0.7.0

- Card Hand: fixed the missing block-atlas card-back texture with fully opaque pixel art; all 20 visual card-count stages use the correct texture.
- Card Hand: **Deposit inventory cards** transfers regular MTG cards to the Hand, respecting the 100-card maximum.
- Card Hand: multi-select any number of cards (including **Select all** / **Clear**) and take them together; prevents the transfer if insufficient inventory slots are free.
- Community Card Collection: **Deposit inventory cards** and a **Loose** card input slot now accept individual regular MTG cards without a deckbox. Lands/tokens stay separate; undeposited slot contents are returned upon closing.

## Blocks and counter tool

All four database/builder blocks are in the Functional Blocks creative tab and have survival recipes. Database/builder recipe: iron/glass/iron, redstone/centre/redstone, iron/iron/iron. Centre: green dye for lands, yellow dye for tokens, purple dye for community cards, crafting table for the builder. Counter recipe: iron nugget/redstone/iron nugget, then redstone underneath the middle.

- **Community Land Catalogue:** green. Search names or Scryfall queries, select a card, choose quantity, then Take selected. **All lands / Basics / Nonbasics** tabs keep basic lands easy to reach, and **Full art** restricts results to full-art printings. White, Blue, Black, Red, Green and Colorless toggles filter the mana a land can produce. Only Commander-legal lands are shown. Selecting colors restricts both color identity and produced mana: Green alone excludes White/Green dual lands; Green + White permits them. A land must produce at least one selected mana type and cannot produce an unselected colored mana type. Colorless production is allowed alongside selected colors. This also excludes flexible any-color producers unless all their produced colors are selected. All clears the color restriction. Infinite free copies, without depositing or owning a card first.
- **Community Token Catalogue:** gold. Same search/withdraw controls, restricted to cards with Token in their type line. Emblems and other token-like objects are excluded. Optional Oracle text and Power/toughness fields combine with the name search; leave either blank to skip it. Power/toughness uses numeric values such as `1/1` or `2/2`. Infinite free copies, without depositing first.
- **Community Card Collection:** purple. Insert an MTGCard deckbox into the dedicated slot, or shift-click it from your inventory. Deposit contents moves regular cards into the shared collection while leaving lands, tokens, and other items in the box. Select a card and choose a quantity, then Selected into box withdraws available copies into empty main slots. Fill box from search takes matching stored cards until the box is full. Take to inventory withdraws the selected card directly. Withdrawals consume actual shared stock; they never create free regular cards. Closing returns the deckbox to your inventory (or drops it by you if the inventory is full).
- **Deck Builder:** blue. Place any database blocks within four blocks in each direction. Place an empty MTGCard deckbox directly against any face of the builder. The builder shows the linked database kinds when checking the list. You can also paste an **Archidekt deck URL** and import it directly; only cards in the main deck are imported. Sideboard and Maybeboard entries are ignored. Archidekt printing/set information is preserved when available. **Public and unlisted decks are supported** when Archidekt allows anonymous access to the deck URL; private decks are not supported because the addon does not store or request Archidekt login credentials. A failed URL import leaves the currently loaded deck untouched.
- **Card Counter:** right-click a placed MTGCard card with this tool. Set a named total, select a counter to use +1/−1, or set zero/remove to delete it. Supports up to 16 named counter types per card and totals up to 1,000,000. When looking at a placed card, a readable HUD shows its counter labels and totals. Uses MTGCard's existing counter metadata. Visible markers sit directly on the placed card and grow into piles as counter totals increase. Each counter type contributes up to 12 visible markers, with up to six types represented; exact totals remain in the HUD. Default markers are provided when no MTGCard counter icon was selected. Hidden cards retain MTGCard's normal visibility rules.


## Card Hand

The **Card Hand** block links to the nearest MTGCard Deck Control within 8 blocks. The player who places it becomes the owner and can add or remove online players from its viewer list. Hand card data is sent only to authorized viewers unless **Reveal to all** is enabled.

Once linked, normal Deck Control draws — including redstone draws — are routed into the Hand instead of being ejected into the world. If no linked Hand is available, MTGCard's normal draw behavior remains unchanged. The Hand holds up to 100 cards.

The Deck Control gains **Discard Random from Hand**. It chooses a card server-side and sends it into the MTGCard Graveyard touching the Deck Control. The Hand screen has the same random-discard action. If the Graveyard is missing or full, no card is removed.

## Grid view and artwork

All three databases have a List/Grid toggle. The choice is shared by every Caszual MTG card browser and remembered between sessions. Grid shows enlarged cards four across; scroll to see more, and select a tile for the larger side preview. The community grid shows the actual printings available in shared stock.

In the land or token database, select a card and click **Choose artwork**. Alternate artwork choices open in a grid for that same card. Select a printing, set the quantity, then **Take selected** to receive that printing. Previous/Next browse artwork pages; **Back to search** returns to the original filters. New artwork choices require an online search; saved matching choices remain available if that search fails.

## Custom Deckbox

The Custom Deckbox uses MTGCard's normal box shape, opening model, dark brown edging and gold front details. Only the main panel texture changes, in the world and on the inventory item.

Craft it with glass, gold ingots and a chest, using the normal deckbox pattern:

```text
Glass  Gold   Glass
Gold   Chest  Gold
Glass  Gold   Glass
```

Place the box, hold the block whose texture you want, then **sneak-right-click the box**. Applying a different material consumes one block in survival; creative mode does not consume it. Reapplying the same material does not consume another block. Normal right-click opens the deckbox.

Vanilla and modded BlockItems can supply the material. The panels use the block's representative texture, including resource-pack replacements. Blocks with several face textures use one representative texture on the panels; their shape, light emission, and other behavior are not copied. The original edging and front details remain supplied by MTGCard.

The texture is saved with the placed box and its item, and survives breaking and placing it again. Its cards continue to use MTGCard's normal persistent deckbox storage. It works as the deck builder's adjacent output and in the community database's bulk-transfer slot. The item's tooltip names the selected material.

Each database kind shares one collection across the entire server and all dimensions. Breaking a database block does not delete the collection. Replacing the block gives access to it again. All players have deposit/withdraw access; this first version has no per-player permissions or contribution ownership.

## Larger previews in containers

Hover over a card in a chest, inventory, or other standard container screen and **hold V**. **Press F while holding V** to flip between faces. Release V to return. The container stays open and the card is never picked up. Hidden cards are not revealed by this preview. These are fixed keys in this version.

## Decklists and missing-card files

Use Import .txt, drag a `.txt` file onto the builder screen, or Paste list. Example:

```text
1 Ghave, Guru of Spores
1 Sol Ring
1 Command Tower
10 Forest
10 Plains
10 Swamp
```

Both `4 Card Name` and `4x Card Name` work, as do name-only lines. Duplicate names are combined. Arena/Moxfield suffixes such as `(CMM) 396` are removed. Blank lines and # comments are ignored. Commander/Deck/Mainboard headers are accepted; Sideboard/Maybeboard and subsequent lines are excluded. Text files must be UTF-8 and at most 24 KB; imports are limited to 500 cards.

**First = commander** is ON initially. Put your commander first; turn this option OFF for ordinary decks. With it on, the first available copy of the first listed card goes in MTGCard's first special slot, provided it is commander-legal. The deckbox has 99 main slots. This build supports one commander, not automatic partner/sideboard assignment.

After import, every card name appears immediately. Availability checks update an icon beside each entry: green check for all copies available, amber partial icon for some copies, red cross for none, and an ellipsis while checking. Rows show available/requested quantities, and missing cards remain visible. The screen also reports requested, available and missing totals. Select an available row to preview its card. **Build complete** requires all requested copies. **Build available** assembles a partial deck. Both require an empty adjacent deckbox. Community stock is withdrawn during assembly; lands/tokens do not consume stock. Rechecking before building uses current shared quantities, including other players' withdrawals. When a decklist specifies a set and collector number, the builder prefers that exact printing. If only another printing of the same card exists, it remains usable but the row is marked **alternate art**.

**Shop missing** sends the currently missing cards to a nearby MTGCard Card Store (within four blocks of the Deck Builder). Matching cards are resolved, added to that player's saved store cart, and the store menu opens. A missing or unreachable Card Store produces an in-game message. This prepares the cart; it does not submit or purchase an order automatically.

## Catalogue and matching details

Online catalogue searches use Scryfall through an asynchronous server request. The server needs internet access to discover new cards. Previously discovered land/token templates are saved with the world and can be used offline. Online results are paged, up to 40 unique cards per page; empty search lists the category. Community search is local by name/type. Card images use MTGCard's own image cache.

Deck matching uses normalized exact names across printings, with apostrophe and whitespace normalization. It does not require a particular set, collector number, or foil treatment. Custom cards already deposited can be matched by their displayed name. Land/token names missing from the saved catalogue are resolved using MTGCard's online name service during import; ambiguous tokens may need to be searched in the token catalogue first. Regular missing cards are never generated.

The community collections are stored in the overworld SavedData file for this addon. MTGCard handles deckbox storage. Keep normal world backups.

## Validation and limits

The Java build and parser checks pass. Dedicated-server integration checks cover storage, bulk deckbox transfers, strict token classification, mana metadata, deck availability and missing-card networking. A headless client bootstrap loads both entrypoints, the community screen, and the transformed placed-card renderer; marker growth and its visual cap pass. See VALIDATION.md. Actual screen appearance, mouse interactions and live online search still need in-game testing. Treat 0.7.0 as a test build.

## 0.6.1: MTGCard block entity validation crash safeguard

Caszual MTG no longer invokes MTGCard's block-entity initialization itself. On normal mod initialization, it verifies MTGCard's registered Deckbox types (including `warped_deckbox`) and Card Store block-entity types recognize their own registered blocks. Any missing valid-block associations are repaired in place without replacing native entities or altering inventories.

This addresses the reported `Invalid block entity mtgcard:deckbox` errors seen by Jade and `Invalid block entity mtgcard:card_store` exceptions during interactions. The regression harness also checks actual server-side block-entity creation for a Warped Deckbox and Card Store. Back up your world and update **both client and server** to 0.6.1. A full client/modpack recreation of the user's issue has not yet been performed.

## Source build

The source zip does not redistribute MTGCard. Put your `MtgCard-fabric-1.7.0-26.2.jar` into the source project's `libs` directory. With Java 25 installed, run `gradlew.bat build` on Windows or `./gradlew build` on Linux/macOS. Output is in `build/libs`. Gradle downloads Fabric/Minecraft dependencies on the first build.

## Retained startup fix

Moved the client container accessor into `dev.casz.caszualmtg.mixin`, separate from all regular addon classes. This fixes the client IllegalClassLoadError caused by Mixin reserving the main addon package. Remove older Caszual MTG jars before installing 0.6.1. Update both clients and server together: this version changes the search network messages and retains the custom deckbox and material component.
