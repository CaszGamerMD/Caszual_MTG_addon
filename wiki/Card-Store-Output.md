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
