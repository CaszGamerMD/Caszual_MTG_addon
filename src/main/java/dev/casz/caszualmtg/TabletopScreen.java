package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.core.BlockPos;
import net.minecraft.world.item.ItemStack;
import java.util.*;

/** A shared upper battlefield and a private lower hand, with deck/zone controls. */
public final class TabletopScreen extends LegacyScreen {
 TabletopWire.Reply data;
 String message="";
 String bottomTab="hand";
 String pickedBoard="";
 int pickedBottom=-1,scroll=0,ticks=0,preview=-1;
 boolean deckTools=true;
 final Set<Integer> scryBottom=new LinkedHashSet<>();
 TabletopScreen(TabletopWire.Reply reply){super(Component.literal("Caszual MTG Tabletop"));data=reply;}

 void update(TabletopWire.Reply reply){
  boolean rebuild=data.scry().isEmpty()!=reply.scry().isEmpty()
    ||data.seat().equals(data.pos())!=reply.seat().equals(reply.pos());
  data=reply;
  if(!reply.message().isBlank())message=reply.message();
  if(!reply.scry().isEmpty())bottomTab="scry";
  else if(bottomTab.equals("scry")){bottomTab="hand";scryBottom.clear();}
  if(!pickedBoard.isBlank()&&data.cards().stream().noneMatch(c->c.id().equals(pickedBoard)))pickedBoard="";
  if(pickedBottom>=bottomCards().size())pickedBottom=-1;
  if(rebuild)rebuildWidgets();
 }

