package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import com.spider.mtgcard.util.TcgCardMeta;
import org.lwjgl.glfw.GLFW;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStack;
import java.util.*;
import java.util.stream.Collectors;

/**
 * One table at a time; top tabs switch seats, while the private hand remains
 * anchored at the bottom. All drag/drop results are validated by the server.
 */
public final class TabletopScreen extends LegacyScreen {
 TabletopWire.Reply data;
 BlockPos view;
 String message="";
 String zone="hand";
 String menuMode="";
 EditBox quantity;
 boolean resetConfirm=false;
 boolean discardMode=false;
 boolean tokenTrayOpen=false,counterOpen=false;
 String counterCard="",tokenText="",tokenOracleText="",tokenPtText="",targetSource="";
 int traySelected=-1,tokenResultSelected=-1,trayScroll=0,tokenResultScroll=0,shownScroll=0,publicRevealScroll=0;
 EditBox counterName,counterTotal,tokenSearch,tokenOracle,tokenPt;
 int zoneScroll=0,tabScroll=0,ticks=0;
 String selectedCard="";
 String pendingHandZone="";
 int pendingHandSlot=-1;
 int selectedZone=-1;
 Set<Integer> scryBottom=new LinkedHashSet<>();
 Drag drag;
 record Drag(String source,String id,int index,ItemStack card,int startX,int startY) {}

