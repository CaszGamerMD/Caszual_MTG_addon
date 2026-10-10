# MTG Staff

## Hex RGB glow colors (0.8.0)

The staff now supports any six-digit RGB hex value, e.g. `#22D3EE` and `#FF55A8`, for the two staff actions. No wool-block color sampling is needed.

1. Have a targeting staff anywhere in your inventory or offhand.
2. Open a Card Hand you are authorized to use.
3. On the right side of the screen, enter the **Left click** and **Right click** hex colors. The color swatches update as you type.
4. Press **Apply to all staffs**. The color presets are saved in the Hand Block, and all staffs in your inventory (including offhand) are updated at once.
5. New glow targets use the color stored on the held staff. Existing marks you own are refreshed when you apply colors.

The defaults are **#FFFFFF** (left click) and **#FFAA00** (right click). Invalid values cannot be applied. Presets persist in the Hand Block's saved data and on the staff item. When different players use the same Hand Block, applying its colors updates only the staffs belonging to the player who pressed the button.

All clients need this version of the addon for full-precision colors. The effect is visible as an outline and does not emit light.

The **MTG Staff** is a multiplayer target-declaration tool.

## Controls

While holding the staff:

- **Left-click an entity/card display** → mark it with a highlight using the staff's **left-click RGB color** (default white).
- **Right-click an entity/card display** → mark it with an highlight using the staff's **right-click RGB color** (default orange/gold).
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