 int boardX(){return 12;}
 int boardY(){return 44;}
 int boardW(){return Math.max(190,width-196);}
 int boardH(){return Math.max(108,height/2-57);}
 int sidebarX(){return width-168;}
 int bottomY(){return height/2+7;}
 int cardTop(){return bottomY()+38;}
 int columns(){return Math.max(1,(boardW()-16)/83);}
 int visibleRows(){return Math.max(1,(height-cardTop()-23)/112);}
 boolean playing(){return Minecraft.getInstance().player!=null&&data.tiles().stream().anyMatch(t->t.pos().equals(data.seat())&&t.owner().equals(Minecraft.getInstance().player.getGameProfile().name()));}
 void button(String label,int px,int py,int pw,Runnable action){
  addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(px,py,pw,20).build());
 }
 void selectTab(String tab){bottomTab=tab;pickedBottom=-1;scroll=0;rebuildWidgets();}
 void send(String action,String ref,BlockPos target,int x,int y,int amount){
  if(ClientPlayNetworking.canSend(TabletopWire.Request.TYPE))ClientPlayNetworking.send(new TabletopWire.Request(data.pos(),action,ref,target,x,y,amount));
 }
 void action(String name,int count){send(name,"",data.seat(),0,0,count);}
 void tableAction(String name){if(!pickedBoard.isBlank())send(name,pickedBoard,data.seat(),0,0,0);}
 TabletopWire.Card chosenCard(){
  for(var c:data.cards())if(c.id().equals(pickedBoard))return c;
  return null;
 }
 boolean isOwnCard(TabletopWire.Card card){
  return card!=null&&Minecraft.getInstance().player!=null
   &&card.owner().equals(Minecraft.getInstance().player.getUUID().toString());
 }
 void setTabButtons(){
  int y=bottomY()+5,x=boardX();
  button("Hand ("+data.hand().size()+")",x,y,105,()->selectTab("hand"));
  button("Grave ("+data.grave().size()+")",x+111,y,112,()->selectTab("grave"));
  button("Exile ("+data.exile().size()+")",x+229,y,108,()->selectTab("exile"));
  if(!data.scry().isEmpty())button("Scry ("+data.scry().size()+")",x+344,y,105,()->selectTab("scry"));
 }
 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,680,440))return;
  clearWidgets();
  int x=sidebarX(),y=47,w=156;
  button("Deck actions",x,y,76,()->{deckTools=true;rebuildWidgets();});
  button("Card actions",x+78,y,78,()->{deckTools=false;rebuildWidgets();});
  if(deckTools){
   button("Draw 1",x,y+34,76,()->action("draw",1));
   button("Draw 7",x+80,y+34,76,()->action("draw",7));
   button("Scry 1",x,y+60,76,()->action("scry_begin",1));
   button("Scry 3",x+80,y+60,76,()->action("scry_begin",3));
   button("Mill 1",x,y+86,76,()->action("mill",1));
   button("Mill 5",x+80,y+86,76,()->action("mill",5));
   button("Shuffle deck",x,y+112,156,()->action("shuffle",0));
   if(!data.scry().isEmpty()){
    button("Resolve scry",x,y+144,156,this::resolveScry);
    button("Cancel scry",x,y+168,156,()->send("scry_cancel","",data.seat(),0,0,0));
   }
  }else{
   button("Tap / Untap",x,y+34,156,()->tableAction("tap"));
   button("Face down / up",x,y+60,156,()->tableAction("hide"));
   button("Return to hand",x,y+86,156,()->tableAction("return"));
   button("To graveyard",x,y+112,156,()->tableAction("grave"));
   button("Exile",x,y+138,156,()->tableAction("exile"));
   if((bottomTab.equals("grave")||bottomTab.equals("exile"))&&pickedBottom>=0)
    button("Zone → Hand",x,y+170,156,this::zoneToHand);
  }
  button("Done",x,height-33,156,this::onClose);
  setTabButtons();
 }
 void zoneToHand(){
  if(pickedBottom<0)return;
  var list=bottomTab.equals("grave")?data.grave():data.exile();
  if(pickedBottom>=list.size())return;
  send("zone_to_hand","",data.seat(),0,0,list.get(pickedBottom).slot());
 }
 void resolveScry(){
  List<Integer> top=new ArrayList<>(),bottom=new ArrayList<>();
  for(int i=0;i<data.scry().size();i++)(scryBottom.contains(i)?bottom:top).add(i);
  String first=top.stream().map(String::valueOf).collect(java.util.stream.Collectors.joining(","));
  String second=bottom.stream().map(String::valueOf).collect(java.util.stream.Collectors.joining(","));
  send("scry_commit",first+"|"+second,data.seat(),0,0,0);
 }
 List<ItemStack> bottomCards(){
  if(bottomTab.equals("scry"))return data.scry();
  if(bottomTab.equals("grave"))return data.grave().stream().map(TabletopWire.ZoneCard::stack).toList();
  if(bottomTab.equals("exile"))return data.exile().stream().map(TabletopWire.ZoneCard::stack).toList();
  return data.hand();
 }
 @Override public boolean isPauseScreen(){return false;}
 @Override public void tick(){
  super.tick();
  if(++ticks%30==0)send("refresh","",data.seat(),0,0,0);
 }
 int minX(){return data.tiles().stream().mapToInt(t->t.pos().getX()).min().orElse(0);}
 int minZ(){return data.tiles().stream().mapToInt(t->t.pos().getZ()).min().orElse(0);}
 int countX(){return Math.max(1,data.tiles().stream().mapToInt(t->t.pos().getX()).max().orElse(minX())-minX()+1);}
 int countZ(){return Math.max(1,data.tiles().stream().mapToInt(t->t.pos().getZ()).max().orElse(minZ())-minZ()+1);}
 int tileX(BlockPos pos){return boardX()+(pos.getX()-minX())*boardW()/countX();}
 int tileY(BlockPos pos){return boardY()+(pos.getZ()-minZ())*boardH()/countZ();}
 int tileW(){return Math.max(1,boardW()/countX());}
 int tileH(){return Math.max(1,boardH()/countZ());}
 int cardWidth(){
  return Math.max(16,Math.min(64,Math.min(tileW()-8,Math.round((tileH()-8)/1.42f))));
 }
 int cardHeight(){return Math.round(cardWidth()*1.42f);}
 int cardX(TabletopWire.Card c){return tileX(c.pos())+4+c.x()*Math.max(0,tileW()-cardWidth()-8)/1000;}
 int cardY(TabletopWire.Card c){return tileY(c.pos())+4+c.y()*Math.max(0,tileH()-cardHeight()-8)/1000;}
 BlockPos tileAt(int mx,int my){
  if(mx<boardX()||my<boardY()||mx>=boardX()+boardW()||my>=boardY()+boardH())return null;
  int cx=Math.min(countX()-1,(mx-boardX())*countX()/boardW());
  int cz=Math.min(countZ()-1,(my-boardY())*countZ()/boardH());
  int x=minX()+cx,z=minZ()+cz;
  for(var t:data.tiles())if(t.pos().getX()==x&&t.pos().getZ()==z)return t.pos();
  return null;
 }
 @Override public boolean mouseClicked(MouseButtonEvent e,boolean twice){
  int mx=(int)e.x(),my=(int)e.y();
  BlockPos dest=tileAt(mx,my);
  if(dest!=null){
   List<TabletopWire.Card> reversed=new ArrayList<>(data.cards());
   Collections.reverse(reversed);
   // Clicking a card selects it; clicking elsewhere then drops it at the chosen pixel.
   for(var c:reversed)if(mx>=cardX(c)&&mx<cardX(c)+cardWidth()&&my>=cardY(c)&&my<cardY(c)+cardHeight()){
    if(c.id().equals(pickedBoard))pickedBoard="";else pickedBoard=c.id();
    return true;
   }
   int nx=Math.clamp((mx-tileX(dest)-4)*1000/Math.max(1,tileW()-cardWidth()-8),0,1000);
   int ny=Math.clamp((my-tileY(dest)-4)*1000/Math.max(1,tileH()-cardHeight()-8),0,1000);
   TabletopWire.Card selected=chosenCard();
   if(selected!=null){
    if(!isOwnCard(selected)){message="You may only move your own cards.";return true;}
    send("move",selected.id(),dest,nx,ny,0);pickedBoard="";return true;
   }
   if(pickedBottom>=0){
    if(bottomTab.equals("hand"))send("put_hand","",dest,nx,ny,pickedBottom);
    else if(bottomTab.equals("grave")&&pickedBottom<data.grave().size())send("put_grave","",dest,nx,ny,data.grave().get(pickedBottom).slot());
    else if(bottomTab.equals("exile")&&pickedBottom<data.exile().size())send("put_exile","",dest,nx,ny,data.exile().get(pickedBottom).slot());
    pickedBottom=-1;return true;
   }
   message="Choose a card below, then click anywhere on the tabletop.";
   return true;
  }
  int index=bottomIndex(mx,my);
  if(index>=0&&index<bottomCards().size()){
   pickedBottom=index;pickedBoard="";
   if(bottomTab.equals("scry")){
    if(!scryBottom.add(index))scryBottom.remove(index);
   }
   return true;
  }
  return super.mouseClicked(e,twice);
 }
 int bottomIndex(int mx,int my){
  int dx=mx-boardX()-6,dy=my-cardTop();
  if(dx<0||dx>=boardW()-12||dy<0||dy>=visibleRows()*112)return -1;
  int col=dx/83,row=dy/112;
  if(col>=columns())return -1;
  return (scroll+row)*columns()+col;
 }
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(my>=cardTop()&&mx<boardX()+boardW()){
   int rows=(bottomCards().size()+columns()-1)/columns();
   scroll=Math.clamp(scroll-(int)Math.signum(dy),0,Math.max(0,rows-visibleRows()));
   return true;
  }
  return super.mouseScrolled(mx,my,dx,dy);
 }
 @Override public void render(GuiGraphics g,int mx,int my,float delta){
  g.fill(0,0,width,height,0xFF101923);
  g.fill(0,0,width,32,0xFF283747);
  g.drawString(font,"CASZUAL MTG  /  TABLETOP",12,11,0xFFF6E0B0);
  g.fill(boardX()-2,boardY()-2,boardX()+boardW()+2,boardY()+boardH()+2,0xFF836345);
  g.fill(boardX(),boardY(),boardX()+boardW(),boardY()+boardH(),0xFF283D39);
  for(var tile:data.tiles()){
   int tx=tileX(tile.pos()),ty=tileY(tile.pos()),tw=tileW(),th=tileH();
   boolean own=tile.pos().equals(data.seat())&&playing();
   g.fill(tx+1,ty+1,tx+tw-2,ty+th-2,own?0xFF315348:0xFF355044);
   g.drawString(font,font.plainSubstrByWidth(tile.owner().isBlank()?"Empty seat":tile.owner(),tw-6),tx+5,ty+5,own?0xFFFFD58D:0xFFB2C6BE);
  }
  for(var c:data.cards()){
   int x=cardX(c),y=cardY(c),cw=cardWidth(),ch=cardHeight();
   boolean chosen=c.id().equals(pickedBoard);
   int border=chosen?0xFFFFCC66:c.tapped()?0xFF8FB7E0:0xFF101C23;
   g.fill(x-2,y-2,x+cw+2,y+ch+2,border);
   if(c.hidden()&&c.stack().isEmpty()){
    g.fill(x,y,x+cw,y+ch,0xFF172B47);
    g.fill(x+4,y+4,x+cw-4,y+ch-4,0xFF3D5D83);
    g.drawCenteredString(font,"MTG",x+cw/2,y+ch/2-5,0xFFF1D89C);
   }else if(!c.stack().isEmpty())CaszualMtgClient.art(g,c.stack(),0,x,y,cw,ch);
   if(c.tapped())g.drawString(font,"TAPPED",x,y+ch-10,0xFFFFFFAA);
  }
  int bx=boardX(),by=bottomY();
  g.fill(bx-2,by-2,bx+boardW()+2,height-8,0xFF283748);
  g.fill(bx,by,bx+boardW(),height-10,0xFF152234);
  List<ItemStack> cards=bottomCards();
  int maxRows=Math.min(visibleRows(),Math.max(0,(cards.size()+columns()-1)/columns()-scroll));
  for(int row=0;row<maxRows;row++)for(int col=0;col<columns();col++){
   int index=(scroll+row)*columns()+col;if(index>=cards.size())break;
   int x=bx+6+col*83,y=cardTop()+row*112;
   boolean selected=index==pickedBottom;
   boolean bottom=bottomTab.equals("scry")&&scryBottom.contains(index);
   g.fill(x-2,y-2,x+75,y+108,selected?0xFFE2BD70:bottom?0xFF9D5663:0xFF455D77);
   CaszualMtgClient.art(g,cards.get(index),0,x+1,y+1,70,103);
   if(bottomTab.equals("scry"))g.drawString(font,bottom?"BOTTOM":"TOP",x+3,y+93,bottom?0xFFFFCED2:0xFFEAF6A7);
  }
  g.fill(sidebarX()-5,37,width-7,height-8,0xFF202D3D);
  g.drawString(font,"Library: "+data.libraryCount(),sidebarX()+4,39,0xFFF4D9A6);
  String owner=playing()?"Your seat: "+data.seat().getX()+","+data.seat().getZ():"Spectator / occupied";
  g.drawString(font,font.plainSubstrByWidth(owner,155),sidebarX()+4,height-64,0xFFB3CBE2);
  if(!message.isBlank())g.drawString(font,font.plainSubstrByWidth(message,boardW()-12),bx+4,height-19,0xFFFFD78B);
  else g.drawString(font,"Click a card below, then place it above. Click a played card to move it.",bx+4,height-19,0xFFAEC2D5);
  super.render(g,mx,my,delta);
  // Hold mouse over an art card for a larger readable preview.
  int hit=bottomIndex(mx,my);
  if(hit>=0&&hit<cards.size()&&cards.get(hit)!=null&&!cards.get(hit).isEmpty()){
   int px=Math.min(width-182,Math.max(8,mx+16)),py=Math.max(35,Math.min(height-246,my-170));
   g.fill(px-3,py-3,px+158,py+225,0xFFB89B6D);
   CaszualMtgClient.art(g,cards.get(hit),0,px,py,155,222);
  }
 }
}
