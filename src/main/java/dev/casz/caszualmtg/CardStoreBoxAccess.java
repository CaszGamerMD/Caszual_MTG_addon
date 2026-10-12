package dev.casz.caszualmtg;

import net.minecraft.world.item.ItemStack;

/** Access to the Card Store's dedicated MTGCard deckbox slot. */
public interface CardStoreBoxAccess {
 ItemStack caszual$getDeckbox();
 void caszual$setDeckbox(ItemStack stack);
}
