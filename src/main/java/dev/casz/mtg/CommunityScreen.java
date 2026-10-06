package dev.casz.mtg;
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
 public CommunityScreen(CommunityMenu menu,Inventory inventory,Component title){super(menu,inventory,title,640,520);}
 public void update(Wire.Reply reply){data=reply;selected=-1;scroll=0;message="";}
 @Override protected void init(){if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,5,640,520))return;imageWidth=Math.max(640,width-16);imageHeight=Math.max(520,height-16);super.init();button(grid?"List view":"Grid view",imageWidth-114,6,98,()->{query=search.getValue();grid=!grid;ClientPrefs.setGrid(grid);scroll=0;rebuildWidgets();});search=addRenderableWidget(new EditBox(font,leftPos+12,topPos+30,326,20,Component.literal("Search stored cards")));search.setMaxLength(200);search.setValue(query);button("Search",344,30,78,()->{page=0;query=search.getValue();send("search",query,0);});
  button("Previous",12,382,78,()->{page=Math.max(0,page-1);query=search.getValue();send("search",query,page);});button("Next",96,382,62,()->{page++;query=search.getValue();send("search",query,page);});quantity=addRenderableWidget(new EditBox(font,leftPos+166,topPos+382,38,20,Component.literal("Quantity")));quantity.setValue("1");quantity.setMaxLength(2);
  button("Take to inventory",212,382,136,()->{if(chosen()!=null)send("withdraw",chosen().key(),amount());});
  button("Deposit contents",imageWidth-170,394,154,()->send("box_deposit","",0));button("Selected into box",imageWidth-170,420,154,()->{if(chosen()!=null)send("box_withdraw",chosen().key(),amount());});button("Fill box from search",imageWidth-170,446,154,()->send("box_fill","",99));button("Done",imageWidth-90,imageHeight-28,74,this::onClose);
 }
 @Override public void removed(){MtgGuiScaleHelper.restoreGuiScale(this);super.removed();}
 int amount(){try{int n=Integer.parseInt(quantity.getValue());if(n>=1&&n<=99)return n;}catch(NumberFormatException e){}message="Enter quantity 1–99.";return 0;}
 Wire.Row chosen(){return data!=null&&selected>=0&&selected<data.rows().size()?data.rows().get(selected):null;}
 void button(String label,int x,int y,int w,Runnable action){addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(leftPos+x,topPos+y,w,20).build());}
 void send(String action,String text,int count){if(!action.equals("search")&&!action.equals("box_deposit")&&count<1)return;if(action.equals("withdraw")&&count>64){message="Inventory withdrawal limit is 64; deckbox limit is 99.";return;}long now=System.currentTimeMillis();if(now-lastSend<180)return;lastSend=now;ClientPlayNetworking.send(new Wire.Request(menu.pos,action,text,count));message="Working…";}
 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){int x=leftPos,y=topPos;g.fill(x,y,x+imageWidth,y+imageHeight,0xFF152032);g.drawString(font,title,x+12,y+12,0xFFFFFFFF);g.drawString(font,font.plainSubstrByWidth(data==null?"Loading shared collection…":data.message(),imageWidth-28),x+12,y+58,0xFFB3DFFF);
  if(data!=null)CardBrowser.render(g,font,data.rows(),x+12,y+76,Math.max(412,imageWidth-228),302,scroll,selected,grid,false);
  var chosen=chosen();if(chosen!=null)ClientCompanion.art(g,chosen.card(),face,x+imageWidth-188,y+76,158,288);
  g.drawString(font,"Your inventory",x+12,y+395,0xFFB3DFFF);g.drawString(font,"Deckbox",x+imageWidth-240,y+398,0xFFB3DFFF);
  for(var slot:menu.slots){g.fill(x+slot.x-1,y+slot.y-1,x+slot.x+17,y+slot.y+17,0xFF91A5C1);g.fill(x+slot.x,y+slot.y,x+slot.x+16,y+slot.y+16,0xFF27364D);}
  g.drawString(font,"Closing returns the deckbox to you.",x+212,y+474,0xFF9CADC6);if(!message.isEmpty())g.drawString(font,font.plainSubstrByWidth(message,imageWidth-116),x+12,y+imageHeight-21,0xFFFFDA8A);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}
 @Override public boolean mouseClicked(MouseButtonEvent event,boolean twice){int listW=Math.max(412,imageWidth-228);int at=CardBrowser.hit((int)event.x(),(int)event.y(),leftPos+12,topPos+76,listW,302,scroll,data==null?0:data.rows().size(),grid);if(at>=0){selected=at;return true;}return super.mouseClicked(event,twice);}
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){int listW=Math.max(412,imageWidth-228);if(mx>=leftPos+12&&mx<leftPos+12+listW&&my>=topPos+76&&my<topPos+378){scroll=CardBrowser.clampScroll(scroll-(int)Math.signum(dy)*(grid?4:3),data==null?0:data.rows().size(),listW,302,grid);return true;}return super.mouseScrolled(mx,my,dx,dy);}
}
