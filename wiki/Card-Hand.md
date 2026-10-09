# Card Hand

The **Card Hand** is a podium-style block that stores up to **100 MTG cards** and integrates directly with an MTGCard Deck Control.

## Ownership and privacy

The first player to place/use the Hand becomes its owner.

The owner can:

- add online players to the viewer list;
- remove viewers;
- choose which Deck Control is linked.

Authorized viewers can see the actual cards in the Hand. Unauthorized players only see that the Hand is private.

**Reveal to all** makes the contents visible to everyone. Authorized Hand players can toggle reveal mode.

Card identities are not sent to unauthorized viewers.

## Linking to Deck Control

Linking is explicit so multiple nearby Deck Controls do not get mixed up.

1. Open the Card Hand.
2. Press **Link Deck Control**.
3. The Hand screen closes and link-selection mode is armed.
4. Right-click the exact Deck Control to use.

The selected Deck Control must be within the Hand's 8-block link range. A Deck Control already claimed by another Hand cannot be claimed again.

## Adding and taking cards

### Add

Right-click the Hand podium while holding an MTG card. One card is inserted into the Hand if you are authorized and space is available.

### Take

Open the Hand, select a card, and press **Take selected**. The card is returned to your inventory (or dropped if inventory insertion fails).

If strict-mulligan discards are pending, taking cards out is blocked until those discards are completed.

## Deck Control draw routing

When linked, normal Deck Control draws are routed directly into the Card Hand instead of being ejected into the world.

This includes redstone-triggered Deck Control draws.

If the Hand reaches 100 cards, further linked draws are consumed without removing another card from the library.

## World visualizer

The podium displays only face-down MTG card backs:

- **0–13 cards:** individual face-down cards are shown on the top surface.
- **14+ cards:** the display becomes a growing face-down stack.

This is only a count visualization; it does not reveal the cards' identities.

## Random discard

The Hand screen provides **Random → Graveyard**. The linked Deck Control also gains a **Discard Random from Hand** action.

Requirements:

- linked Deck Control exists;
- an MTGCard Graveyard is touching the Deck Control;
- the Graveyard has an empty graveyard slot.

The card is chosen server-side. If requirements are not met, no Hand card is removed.

## Mulligans

Press **Mulligan** to show:

- **Friendly**
- **Strict**
- **Cancel**

### Friendly

- return all Hand cards to the linked library;
- shuffle;
- draw 7 new cards into the Hand;
- reset strict-mulligan tracking.

### Strict

Each Strict press:

- returns the current Hand to the library;
- shuffles;
- draws 7;
- increments the strict mulligan count.

### Cancel / finish strict sequence

Cancel ends the current mulligan sequence. The Hand then requires:

`strict presses - 1` selected-card discards.

Examples:

- 1 strict mulligan → discard 0
- 2 strict mulligans → discard 1
- 3 strict mulligans → discard 2

Required discards are sent to the Graveyard touching the linked Deck Control. You choose the cards by selecting them in the Hand UI.
