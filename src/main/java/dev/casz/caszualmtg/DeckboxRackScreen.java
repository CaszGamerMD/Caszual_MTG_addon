package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Inventory;

public final class DeckboxRackScreen extends LegacyContainerScreen<DeckboxRackMenu> {
 public DeckboxRackScreen(DeckboxRackMenu menu,Inventory inv,Component title){super(menu,inv,title,206,246);}
 @Override protected void init(){super.init();addRenderableWidget(Button.builder(Component.literal("Done"),b->onClose()).bounds(leftPos+125,topPos+219,68,20).build());}
 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){
  int x=leftPos,y=topPos;
  g.fill(x,y,x+206,y+246,0xFF182335);
  g.drawString(font,"Deckbox Rack · 5 slots",x+12,y+12,0xFFEAD9B2);
  g.drawString(font,"Store / take deckboxes",x+12,y+32,0xFFB3DFFF);
  for(var slot:menu.slots){g.fill(x+slot.x-1,y+slot.y-1,x+slot.x+17,y+slot.y+17,0xFFB0A0A0);g.fill(x+slot.x,y+slot.y,x+slot.x+16,y+slot.y+16,0xFF27364D);}
  g.drawString(font,"Inventory",x+12,y+110,0xFFB3DFFF);
  g.drawString(font,"Rack retains contents when mined",x+12,y+218,0xFF9CADC6);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}
}
