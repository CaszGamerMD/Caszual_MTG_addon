package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.components.*;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Inventory;

/** Full-viewport Community Card Collection with independent browse and transfer regions. */
public final class CommunityScreen extends LegacyContainerScreen<CommunityMenu> {
 Wire.Reply data;
 EditBox search,quantity;
 String query="",message="";
 boolean grid=ClientPrefs.grid();
 int selected=-1,scroll=0,page=0,face=0;
 long lastSend;

 public CommunityScreen(CommunityMenu menu,Inventory inventory,Component title){
  super(menu,inventory,title,640,430);
 }
 public void update(Wire.Reply reply){
  data=reply;selected=-1;scroll=0;message="";
 }
 int side(){return FullScreenMenuLayout.sidebarX(width);}
 int browseTop(){return 86;}
 int browseWidth(){return FullScreenMenuLayout.browseWidth(width);}
 int browseHeight(){return FullScreenMenuLayout.browseHeight(height,browseTop());}
 // CardBrowser derives its card height from its width. Bound that width to
 // the browse area HEIGHT too: wide windows with short viewports must not
 // render giant cards over the action buttons and player inventory.
 int browserWidth(){
  if(!grid)return browseWidth();
  int maxCell=Math.max(32,Math.round((browseHeight()-22)*.716f)+8);
  return Math.min(browseWidth(),maxCell*4+18);
 }
 int actionY(){return FullScreenMenuLayout.actionY(height);}
 int previewHeight(){return Math.max(115,Math.min(270,FullScreenMenuLayout.inventoryTop(height)-213));}
 int looseY(){return browseTop()+previewHeight()+14;}
 int boxY(){return looseY()+26;}
 int sideButtonWidth(){return FullScreenMenuLayout.sidebarWidth(width)-42;}

 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,640,430))return;
  String lastSearch=search==null?query:search.getValue();
  String lastQuantity=quantity==null?"1":quantity.getValue();
  imageWidth=width;
  imageHeight=height;
  super.init();
  FullScreenMenuLayout.positionInventory(menu,2,height);
  FullScreenMenuLayout.position(menu.slots.get(0),side()+8,boxY());
  FullScreenMenuLayout.position(menu.slots.get(1),side()+8,looseY());

  button(grid?"List view":"Grid view",width-110,7,98,()->{
   query=search.getValue();grid=!grid;ClientPrefs.setGrid(grid);
   scroll=0;rebuildWidgets();
  });
  search=addRenderableWidget(new EditBox(font,12,34,browseWidth()-96,20,Component.literal("Search stored cards")));
  search.setMaxLength(200);search.setValue(lastSearch);
  button("Search",12+browseWidth()-89,34,85,()->{
   page=0;query=search.getValue();send("search",query,0);
  });
  button("Deposit inventory cards",side(),34,FullScreenMenuLayout.sidebarWidth(width),()->
    send("deposit_inventory","",0));

  button("Previous",12,actionY(),78,()->{
   page=Math.max(0,page-1);query=search.getValue();send("search",query,page);
  });
  button("Next",96,actionY(),62,()->{
   page++;query=search.getValue();send("search",query,page);
  });
  quantity=addRenderableWidget(new EditBox(font,166,actionY(),38,20,Component.literal("Quantity")));
  quantity.setValue(lastQuantity);quantity.setMaxLength(2);
  button("Take to inventory",212,actionY(),136,()->{
   if(chosen()!=null)send("withdraw",chosen().key(),amount());
  });

  button("Deposit loose card",side()+36,looseY(),sideButtonWidth(),()->
    send("deposit_loose","",0));
  button("Deposit contents",side()+36,boxY(),sideButtonWidth(),()->
    send("box_deposit","",0));
  button("Selected into box",side()+8,boxY()+27,FullScreenMenuLayout.sidebarWidth(width)-8,()->{
   if(chosen()!=null)send("box_withdraw",chosen().key(),amount());
  });
  button("Fill box from search",side()+8,boxY()+54,FullScreenMenuLayout.sidebarWidth(width)-8,()->
    send("box_fill","",99));
  button("Done",width-86,height-32,74,this::onClose);
 }

 @Override public void removed(){MtgGuiScaleHelper.restoreGuiScale(this);super.removed();}
 int amount(){
  try{int n=Integer.parseInt(quantity.getValue());if(n>=1&&n<=99)return n;}
  catch(NumberFormatException ignored){}
  message="Enter quantity 1–99.";return 0;
 }
 Wire.Row chosen(){
  return data!=null&&selected>=0&&selected<data.rows().size()?data.rows().get(selected):null;
 }
 void button(String label,int x,int y,int w,Runnable action){
  addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(x,y,w,20).build());
 }
 void send(String action,String text,int count){
  if((action.equals("withdraw")||action.equals("box_withdraw")||action.equals("box_fill"))&&count<1)return;
  if(action.equals("withdraw")&&count>64){
   message="Inventory withdrawal limit is 64; deckbox limit is 99.";return;
  }
  long now=System.currentTimeMillis();
  if(now-lastSend<180)return;
  lastSend=now;
  ClientPlayNetworking.send(new Wire.Request(menu.pos,action,text,count));
  message="Working…";
 }

 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){
  g.fill(0,0,width,height,0xFF152032);
  g.fill(0,0,width,27,0xFF202F45);
  g.drawString(font,title,12,11,0xFFFFFFFF);
  String serverMessage=data==null?"Loading shared collection…":data.message();
  g.drawString(font,font.plainSubstrByWidth(serverMessage,width-24),12,64,0xFFB3DFFF);

  int listW=browseWidth(),listH=browseHeight();
  g.fill(11,browseTop()-1,13+listW,browseTop()+listH+1,0xFF41536C);
  g.fill(12,browseTop(),12+listW,browseTop()+listH,0xFF101B2A);
  if(data!=null)CardBrowser.render(g,font,data.rows(),12,browseTop(),browserWidth(),listH,scroll,selected,grid,false);

  int previewY=browseTop(),previewH=previewHeight(),sx=side();
  g.fill(sx+3,previewY-2,width-12,previewY+previewH+3,0xFF41536C);
  g.fill(sx+4,previewY-1,width-13,previewY+previewH+2,0xFF101B2A);
  Wire.Row chosen=chosen();
  if(chosen!=null)CaszualMtgClient.art(g,chosen.card(),face,
    sx+11,previewY+4,FullScreenMenuLayout.sidebarWidth(width)-23,previewH-8);
  else g.drawCenteredString(font,"Select a card",sx+FullScreenMenuLayout.sidebarWidth(width)/2,
    previewY+previewH/2,0xFFB3DFFF);

  // The transfer buttons label their corresponding slots; separate floating
  // labels previously collided with the preview and adjacent action rows.
  g.drawString(font,"Your inventory",12,FullScreenMenuLayout.inventoryLabelY(height),0xFFB3DFFF);
  for(var slot:menu.slots){
   g.fill(slot.x-1,slot.y-1,slot.x+17,slot.y+17,0xFF91A5C1);
   g.fill(slot.x,slot.y,slot.x+16,slot.y+16,0xFF27364D);
  }
  g.drawString(font,font.plainSubstrByWidth("Closing returns un-deposited loose cards and deckbox.",width-302),
    188,FullScreenMenuLayout.inventoryLabelY(height),0xFF9CADC6);
  if(!message.isEmpty())g.drawString(font,font.plainSubstrByWidth(message,width-300),
    188,FullScreenMenuLayout.statusY(height),0xFFFFDA8A);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}

 @Override public boolean mouseClicked(MouseButtonEvent event,boolean twice){
  int at=CardBrowser.hit((int)event.x(),(int)event.y(),12,browseTop(),browserWidth(),browseHeight(),
    scroll,data==null?0:data.rows().size(),grid);
  if(at>=0){selected=at;face=0;return true;}
  return super.mouseClicked(event,twice);
 }
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(mx>=12&&mx<12+browseWidth()&&my>=browseTop()&&my<browseTop()+browseHeight()){
   scroll=CardBrowser.clampScroll(scroll-(int)Math.signum(dy)*(grid?4:3),
     data==null?0:data.rows().size(),browserWidth(),browseHeight(),grid);
   return true;
  }
  return super.mouseScrolled(mx,my,dx,dy);
 }
}
