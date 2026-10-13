package dev.casz.caszualmtg;

import com.spider.mtgcard.cardstore.CardStoreScreenHandler;
import com.spider.mtgcard.client.gui.CardStoreScreen;
import dev.casz.caszualmtg.mixin.ContainerAccess;
import dev.casz.caszualmtg.mixin.MenuSlotPositionAccessor;
import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.Component;
import net.minecraft.world.inventory.Slot;

/**
 * Places the injected Card Store deckbox slot in a labeled right-sidebar row,
 * above MTGCard's Buy/Clear Cart controls and completely outside its inventory.
 * Uses live widget positions, so dynamic GUI scaling cannot displace the slot.
 */
public final class CardStoreDeckboxLayout {
 private CardStoreDeckboxLayout(){}
 public static final int SLOT_INDEX=36;

 public static void arrange(CardStoreScreen screen){
  CardStoreScreenHandler menu=screen.getMenu();
  if(menu.slots.size()<=SLOT_INDEX)return;
  ContainerAccess access=(ContainerAccess)screen;
  int invX=access.companion$getLeftPos()+CardStoreScreenHandler.MARGIN+8;
  int invY=access.companion$getTopPos()+240-CardStoreScreenHandler.MARGIN-CardStoreScreenHandler.INV_BLOCK_H;

  // MTGCard creates these widgets in both tabs. The earliest purchase button
  // provides an anchor that works with 1x and 2x fullscreen widget scaling.
  int buyY=invY-56;
  for(var child:screen.children()){
   if(child instanceof Button button&&button.getMessage().getString().equals("Buy")){
    buyY=button.getY();break;
   }
  }
  // Dedicated 18px display line, 6px before the Buy button, never in the
  // main 9x4 inventory grid or overlaying the native store action buttons.
  int screenX=invX+4;
  int screenY=buyY-25;
  Slot slot=menu.slots.get(SLOT_INDEX);
  ((MenuSlotPositionAccessor)(Object)slot).caszual$setX(screenX-access.companion$getLeftPos());
  ((MenuSlotPositionAccessor)(Object)slot).caszual$setY(screenY-access.companion$getTopPos());
 }

 public static int screenSlotX(CardStoreScreen screen){
  ContainerAccess c=(ContainerAccess)screen;
  return c.companion$getLeftPos()+screen.getMenu().slots.get(SLOT_INDEX).x;
 }
 public static int screenSlotY(CardStoreScreen screen){
  ContainerAccess c=(ContainerAccess)screen;
  return c.companion$getTopPos()+screen.getMenu().slots.get(SLOT_INDEX).y;
 }
}
