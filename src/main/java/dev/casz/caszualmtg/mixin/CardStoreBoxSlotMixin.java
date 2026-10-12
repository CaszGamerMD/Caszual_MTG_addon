package dev.casz.caszualmtg.mixin;

import com.spider.mtgcard.cardstore.CardStoreScreenHandler;
import com.spider.mtgcard.cardstore.CardStoreBlockEntity;
import com.spider.mtgcard.deckbox.DeckboxBlockItem;
import dev.casz.caszualmtg.CardStoreBoxInventory;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.Container;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Adds a synced 37th slot, next to the player inventory, to MTGCard's Card Store. */
@Mixin(CardStoreScreenHandler.class)
public abstract class CardStoreBoxSlotMixin {
 @Inject(method="<init>(ILnet/minecraft/world/entity/player/Inventory;Lcom/spider/mtgcard/cardstore/CardStoreScreenHandler$OpenData;)V",at=@At("TAIL"))
 private void caszual$addBoxSlot(int sync,Inventory inv,CardStoreScreenHandler.OpenData data,CallbackInfo ci){
  Container target=inv.player.level().getBlockEntity(data.blockPos()) instanceof CardStoreBlockEntity be
      ?new CardStoreBoxInventory(be):new SimpleContainer(1);
  ((MenuSlotInvoker)(Object)this).caszual$addSlot(new Slot(target,0,190,154){
   @Override public boolean mayPlace(ItemStack stack){return stack.getItem() instanceof DeckboxBlockItem;}
   @Override public int getMaxStackSize(){return 1;}
  });
 }
}