 TabletopScreen(TabletopWire.Reply reply){
  super(Component.literal("Caszual MTG Tabletop"));
  data=reply;
  view=reply.seat();
 }
 void update(TabletopWire.Reply reply){
  boolean changed=!data.tiles().equals(reply.tiles())||data.scry().isEmpty()!=reply.scry().isEmpty()
   ||data.commander().isEmpty()!=reply.commander().isEmpty()
   ||data.reveal().isEmpty()!=reply.reveal().isEmpty()
    ||data.ownHandRevealed()!=reply.ownHandRevealed();
  data=reply;
  if(reply.tiles().stream().noneMatch(t->t.pos().equals(view)))view=reply.seat();
  if(!reply.message().isBlank())message=reply.message();
  if(!reply.reveal().isEmpty())zone="reveal";
  else if(!reply.scry().isEmpty())zone="scry";
  else if(zone.equals("scry")||zone.equals("reveal")){zone="hand";scryBottom.clear();}
  if(!selectedCard.isBlank()&&reply.cards().stream().noneMatch(c->c.id().equals(selectedCard)))selectedCard="";
  if(pendingHandSlot>=reply.hand().size()){pendingHandZone="";pendingHandSlot=-1;rebuildWidgets();}
  if(changed)rebuildWidgets();
  if(counterOpen&&data.cards().stream().noneMatch(c->c.id().equals(counterCard))){counterOpen=false;rebuildWidgets();}
 }
 void send(String action,String ref,BlockPos target,int x,int y,int amount){
  if(ClientPlayNetworking.canSend(TabletopWire.Request.TYPE))
   ClientPlayNetworking.send(new TabletopWire.Request(data.pos(),action,ref,target,x,y,amount));
 }
 void action(String name,int amount){send(name,"",data.seat(),0,0,amount);}
 void button(String label,int x,int y,int w,Runnable callback){
  if(w>18)addRenderableWidget(Button.builder(Component.literal(label),b->callback.run()).bounds(x,y,w,20).build());
 }
 // The public hand is displayed on its owner's table for all viewers.
 TabletopWire.ShownHand shownHand(){
  for(var hand:data.shownHands())if(hand.seat().equals(view))return hand;
  return null;
 }
 TabletopWire.PublicReveal displayedReveal(){
  for(var deck:data.publicReveals())if(deck.seat().equals(view))return deck;
  return null;
 }
 int revealStripX(){return boardX()+12;}
 int revealStripY(){return boardY()+36;}
 int revealStripStep(){return 60;}
 int revealStripCardW(){return 52;}
 int revealStripCardH(){return 75;}
 int revealStripVisible(){return Math.max(1,(boardW()-28)/revealStripStep());}
 int revealStripAt(int mx,int my){
  TabletopWire.PublicReveal shown=displayedReveal();
  if(shown==null||tokenTrayOpen||counterOpen||mx<revealStripX()||my<revealStripY()
     ||my>=revealStripY()+revealStripCardH())return -1;
  int col=(mx-revealStripX())/revealStripStep();
  if(col>=revealStripVisible()||mx>=revealStripX()+col*revealStripStep()+revealStripCardW())return -1;
  int index=publicRevealScroll+col;
  return index<shown.cards().size()?index:-1;
 }
 boolean isHandRevealed(BlockPos seat){
  return data.shownHands().stream().anyMatch(hand->hand.seat().equals(seat));
 }
 int shownHandX(){return boardX()+11;}
 int shownHandY(){return boardY()+boardH()-103;}
 int shownCardW(){return 54;}
 int shownCardH(){return 80;}
 int shownCardStride(){return 61;}
 int shownHandVisible(){return Math.max(1,(boardW()-27)/shownCardStride());}
 int shownCardAt(int mx,int my){
  TabletopWire.ShownHand hand=shownHand();
  if(hand==null||tokenTrayOpen||mx<shownHandX()||my<shownHandY()||my>=shownHandY()+shownCardH())return -1;
  int col=(mx-shownHandX())/shownCardStride();
  if(col>=shownHandVisible()||mx>=shownHandX()+col*shownCardStride()+shownCardW())return -1;
  int index=shownScroll+col;
  return index<hand.cards().size()?index:-1;
 }
 boolean playing(){
  var me=Minecraft.getInstance().player;
  return me!=null&&data.tiles().stream().anyMatch(t->t.pos().equals(data.seat())&&t.owner().equals(me.getGameProfile().name()));
 }
 TabletopWire.Tile shown(){
  for(var t:data.tiles())if(t.pos().equals(view))return t;
  return null;
 }
 List<TabletopWire.Card> displayed(){
  return data.cards().stream().filter(c->c.pos().equals(view)).toList();
 }
 List<ItemStack> zoneCards(){
  return switch(zone){
   case "grave" -> data.grave().stream().map(TabletopWire.ZoneCard::stack).toList();
   case "exile" -> data.exile().stream().map(TabletopWire.ZoneCard::stack).toList();
   case "scry" -> data.scry();
   case "reveal" -> data.reveal();
   default -> data.hand();
  };
 }
 void switchZone(String next){
  zone=next;zoneScroll=0;selectedZone=-1;drag=null;pendingHandZone="";pendingHandSlot=-1;rebuildWidgets();
 }
 int boardX(){return 12;}
 int boardY(){return menuMode.isEmpty()?66:97;}
 int boardW(){return width-24;}
 int handTop(){return height-139;}
 int boardH(){return Math.max(100,handTop()-boardY()-8);}
 int zoneY(){return handTop()+31;}
 int handCardW(){return 67;}
 int handCardH(){return 96;}
 int handStart(){return 93;}
 int handStride(){return 71;}
 int visibleHandCards(){return Math.max(1,(width-handStart()-21)/handStride());}
 int boardCardW(){
  int base=Math.max(38,Math.min(70,boardW()/10));
  TabletopWire.Tile tile=shown();
  int scale=tile==null?100:Math.clamp(tile.cardScale(),45,180);
  int heightLimit=Math.max(18,Math.round((boardH()-18)/1.43f));
  return Math.max(18,Math.min(Math.round(base*scale/100f),heightLimit));
 }
 int boardCardH(){return Math.round(boardCardW()*1.43f);}
 int cardX(TabletopWire.Card c){return boardX()+8+c.x()*Math.max(0,boardW()-boardCardW()-16)/1000;}
 int cardY(TabletopWire.Card c){return boardY()+8+c.y()*Math.max(0,boardH()-boardCardH()-16)/1000;}
 int xNormalized(int mx){return Math.clamp((mx-boardX()-8)*1000/Math.max(1,boardW()-boardCardW()-16),0,1000);}
 int yNormalized(int my){return Math.clamp((my-boardY()-8)*1000/Math.max(1,boardH()-boardCardH()-16),0,1000);}
 boolean boardHit(int x,int y){return x>=boardX()&&x<boardX()+boardW()&&y>=boardY()&&y<boardY()+boardH();}
 TabletopWire.Card cardAt(int mx,int my){
  List<TabletopWire.Card> list=new ArrayList<>(displayed());Collections.reverse(list);
  for(var c:list){
   int x=cardX(c),y=cardY(c),w=boardCardW(),h=boardCardH();
   // Tapped cards are rotated around the center of their upright bounds.
   // Match the actual sideways artwork for click and Alt-to-zoom hit testing.
   int left=c.tapped()?x+(w-h)/2:x;
   int top=c.tapped()?y+(h-w)/2:y;
   int visualW=c.tapped()?h:w,visualH=c.tapped()?w:h;
   if(mx>=left&&mx<left+visualW&&my>=top&&my<top+visualH)return c;
  }
  return null;
 }
 int zoneAt(int mx,int my){
  if(mx<handStart()||my<zoneY()||my>=zoneY()+handCardH()+2)return -1;
  int at=(mx-handStart())/handStride();
  if(at<0||at>=visibleHandCards())return -1;
  int index=zoneScroll+at;
  return index>=0&&index<zoneCards().size()?index:-1;
 }
 void selectView(BlockPos target){view=target;selectedCard="";drag=null;shownScroll=0;publicRevealScroll=0;rebuildWidgets();}
 int wanted(){try{return Math.clamp(Integer.parseInt(quantity.getValue().trim()),1,99);}catch(Exception e){message="Enter a number from 1 to 99.";return -1;}}
 void amountAction(String action){int n=wanted();if(n<0)return;send(action,"",data.seat(),0,0,n);}
 void openMenu(String name){menuMode=menuMode.equals(name)?"":name;resetConfirm=false;rebuildWidgets();}
 String seatLabel(TabletopWire.Tile t){
  String name=t.owner().isBlank()?"Empty":t.owner();
  if(name.length()>11)name=name.substring(0,11);
  return (t.active()?"▶ ":"")+name+(t.hasLife()?"  "+t.life()+" ♥":"  --");
 }
 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,680,440))return;
  clearWidgets();
  int x=12;
  int maxTabs=Math.max(1,(width-95)/137);
  int last=Math.min(data.tiles().size(),tabScroll+maxTabs);
  for(int i=tabScroll;i<last;i++){
   TabletopWire.Tile t=data.tiles().get(i);
   button(seatLabel(t),x,7,132,()->selectView(t.pos()));
   x+=137;
  }
  if(data.tiles().size()>maxTabs){
   button("◀",width-77,7,31,()->{tabScroll=Math.max(0,tabScroll-maxTabs);rebuildWidgets();});
   button("▶",width-42,7,31,()->{tabScroll=Math.min(Math.max(0,data.tiles().size()-maxTabs),tabScroll+maxTabs);rebuildWidgets();});
  }
  int ux=12,uy=38;
  button("Draw ▾",ux,uy,86,()->openMenu("draw"));ux+=91;
  button("Deck ▾",ux,uy,86,()->openMenu("deck"));ux+=91;
  button("Pass Turn",ux,uy,91,()->action("pass_turn",0));ux+=96;
  button("Flip",ux,uy,58,()->tableAction("flip"));ux+=63;
  button("Untap All",ux,uy,92,()->action("untap_all",0));ux+=97;
  button("Target ▾",ux,uy,83,()->{tokenTrayOpen=false;counterOpen=false;openMenu("target");});ux+=88;
  button(tokenTrayOpen?"Tokens ▴":"Tokens ▾",ux,uy,94,()->{
   tokenTrayOpen=!tokenTrayOpen;counterOpen=false;rebuildWidgets();
   if(tokenTrayOpen)searchTokens(0);
  });
  button("Close",width-77,uy,64,this::onClose);
  if(menuMode.equals("target")){
   int tx=12,ty=66;
   button("Target Player",tx,ty,112,()->{send("target_player",targetSource,view,0,0,0);message="Declared player target.";});
   button("Clear Target",tx+117,ty,110,()->{action("target_clear",0);targetSource="";});
   button("Exit Targeting",tx+232,ty,125,()->{targetSource="";openMenu("");});
  }else if(menuMode.equals("draw")){
   int mx=12,my=66;
   quantity=addRenderableWidget(new EditBox(font,mx+62,my+3,48,18,Component.literal("X")));
   quantity.setMaxLength(2);quantity.setValue("3");
   button("Draw",mx+115,my,62,()->action("draw",1));
   button("Draw X",mx+182,my,68,()->amountAction("draw"));
   button("Mulligan",mx+255,my,89,()->openMenu("mulligan"));
   button("Scry X",mx+349,my,74,()->amountAction("scry_begin"));
   button("Mill X",mx+428,my,73,()->amountAction("mill"));
  }else if(menuMode.equals("mulligan")){
   int mx=12,my=66;
   button("Friendly",mx,my,85,()->action("mulligan_friendly",0));
   button("Strict",mx+90,my,85,()->action("mulligan_strict",0));
   button("Finish",mx+180,my,85,()->action("mulligan_finish",0));
   button("Back",mx+270,my,64,()->openMenu("draw"));
   button("Discard mode",mx+339,my,108,()->{discardMode=!discardMode;message=discardMode?"Click a card in Hand to discard for strict mulligan.":"Discard mode off.";});
  }else if(menuMode.equals("deck")){
   int mx=12,my=66;
   quantity=addRenderableWidget(new EditBox(font,mx,my+3,48,18,Component.literal("Reveal count")));
   quantity.setMaxLength(2);quantity.setValue("3");
   button("Shuffle",mx+53,my,83,()->action("shuffle",0));
   button("Search",mx+141,my,78,()->action("search_deck",0));
   button("Reveal X",mx+224,my,87,()->amountAction("reveal_begin"));
   button(resetConfirm?"CONFIRM RESET":"RESET",mx+316,my,135,()->{
    if(resetConfirm){resetConfirm=false;action("reset",0);}
    else{resetConfirm=true;rebuildWidgets();}
   });
  }
  if(counterOpen){
   int px=Math.max(14,width-330),py=boardY()+13;
   counterName=addRenderableWidget(new EditBox(font,px+12,py+33,162,19,Component.literal("Counter name")));
   counterName.setMaxLength(40);counterName.setValue("+1/+1");
   counterTotal=addRenderableWidget(new EditBox(font,px+180,py+33,48,19,Component.literal("Total")));
   counterTotal.setMaxLength(7);counterTotal.setValue("1");
   button("+1/+1",px+12,py+58,68,()->counterPreset("+1/+1"));
   button("-1/-1",px+84,py+58,68,()->counterPreset("-1/-1"));
   button("Loyalty",px+156,py+58,70,()->counterPreset("loyalty"));
   button("Charge",px+230,py+58,74,()->counterPreset("charge"));
   button("+1",px+12,py+86,58,()->changeCounter(1));
   button("-1",px+74,py+86,58,()->changeCounter(-1));
   button("Set",px+136,py+86,56,()->setCounter(false));
   button("Remove",px+196,py+86,74,()->setCounter(true));
   button("Create Token Copy",px+12,py+111,136,()->{
    send("copy_token",counterCard,data.seat(),0,0,0);
    counterOpen=false;rebuildWidgets();
   });
   if(data.cards().stream().anyMatch(c->c.id().equals(counterCard)&&
       Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(c.stack()).typeLine()))
       &&!counterCard.startsWith("copy:"))
    button("Return to tray",px+152,py+111,106,()->{send("token_store",counterCard,data.seat(),0,0,0);counterOpen=false;rebuildWidgets();});
   button("Close",px+263,py+111,44,()->{counterOpen=false;rebuildWidgets();});
  }
  if(tokenTrayOpen){
   int px=tokenPanelX(),py=boardY()+10,pw=tokenPanelW(),bottom=boardY()+boardH()-2;
   g.fill(px,py,px+pw,bottom,0xF11A2839);
   g.fill(px+4,py+4,px+pw-4,py+22,0xFF334B61);
   g.drawString(font,"TOKEN TRAY "+data.tray().size()+"/32",px+10,py+9,0xFFF5DAAA);
   g.drawString(font,"Token catalogue · page "+(data.tokenPage()+1),px+pw/2+8,py+9,0xFFCCE3EF);
   g.drawString(font,"Stored templates",px+8,py+112,0xFFB4CADB);
   g.drawString(font,"P/T    Oracle",px+pw/2+104,py+87,0xFFB4CADB);
   if(data.tokenResults().isEmpty())
    g.drawString(font,"No matching tokens",px+pw/2+8,py+119,0xFFB4CADB);
   int start=py+129,visible=tokenVisibleRows();
   for(int i=0;i<visible;i++){
    int at=trayScroll+i,yy=start+i*38;
    if(at<data.tray().size()){
     ItemStack token=data.tray().get(at);
     g.fill(px+5,yy,px+pw/2-4,yy+37,at==traySelected?0xFF557495:0xFF26384C);
     drawArt(g,token,px+7,yy+2,24,34);
     var meta=TcgCardMeta.read(token);
     g.drawString(font,font.plainSubstrByWidth(TcgCardMeta.displayName(token),pw/2-48),px+36,yy+5,0xFFFFFFFF);
     g.drawString(font,meta.power()+"/"+meta.toughness(),px+36,yy+22,0xFFE4C999);
    }
    int found=tokenResultScroll+i;
    if(found<data.tokenResults().size()){
     ItemStack token=data.tokenResults().get(found).stack();
     g.fill(px+pw/2+4,yy,px+pw-6,yy+37,found==tokenResultSelected?0xFF557495:0xFF26384C);
     drawArt(g,token,px+pw/2+6,yy+2,24,34);
     var meta=TcgCardMeta.read(token);
     g.drawString(font,font.plainSubstrByWidth(TcgCardMeta.displayName(token),pw/2-49),px+pw/2+34,yy+4,0xFFFFFFFF);
     String stats=meta.power().isBlank()?"":meta.power()+"/"+meta.toughness()+" ";
     g.drawString(font,font.plainSubstrByWidth(stats+meta.oracleText(),pw/2-48),px+pw/2+34,yy+22,0xFFDBD6BC);
    }
   }
  }
  if(counterOpen){
   int px=Math.max(14,width-330),py=boardY()+13;
   g.fill(px,py,px+314,py+146,0xF4192839);
   g.fill(px+3,py+3,px+311,py+26,0xFF41536A);
   g.drawString(font,"CARD COUNTERS",px+12,py+9,0xFFFFD694);
   g.drawString(font,"Name                    Total",px+12,py+26,0xFFAAC4D9);
  }
  g.fill(0,handTop(),width,height,0xFF192738);
  g.fill(7,handTop()+27,width-7,height-8,0xFF132033);
  if(data.ownHandRevealed()){
   int top=handTop();
   g.fill(0,top,width,top+5,0xFFFF2020);
   g.fill(0,height-5,width,height,0xFFFF2020);
   g.fill(0,top,5,height,0xFFFF2020);
   g.fill(width-5,top,width,height,0xFFFF2020);
   g.drawString(font,"!! HAND REVEALED TO OPPONENTS !!",Math.max(10,width/2-100),top+9,0xFFFF4545);
  }
  if(data.commander().isEmpty()){
   g.fill(13,zoneY(),81,zoneY()+handCardH(),0xFF354056);
   g.drawCenteredString(font,"COMMANDER",47,zoneY()+24,0xFFE1BD7F);
   g.drawCenteredString(font,"(deckbox)",47,zoneY()+39,0xFF9AB1C6);
  }else drawArt(g,data.commander(),13,zoneY(),67,handCardH());
  List<ItemStack> cards=zoneCards();
  int maxStart=Math.max(0,cards.size()-visibleHandCards());
  zoneScroll=Math.clamp(zoneScroll,0,maxStart);
  for(int i=zoneScroll;i<cards.size()&&i<zoneScroll+visibleHandCards();i++){
   int x=handStart()+(i-zoneScroll)*handStride();
   int y=zoneY();
   g.fill(x-2,y-2,x+handCardW()+2,y+handCardH()+2,i==selectedZone?0xFFFFC566:0xFF425A70);
   drawArt(g,cards.get(i),x,y,handCardW(),handCardH());
   if(zone.equals("scry"))g.drawString(font,scryBottom.contains(i)?"BOTTOM":"TOP",x+4,y+handCardH()-10,0xFFFFE79E);
  }
  g.drawString(font,"Library "+data.libraryCount()+"  |  Hand "+data.hand().size()+"  |  "+zone.toUpperCase(Locale.ROOT),174,handTop()+12,0xFFD3E0EA);
  if(!message.isBlank())g.drawString(font,font.plainSubstrByWidth(message,boardW()-16),boardX()+8,boardY()+boardH()-13,0xFFFFD789);
  super.render(g,mx,my,delta);
  // Alt enlarges the hovered card to a legible preview without revealing opponents' hidden cards.
  boolean alt=GLFW.glfwGetKey(Minecraft.getInstance().getWindow().handle(),GLFW.GLFW_KEY_LEFT_ALT)==GLFW.GLFW_PRESS
   ||GLFW.glfwGetKey(Minecraft.getInstance().getWindow().handle(),GLFW.GLFW_KEY_RIGHT_ALT)==GLFW.GLFW_PRESS;
  if(alt){
   ItemStack hovered=ItemStack.EMPTY;
   if(tokenTrayOpen&&inTokenPanel(mx,my)){
    int row=(my-boardY()-10-129)/38;
    if(row>=0&&row<tokenVisibleRows()&&my>=boardY()+10+129){
     int panelMiddle=tokenPanelX()+tokenPanelW()/2;
     if(mx<panelMiddle){
      int at=trayScroll+row;
      if(at<data.tray().size())hovered=data.tray().get(at);
     }else{
      int at=tokenResultScroll+row;
      if(at<data.tokenResults().size())hovered=data.tokenResults().get(at).stack();
     }
    }
   }
   if(revealedDeck!=null&&!tokenTrayOpen&&!counterOpen){
    int index=revealStripAt(mx,my);
    if(index>=0)hovered=revealedDeck.cards().get(index);
   }
   // The public-hand strip is layered over the battlefield, so it wins
   // the Alt hit-test even when an underlying played card overlaps it.
   if(publicHand!=null&&!tokenTrayOpen){
    int at=shownCardAt(mx,my);
    if(at>=0)hovered=publicHand.cards().get(at);
   }
   var onField=cardAt(mx,my);
   if(hovered.isEmpty()&&onField!=null&&!onField.hidden())hovered=onField.stack();
   int zi=zoneAt(mx,my);
   if(hovered.isEmpty()&&zi>=0&&zi<cards.size())hovered=cards.get(zi);
   if(hovered.isEmpty()&&!data.commander().isEmpty()&&mx>=12&&mx<81&&my>=zoneY())hovered=data.commander();
   if(!hovered.isEmpty()){
    int ph=Math.min(height-65,365),pw=Math.round(ph*.715f);
    int px=Math.max(6,Math.min(width-pw-8,mx+18)),py=Math.max(35,Math.min(height-ph-8,my-ph/2));
    g.fill(px-5,py-5,px+pw+5,py+ph+5,0xFFCFAC73);
    drawArt(g,hovered,px,py,pw,ph);
    g.drawString(font,font.plainSubstrByWidth(TcgCardMeta.displayName(hovered),pw),px+4,py+ph-12,0xFFFCE9B6);
    return;
   }
  }
  if(drag!=null&&drag.card()!=null){
   int px=mx-25,py=my-36;
   g.fill(px-2,py-2,px+54,py+78,0xFFFFD187);
   drawArt(g,drag.card(),px,py,52,76);
  }else{
   int index=zoneAt(mx,my);
   if(index>=0&&index<cards.size()){
    int pw=126,ph=180,px=Math.max(8,Math.min(width-pw-8,mx+18)),py=Math.max(35,Math.min(height-ph-9,my-150));
    g.fill(px-3,py-3,px+pw+3,py+ph+3,0xFFB59A70);
    drawArt(g,cards.get(index),px,py,pw,ph);
   }
  }
 }
}
