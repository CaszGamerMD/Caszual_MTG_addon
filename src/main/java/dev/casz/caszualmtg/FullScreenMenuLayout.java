package dev.casz.caszualmtg;

import dev.casz.caszualmtg.mixin.MenuSlotPositionAccessor;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.Slot;

/** Pixel-space geometry shared by the full-viewport Builder and Community screens. */
public final class FullScreenMenuLayout {
 public static final int MIN_WIDTH=640, MIN_HEIGHT=430;
 public static final int MARGIN=12;
 private FullScreenMenuLayout(){}

 public static int sidebarX(int width){return width-208;}
 public static int sidebarWidth(int width){return width-sidebarX(width)-MARGIN;}
 public static int browseWidth(int width){return sidebarX(width)-MARGIN-14;}
 public static int inventoryTop(int height){return height-98;}
 public static int inventoryLabelY(int height){return inventoryTop(height)-14;}
 public static int actionY(int height){return inventoryTop(height)-49;}
 public static int browseBottom(int height){return actionY(height)-9;}
 public static int browseHeight(int height,int top){return Math.max(1,browseBottom(height)-top);}
 public static int statusY(int height){return height-17;}

 /** Vanilla player inventory in menu order: three rows of 9, then hotbar row. */
 public static void positionInventory(AbstractContainerMenu menu,int first,int height){
  for(int i=0;i<36;i++){
   int px=MARGIN+(i%9)*18;
   int py=inventoryTop(height)+(i<27?(i/9)*18:58);
   position(menu.slots.get(first+i),px,py);
  }
 }
 public static void position(Slot slot,int x,int y){
  ((MenuSlotPositionAccessor)(Object)slot).caszual$setX(x);
  ((MenuSlotPositionAccessor)(Object)slot).caszual$setY(y);
 }
}
