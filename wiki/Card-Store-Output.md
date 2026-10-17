# Card Store deckbox output

Caszual MTG adds a dedicated **Deckbox output** inventory slot to MTGCard's existing Card Store GUI.

## How to use

1. Open the normal MTGCard Card Store.
2. Insert one MTGCard deckbox (including a Caszual Custom Deckbox) into the extra **Deckbox output** slot, next to the player inventory.
3. Add cards to the cart and purchase normally.
4. Printed cards are delivered directly into free main slots in the inserted deckbox, keeping the deckbox's MTGCard storage identity and contents.
5. Remove the deckbox after printing to move it to your inventory or a five-box rack.

If the deckbox fills up, the store tries the buyer's free inventory slots and then falls back to MTGCard's existing adjacent-deckbox or front-ejection behavior. Purchases should never silently disappear just because the output box is full.

The output slot and its deckbox are saved with the Card Store block entity, so closing the store GUI does not remove the box. If you mine the Card Store, the inserted deckbox drops so you can recover it. This feature depends on Caszual MTG being installed on both server and client.

**Note:** The dedicated slot affects card delivery, not the Card Store's prices, cart, or purchasing behavior.

## Refined output slot position (0.11.4)

The additional Card Store deckbox slot now appears in the **right-hand panel near the player inventory, immediately above the native purchase buttons**, with a matching **Deckbox output** label. Unlike the earlier fixed-offset position, it follows the Card Store's own fullscreen GUI layout when Minecraft GUI scale or window dimensions change. Item delivery behavior is unchanged.

## Print / deckbox status indicator

A status bar at the bottom of the open Card Store UI reports the server's real print progress every half-second. It distinguishes:

- **Yellow — Loading deckbox / printing:** the purchase is being processed, with the count of cards successfully inserted into the slotted deckbox
- **Green — Done:** the store has finished printing; the bar displays how many cards reached the deckbox
- **Red — Deck box full:** at least one card could not fit into the inserted deckbox, so MTGCard's player-inventory/adjacent-deckbox/world-output fallbacks are used instead; the indicator also shows the overflow count

The final completion or overflow result remains visible for approximately **three seconds**, then returns to an idle/ready state. This is server-synchronized and still finishes correctly if the player closes the UI while printing.
