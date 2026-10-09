# Card Counter

The **Card Counter** edits named counters on placed MTGCard card displays.

## Use

Right-click a placed MTG card with the Card Counter to open the counter UI.

You can:

- enter a counter name;
- set its exact total;
- use **+1** and **−1** on an existing counter;
- set/remove a counter by setting its value to 0.

Examples:

- +1/+1
- loyalty
- charge
- poison-like custom labels

## Limits

- Up to **16 named counter types per card**.
- Counter values from 0 to **1,000,000**.

Counters are stored using MTGCard's card counter metadata.

## HUD

When looking at a placed card that has counters, Caszual MTG displays a readable HUD with:

- card name;
- counter names;
- exact totals.

Hidden MTGCard cards continue to obey MTGCard's visibility rules.

## World markers

Placed cards can also show counter markers directly on the card. Marker visuals are capped for readability while the HUD preserves the exact numerical total.
