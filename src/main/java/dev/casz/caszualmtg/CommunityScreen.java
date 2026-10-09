package dev.casz.caszualmtg;
import com.spider.mtgcard.client.compat.*;
import com.spider.mtgcard.util.TcgCardMeta;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.components.*;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Inventory;
import java.util.*;

/** Native inventory screen: the deckbox slot is synchronized by the menu protocol. */
public final class CommunityScreen extends LegacyContainerScreen<CommunityMenu> {
 Wire.Reply data;EditBox search,quantity;String query="",message="";boolean grid=ClientPrefs.grid();int selected=-1,scroll=0,page=0,face=0;long lastSend;
 public CommunityScreen(CommunityMenu menu,Inventory inventory,Component title){super(menu,inventory,title,640,430);}
 public void update(Wire.Reply reply){data=reply;selected=-1;scroll=0;message="";}
 @Override protected void init(){if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,640,430))return;super.init();button(grid?"List view":"Grid view",526,6,98,()->{query=search.getValue();grid=!grid;ClientPrefs.setGrid(grid);scroll=0;rebuildWidgets();});search=addRenderableWidget(new EditBox(font,leftPos+12,topPos+30,326,20,Component.literal("Search stored cards")));search.setMaxLength(200);search.setValue(query);button("Search",344,30,78,()->{page=0;query=search.getValue();send("search",query,0);});button("Deposit inventory cards",432,30,192,()->send("deposit_inventory","",0));
  button("Previous",12,292,78,()->{page=Math.max(0,page-1);query=search.getValue();send("search",query,page);});button("Next",96,292,62,()->{page++;query=search.getValue();send("search",query,page);});quantity=addRenderableWidget(new EditBox(font,leftPos+166,topPos+292,38,20,Component.literal("Quantity")));quantity.setValue("1");quantity.setMaxLength(2);
  button("Take to inventory",212,292,136,()->{if(chosen()!=null)send("withdraw",chosen().key(),amount());});
  button("Deposit loose card",470,278,154,()->send("deposit_loose","",0));
  button("Deposit contents",470,304,154,()->send("box_deposit","",0));button("Selected into box",470,330,154,()->{if(chosen()!=null)send("box_withdraw",chosen().key(),amount());});button("Fill box from search",470,356,154,()->send("box_fill","",99));button("Done",550,402,74,this::onClose);
 }
 @Override public void removed(){MtgGuiScaleHelper.restoreGuiScale(this);super.removed();}
 int amount(){try{int n=Integer.parseInt(quantity.getValue());if(n>=1&&n<=99)return n;}catch(NumberFormatException e){}message="Enter quantity 1–99.";return 0;}
 Wire.Row chosen(){return data!=null&&selected>=0&&selected<data.rows().size()?data.rows().get(selected):null;}
 void button(String label,int x,int y,int w,Runnable action){addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(leftPos+x,topPos+y,w,20).build());}
 void send(String action,String text,int count){if((action.equals("withdraw")||action.equals("box_withdraw")||action.equals("box_fill"))&&count<1)return;if(action.equals("withdraw")&&count>64){message="Inventory withdrawal limit is 64; deckbox limit is 99.";return;}long now=System.currentTimeMillis();if(now-lastSend<180)return;lastSend=now;ClientPlayNetworking.send(new Wire.Request(menu.pos,action,text,count));message="Working…";}
 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){int x=leftPos,y=topPos;g.fill(x,y,x+640,y+430,0xFF152032);g.drawString(font,title,x+12,y+12,0xFFFFFFFF);g.drawString(font,font.plainSubstrByWidth(data==null?"Loading shared collection…":data.message(),612),x+12,y+58,0xFFB3DFFF);
  if(data!=null)CardBrowser.render(g,font,data.rows(),x+12,y+76,412,212,scroll,selected,grid,false);
  var chosen=chosen();if(chosen!=null)CaszualMtgClient.art(g,chosen.card(),face,x+452,y+76,158,198);
  g.drawString(font,"Your inventory",x+12,y+305,0xFFB3DFFF);g.drawString(font,"Loose",x+400,y+286,0xFFB3DFFF);g.drawString(font,"Deckbox",x+400,y+308,0xFFB3DFFF);
  for(var slot:menu.slots){g.fill(x+slot.x-1,y+slot.y-1,x+slot.x+17,y+slot.y+17,0xFF91A5C1);g.fill(x+slot.x,y+slot.y,x+slot.x+16,y+slot.y+16,0xFF27364D);}
  g.drawString(font,"Closing returns un-deposited loose cards and the deckbox to you.",x+180,y+384,0xFF9CADC6);if(!message.isEmpty())g.drawString(font,font.plainSubstrByWidth(message,524),x+12,y+409,0xFFFFDA8A);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}
 @Override public boolean mouseClicked(MouseButtonEvent event,boolean twice){int at=CardBrowser.hit((int)event.x(),(int)event.y(),leftPos+12,topPos+76,412,212,scroll,data==null?0:data.rows().size(),grid);if(at>=0){selected=at;return true;}return super.mouseClicked(event,twice);}
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){if(mx>=leftPos+12&&mx<leftPos+424&&my>=topPos+76&&my<topPos+288){scroll=CardBrowser.clampScroll(scroll-(int)Math.signum(dy)*(grid?4:3),data==null?0:data.rows().size(),412,212,grid);return true;}return super.mouseScrolled(mx,my,dx,dy);}
}
