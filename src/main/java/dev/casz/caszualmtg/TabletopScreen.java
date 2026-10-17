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
 String counterCard="",tokenText="";
 int traySelected=-1,tokenResultSelected=-1,trayScroll=0,tokenResultScroll=0;
 EditBox counterName,counterTotal,tokenSearch;
 int zoneScroll=0,tabScroll=0,ticks=0;
 String selectedCard="";
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
   ||data.reveal().isEmpty()!=reply.reveal().isEmpty();
  data=reply;
  if(reply.tiles().stream().noneMatch(t->t.pos().equals(view)))view=reply.seat();
  if(!reply.message().isBlank())message=reply.message();
  if(!reply.reveal().isEmpty())zone="reveal";
  else if(!reply.scry().isEmpty())zone="scry";
  else if(zone.equals("scry")||zone.equals("reveal")){zone="hand";scryBottom.clear();}
  if(!selectedCard.isBlank()&&reply.cards().stream().noneMatch(c->c.id().equals(selectedCard)))selectedCard="";
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
  zone=next;zoneScroll=0;selectedZone=-1;drag=null;rebuildWidgets();
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
 int boardCardW(){return Math.max(38,Math.min(70,boardW()/10));}
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
 void selectView(BlockPos target){view=target;selectedCard="";drag=null;rebuildWidgets();}
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
  button(tokenTrayOpen?"Tokens ▴":"Tokens ▾",ux,uy,94,()->{tokenTrayOpen=!tokenTrayOpen;counterOpen=false;rebuildWidgets();});
  button("Close",width-77,uy,64,this::onClose);
  if(menuMode.equals("draw")){
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
   if(data.cards().stream().anyMatch(c->c.id().equals(counterCard)&&
       Catalogue.isToken(com.spider.mtgcard.util.TcgCardMeta.read(c.stack()).typeLine())))
    button("Return to tray",px+12,py+111,118,()->{send("token_store",counterCard,data.seat(),0,0,0);counterOpen=false;rebuildWidgets();});
   button("Close",px+236,py+111,68,()->{counterOpen=false;rebuildWidgets();});
  }
  if(tokenTrayOpen){
   int px=tokenPanelX(),py=boardY()+10,pw=tokenPanelW();
   tokenSearch=addRenderableWidget(new EditBox(font,px+pw/2+7,py+25,pw/2-82,19,Component.literal("Token search")));
   tokenSearch.setMaxLength(120);tokenSearch.setValue(tokenText);
   button("Search",px+pw-71,py+25,65,()->searchTokens(0));
   button("◀",px+pw/2+6,py+51,24,()->{tokenResultScroll=0;searchTokens(Math.max(0,data.tokenPage()-1));});
   button("▶",px+pw/2+34,py+51,24,()->{tokenResultScroll=0;searchTokens(Math.min(50,data.tokenPage()+1));});
   button("Add selected",px+pw-119,py+51,113,()->{
    if(tokenResultSelected>=0&&tokenResultSelected<data.tokenResults().size())
     send("token_add",data.tokenResults().get(tokenResultSelected).key(),data.seat(),0,0,0);
    else message="Select a token search result.";
   });
   int foot=boardY()+boardH()-27;
   button("Play selected",px+7,foot,98,()->playSelectedToken());
   button("Remove",px+111,foot,68,()->{if(traySelected>=0)send("token_remove","",data.seat(),0,0,traySelected);});
   button("▲",px+184,foot,23,()->{trayScroll=Math.max(0,trayScroll-3);});
   button("▼",px+211,foot,23,()->{trayScroll=Math.min(Math.max(0,data.tray().size()-3),trayScroll+3);});
  }
  int by=handTop()+5;
  button("Hand",12,by,58,()->switchZone("hand"));
  button("GY",74,by,35,()->switchZone("grave"));
  button("Exile",112,by,53,()->switchZone("exile"));
  if(!data.reveal().isEmpty()){
   button("Reveal",169,by,58,()->switchZone("reveal"));
   button("Top → Hand",width-310,by,100,()->action("reveal_to_hand",0));
   button("Top → Field",width-205,by,100,()->{
    message="Drag the first revealed card into the battlefield.";});
   button("Rest → Bottom",width-100,by,90,()->action("reveal_end",0));
  }else if(!data.scry().isEmpty()){
   button("Scry",169,by,48,()->switchZone("scry"));
   button("Resolve",width-185,by,84,this::resolveScry);
   button("Cancel",width-97,by,84,()->action("scry_cancel",0));
  }else{
   button("To Hand",width-385,by,78,()->tableAction("return"));
   button("To GY",width-302,by,66,()->tableAction("grave"));
   button("Exile Card",width-232,by,81,()->tableAction("exile"));
   button("Cmd Zone",width-146,by,84,()->tableAction("commander_home"));
   button("◀",width-60,by,23,()->{zoneScroll=Math.max(0,zoneScroll-visibleHandCards());});
   button("▶",width-34,by,23,()->{zoneScroll+=visibleHandCards();});
  }
 }
 int tokenPanelW(){return Math.min(485,Math.max(352,width-58));}
 int tokenPanelX(){return (width-tokenPanelW())/2;}
 boolean inTokenPanel(int x,int y){return tokenTrayOpen&&x>=tokenPanelX()&&x<tokenPanelX()+tokenPanelW()&&y>=boardY()+10&&y<=boardY()+boardH()-2;}
 boolean inCounterPanel(int x,int y){return counterOpen&&x>=Math.max(14,width-330)&&x<width-12&&y>=boardY()+13&&y<boardY()+151;}
 void searchTokens(int page){tokenText=tokenSearch==null?tokenText:tokenSearch.getValue();tokenResultSelected=-1;send("token_query",tokenText,data.seat(),0,0,page);}
 void playSelectedToken(){
  if(traySelected<0||traySelected>=data.tray().size()){message="Select a token in your tray first.";return;}
  send("token_play","",view,500,500,traySelected);
 }
 void counterPreset(String name){if(counterName!=null)counterName.setValue(name);if(counterTotal!=null)counterTotal.setValue(Integer.toString(counterCount(name)));}
 int counterCount(String name){
  for(var c:data.cards())if(c.id().equals(counterCard))return TabletopCardStats.counters(c.stack()).getOrDefault(name.trim().toLowerCase(Locale.ROOT),0);
  return 0;
 }
 void changeCounter(int amount){if(counterName==null)return;String name=counterName.getValue().trim().toLowerCase(Locale.ROOT);int total=Math.max(0,Math.min(1000000,counterCount(name)+amount));send("counter_set",counterCard+"|"+name,data.seat(),0,0,total);counterTotal.setValue(Integer.toString(total));}
 void setCounter(boolean remove){
  if(counterName==null||counterTotal==null)return;
  String name=counterName.getValue().trim().toLowerCase(Locale.ROOT);
  int amount=0;
  if(!remove)try{amount=Integer.parseInt(counterTotal.getValue());}catch(NumberFormatException ex){message="Use a numeric counter total.";return;}
  if(amount<0||amount>1000000||name.isBlank()||name.length()>40){message="Invalid counter name or total.";return;}
  send("counter_set",counterCard+"|"+name,data.seat(),0,0,amount);
 }
 void resolveScry(){
  List<Integer> first=new ArrayList<>(),second=new ArrayList<>();
  for(int i=0;i<data.scry().size();i++)(scryBottom.contains(i)?second:first).add(i);
  String top=first.stream().map(String::valueOf).collect(Collectors.joining(","));
  String bottom=second.stream().map(String::valueOf).collect(Collectors.joining(","));
  send("scry_commit",top+"|"+bottom,data.seat(),0,0,0);
 }
 void tableAction(String name){
  if(!selectedCard.isBlank())send(name,selectedCard,data.seat(),0,0,0);
  else if(name.equals("return")&&(zone.equals("grave")||zone.equals("exile"))&&selectedZone>=0){
   List<TabletopWire.ZoneCard> list=zone.equals("grave")?data.grave():data.exile();
   if(selectedZone<list.size())send("zone_to_hand","",data.seat(),0,0,list.get(selectedZone).slot());
  }
 }
 boolean own(TabletopWire.Card c){
  var me=Minecraft.getInstance().player;
  return me!=null&&c.owner().equals(me.getUUID().toString());
 }
 @Override public boolean mouseClicked(MouseButtonEvent event,boolean twice){
  int x=(int)event.x(),y=(int)event.y();
  if(inCounterPanel(x,y))return super.mouseClicked(event,twice);
  if(inTokenPanel(x,y)){
   int px=tokenPanelX(),py=boardY()+10,pw=tokenPanelW(),start=py+79;
   int visible=Math.max(2,(boardH()-119)/15);
   if(y>=start&&y<start+visible*15){
    int row=(y-start)/15;
    if(x<px+pw/2){
     int at=trayScroll+row;
     if(at<data.tray().size()){
      traySelected=at;
      if(event.button()==0)drag=new Drag("token","",at,data.tray().get(at),x,y);
     }
    }else{
     int at=tokenResultScroll+row;
     if(at<data.tokenResults().size())tokenResultSelected=at;
    }
    return true;
   }
   return super.mouseClicked(event,twice);
  }
  if(boardHit(x,y)){
   TabletopWire.Card c=cardAt(x,y);
   if(c!=null){selectedCard=c.id();selectedZone=-1;
    if(event.button()==1){
     if(own(c)&&!c.hidden()){counterCard=c.id();counterOpen=true;tokenTrayOpen=false;rebuildWidgets();}
     else message="Counters can only be changed on your face-up cards.";
     return true;
    }
    if(own(c)&&event.button()==0)drag=new Drag("board",c.id(),-1,c.stack(),x,y);
    return true;
   }
  }
  if(!data.commander().isEmpty()&&x>=12&&x<81&&y>=zoneY()&&y<zoneY()+handCardH()){
   drag=new Drag("commander","",-1,data.commander(),x,y);selectedZone=-1;return true;
  }
  int idx=zoneAt(x,y);
  if(idx>=0){
   selectedCard="";selectedZone=idx;
   if(discardMode&&zone.equals("hand")){
    action("mulligan_discard",idx);discardMode=false;
   }else if(zone.equals("scry")){
    if(!scryBottom.add(idx))scryBottom.remove(idx);
   }else{
    String source=zone;
    if(!source.equals("reveal")||idx==0)drag=new Drag(source,"",idx,zoneCards().get(idx),x,y);
   }
   return true;
  }
  return super.mouseClicked(event,twice);
 }
 @Override public boolean mouseReleased(MouseButtonEvent event){
  if(drag!=null){
   Drag held=drag;drag=null;
   int mx=(int)event.x(),my=(int)event.y();
   if(boardHit(mx,my)&&view!=null&&!inTokenPanel(mx,my)&&!inCounterPanel(mx,my)){
    int x=xNormalized(mx),y=yNormalized(my);
    switch(held.source()){
     case "board" -> {
      if(Math.abs(mx-held.startX())>3||Math.abs(my-held.startY())>3)
       send("move",held.id(),view,x,y,0);
      else send("tap",held.id(),view,0,0,0);
     }
     case "hand" -> send("put_hand","",view,x,y,held.index());
     case "grave" -> {
      if(held.index()<data.grave().size())send("put_grave","",view,x,y,data.grave().get(held.index()).slot());
     }
     case "exile" -> {
      if(held.index()<data.exile().size())send("put_exile","",view,x,y,data.exile().get(held.index()).slot());
     }
     case "commander" -> send("play_commander","",view,x,y,0);
     case "token" -> send("token_play","",view,x,y,held.index());
     case "reveal" -> {if(held.index()==0)send("reveal_to_field","",view,x,y,0);}
    }
   }
   return true;
  }
  return super.mouseReleased(event);
 }
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(my>=handTop()){
   int max=Math.max(0,zoneCards().size()-visibleHandCards());
   zoneScroll=Math.clamp(zoneScroll-(int)Math.signum(dy)*3,0,max);
   return true;
  }
  return super.mouseScrolled(mx,my,dx,dy);
 }
 @Override public void tick(){
  super.tick();
  if(++ticks%25==0)send("refresh","",data.seat(),0,0,0);
 }
 @Override public boolean isPauseScreen(){return false;}
 int darken(int rgb){
  int r=(rgb>>16&255)*57/100+12,g=(rgb>>8&255)*57/100+12,b=(rgb&255)*57/100+12;
  return 0xFF000000|(r<<16)|(g<<8)|b;
 }
 void drawArt(GuiGraphics g,ItemStack stack,int x,int y,int w,int h){
  if(stack==null||stack.isEmpty()){
   g.fill(x,y,x+w,y+h,0xFF22364E);
   g.drawCenteredString(font,"MTG",x+w/2,y+h/2-4,0xFFEAD29C);
  }else CaszualMtgClient.art(g,stack,TcgCardMeta.read(stack).face(),x,y,w,h);
 }
 @Override public void render(GuiGraphics g,int mx,int my,float delta){
  g.fill(0,0,width,height,0xFF121B28);
  g.fill(0,0,width,34,0xFF202D3B);
  TabletopWire.Tile tile=shown();
  // The active seat is highlighted independently of which battlefield we are viewing.
  int tabx=12,maxTabs=Math.max(1,(width-95)/137);
  for(int i=tabScroll;i<Math.min(data.tiles().size(),tabScroll+maxTabs);i++){
   TabletopWire.Tile t=data.tiles().get(i);
   int rgb=0xFF000000|(t.color()&0xFFFFFF);
   if(t.pos().equals(view))g.fill(tabx-2,5,tabx+134,30,rgb);
   else if(t.active())g.fill(tabx-2,5,tabx+134,30,0xFF7A6A38);
   tabx+=137;
  }
  g.fill(boardX()-3,boardY()-3,boardX()+boardW()+3,boardY()+boardH()+3,0xFF7D6548);
  int bg=tile==null?0xFF2D453B:darken(tile.color());
  g.fill(boardX(),boardY(),boardX()+boardW(),boardY()+boardH(),bg);
  if(tile!=null)g.drawString(font,tile.owner().isBlank()?"Empty table":tile.owner()+"'s battlefield"+(tile.active()?"  •  CURRENT TURN":""),boardX()+8,boardY()+7,0xFFE5F3E7);
  for(var c:displayed()){
   int x=cardX(c),y=cardY(c),cw=boardCardW(),ch=boardCardH();
   boolean chosen=c.id().equals(selectedCard);
   // Rotate card art and selection border together. The server keeps original
   // coordinates, so tapped/untapped cards never shift their anchor position.
   if(c.tapped()){
    var pose=g.pose();
    pose.pushMatrix();
    pose.translate(x+cw/2.0f,y+ch/2.0f);
    pose.rotate((float)(Math.PI/2.0));
    pose.translate(-x-cw/2.0f,-y-ch/2.0f);
   }
   g.fill(x-2,y-2,x+cw+2,y+ch+2,chosen?0xFFFFD078:c.tapped()?0xFF98BDEB:0xFF19212D);
   if(c.hidden())drawArt(g,ItemStack.EMPTY,x,y,cw,ch);
   else drawArt(g,c.stack(),x,y,cw,ch);
   if(c.tapped())g.pose().popMatrix();
  }
  // Overlays are drawn in screen orientation even on sideways (tapped) cards,
  // keeping P/T and counters readable at their actual visible lower-right edge.
  for(var card:displayed()){
   if(card.hidden()||card.stack().isEmpty())continue;
   int x=cardX(card),y=cardY(card),w=boardCardW(),h=boardCardH();
   int left=card.tapped()?x+(w-h)/2:x,top=card.tapped()?y+(h-w)/2:y;
   int bw=card.tapped()?h:w,bh=card.tapped()?w:h;
   String pt=TabletopCardStats.powerToughness(card.stack());
   if(!pt.isEmpty()){
    int labelW=Math.max(30,font.width(pt)+12),bx=left+bw-labelW,by=top+bh-14;
    g.fill(bx,by,bx+labelW,by+14,0xF0192636);
    g.fill(bx,by,bx+labelW,by+1,0xFFE6C079);
    g.drawCenteredString(font,pt,bx+labelW/2,by+3,0xFFFFFFFF);
   }
   int line=0;
   for(var counter:TabletopCardStats.counters(card.stack()).entrySet()){
    if(line>=3)break;
    String label=counter.getKey()+" ×"+counter.getValue();
    int lw=Math.min(bw-2,Math.max(22,font.width(label)+9)),ly=top+line*13;
    g.fill(left,ly,left+lw,ly+12,0xF0273650);
    g.drawString(font,font.plainSubstrByWidth(label,lw-6),left+3,ly+2,0xFFFFE19F);
    line++;
   }
  }
  if(tokenTrayOpen){
   int px=tokenPanelX(),py=boardY()+10,pw=tokenPanelW(),bottom=boardY()+boardH()-2;
   g.fill(px,py,px+pw,bottom,0xF11A2839);
   g.fill(px+4,py+4,px+pw-4,py+22,0xFF334B61);
   g.drawString(font,"TOKEN TRAY  "+data.tray().size()+"/32",px+10,py+9,0xFFF5DAAA);
   g.drawString(font,"Search / catalogue",px+pw/2+8,py+9,0xFFCCE3EF);
   g.drawString(font,"Stored templates · drag to field",px+8,py+53,0xFFB4CADB);
   int start=py+79,visible=Math.max(2,(boardH()-119)/15);
   for(int i=0;i<visible;i++){
    int at=trayScroll+i,yy=start+i*15;
    if(at<data.tray().size()){
     g.fill(px+5,yy,px+pw/2-4,yy+14,at==traySelected?0xFF557495:0xFF26384C);
     String name=com.spider.mtgcard.util.TcgCardMeta.displayName(data.tray().get(at));
     g.drawString(font,font.plainSubstrByWidth(name,pw/2-18),px+9,yy+3,0xFFFFFFFF);
    }
    int found=tokenResultScroll+i;
    if(found<data.tokenResults().size()){
     g.fill(px+pw/2+4,yy,px+pw-6,yy+14,found==tokenResultSelected?0xFF557495:0xFF26384C);
     String name=com.spider.mtgcard.util.TcgCardMeta.displayName(data.tokenResults().get(found).stack());
     g.drawString(font,font.plainSubstrByWidth(name,pw/2-18),px+pw/2+8,yy+3,0xFFFFFFFF);
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
   var onField=cardAt(mx,my);
   if(onField!=null&&!onField.hidden())hovered=onField.stack();
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
