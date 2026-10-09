# MTG Staff

The **MTG Staff** is a multiplayer target-declaration tool.

## Controls

While holding the staff:

- **Left-click an entity/card display** → mark it with a **white** highlight.
- **Right-click an entity/card display** → mark it with an **orange/gold** highlight.
- **Right-click empty air** → clear the highlights created by your staff.

The targeting hooks include MTGCard's custom placed-card entities so target declaration does not simply rotate/break the card.

## Multiplayer visibility

Highlights are applied server-side and are visible to other players.

Target assignments are tracked per staff user. If multiple players target the same entity, clearing one player's staff targets does not blindly erase another player's remaining assignment.

## Held pose

Holding the MTG Staff changes the holder's arm pose to an extended, nearly horizontal staff stance. The 3D staff is lengthened downward to visually approach the ground and uses:

- a dark wooden shaft;
- an amethyst-block-textured head.

The item has a dedicated first-person, third-person, GUI and ground transform.
