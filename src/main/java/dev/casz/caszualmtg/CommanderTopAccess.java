package dev.casz.caszualmtg;

import net.minecraft.world.item.ItemStack;

/**
 * A display-only view of the commander stored in a *placed* MTGCard deckbox.
 * It is not an inventory and never grants access to other deckbox slots.
 */
public interface CommanderTopAccess {
 ItemStack caszual$commanderForDisplay();
}
