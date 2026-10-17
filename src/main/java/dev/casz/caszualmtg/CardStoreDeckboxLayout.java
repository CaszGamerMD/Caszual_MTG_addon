package dev.casz.caszualmtg;

import com.spider.mtgcard.cardstore.CardStoreScreenHandler;
import com.spider.mtgcard.client.gui.CardStoreScreen;
import dev.casz.caszualmtg.mixin.ContainerAccess;
import dev.casz.caszualmtg.mixin.MenuSlotPositionAccessor;
import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.Component;
import net.minecraft.world.inventory.Slot;
import com.spider.mtgcard.client.compat.GuiGraphics;
import net.minecraft.client.gui.Font;
import java.util.WeakHashMap;
import java.util.Map;

/**
 * Places the injected Card Store deckbox slot in a labeled right-sidebar row,
 * above MTGCard's Buy/Clear Cart controls and completely outside its inventory.
 * Uses live widget positions, so dynamic GUI scaling cannot displace the slot.
 */
public final class CardStoreDeckboxLayout {
 private CardStoreDeckboxLayout(){}
 public static final int SLOT_INDEX=36;
 private static final Map<CardStoreScreen,CardStoreStatusWire.Progress> PROGRESS=new WeakHashMap<>();
 public static void updateProgress(CardStoreScreen screen,CardStoreStatusWire.Progress status){
  if(status.pos().equals(screen.getMenu().blockPos))PROGRESS.put(screen,status);
 }
 /** Visible beneath the store's controls, not on top of its Buy button. */
 public static void drawProgress(CardStoreScreen screen,GuiGraphics graphics,Font font){
  if(screen.getMenu().slots.size()<=SLOT_INDEX)return;
  CardStoreStatusWire.Progress status=PROGRESS.get(screen);
  boolean box=screen.getMenu().slots.get(SLOT_INDEX).hasItem();
  int phase=status==null?CardStoreStatusWire.Progress.IDLE:status.phase();
  String label;
  int textColor,barColor;
  switch(phase){
   case CardStoreStatusWire.Progress.PRINTING -> {
    label=!box?"Printing cards — no deckbox in slot"
     :status.total()<=0?"Processing purchase…"
     :"Loading deckbox: "+status.inserted()+"/"+status.total()+" cards";
    textColor=0xFFFFDE84;barColor=0xFF514022;
   }
   case CardStoreStatusWire.Progress.DONE -> {
    label=box?"✓ Done — "+status.inserted()+" cards moved into deckbox"
     :"✓ Printing finished — sent to regular output";
    textColor=0xFF95EEAF;barColor=0xFF1D4530;
   }
   case CardStoreStatusWire.Progress.FULL -> {
    label="! Deck box full: "+status.inserted()+" inserted, "+status.overflow()+" routed elsewhere";
    textColor=0xFFFF9494;barColor=0xFF51282A;
   }
   default -> {
    label=box?"Deckbox ready":"Insert a deckbox for direct card delivery";
    textColor=0xFFB9C9D8;barColor=0xFF26354B;
   }
  }
  int w=Math.min(310,Math.max(160,screen.width-24)),x=(screen.width-w)/2,y=screen.height-24;
  graphics.fill(x,y,x+w,y+17,barColor);
  graphics.drawCenteredString(font,font.plainSubstrByWidth(label,w-12),screen.width/2,y+5,textColor);
 }


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
