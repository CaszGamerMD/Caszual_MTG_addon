package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.components.*;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStack;

public final class HandScreen extends LegacyScreen {
 HandWire.Reply data;EditBox playerName,staffLeft,staffRight;int x,y,w,h,scroll,selected=-1,ticks;final java.util.LinkedHashSet<Integer> chosen=new java.util.LinkedHashSet<>();String message="";boolean mulliganMenu;
 HandScreen(HandWire.Reply data){super(Component.literal("Card Hand"));this.data=data;}
 void update(HandWire.Reply reply){
  boolean controlsChanged=data.authorized()!=reply.authorized()||data.canManage()!=reply.canManage()||data.revealAll()!=reply.revealAll()||data.pendingDiscards()!=reply.pendingDiscards()||data.hasStaff()!=reply.hasStaff();
  data=reply;if(!reply.message().isBlank()){message=reply.message();chosen.clear();selected=-1;}chosen.removeIf(i->i>=reply.cards().size());if(selected>=reply.cards().size())selected=-1;
  if(reply.pendingDiscards()>0)mulliganMenu=false;
  if(reply.message().startsWith("Applied ")&&staffLeft!=null&&staffRight!=null){
   staffLeft.setValue(reply.staffLeft());staffRight.setValue(reply.staffRight());
  }
  if(controlsChanged)rebuildWidgets();
 }
 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,640,430))return;
  w=Math.max(1,width-16);h=Math.max(1,height-16);x=(width-w)/2;y=(height-h)/2;clearWidgets();
  button("Refresh",x+12,y+32,72,()->send("refresh",""));
  if(data.authorized())button(data.revealAll()?"Hide from all":"Reveal to all",x+90,y+32,112,()->send("reveal",""));
  if(data.canManage()){
   button("Link Deck Control",x+208,y+32,124,()->{send("link","");onClose();});
   playerName=addRenderableWidget(new EditBox(font,x+12,y+58,150,20,Component.literal("Player")));playerName.setMaxLength(32);playerName.setHint(Component.literal("Online player name"));
   button("Add viewer",x+168,y+58,86,()->send("add_viewer",playerName.getValue()));
   button("Remove viewer",x+260,y+58,102,()->send("remove_viewer",playerName.getValue()));
  }
  if(data.authorized()){
   button("Deposit inventory cards",x+370,y+58,176,()->send("deposit_inventory",""));
   if(data.pendingDiscards()==0){button("Select all",x+370,y+84,88,()->{chosen.clear();for(int i=0;i<data.cards().size();i++)chosen.add(i);});button("Clear",x+464,y+84,72,chosen::clear);}
   if(data.pendingDiscards()>0){
    button("Discard selected ("+data.pendingDiscards()+")",x+12,y+84,168,()->sendSelected("discard_selected"));
   }else if(mulliganMenu){
    button("Friendly",x+12,y+84,92,()->send("mulligan_friendly",""));
    button("Strict"+(data.strictMulligans()>0?" ("+data.strictMulligans()+")":""),x+110,y+84,104,()->send("mulligan_strict",""));
    button("Cancel",x+220,y+84,86,()->{mulliganMenu=false;send("mulligan_cancel","");rebuildWidgets();});
   }else{
    button("Take selected",x+12,y+84,108,()->sendManySelected());
    button("Random → Graveyard",x+126,y+84,142,()->send("discard_random",""));
    button("Mulligan",x+274,y+84,90,()->{mulliganMenu=true;rebuildWidgets();});
   }
  }
  if(data.hasStaff()&&data.authorized()){
   int sidebar=x+w-144;
   staffLeft=addRenderableWidget(new EditBox(font,sidebar,y+164,106,20,Component.literal("Left click color")));
   staffLeft.setMaxLength(7);staffLeft.setValue(data.staffLeft());
   staffRight=addRenderableWidget(new EditBox(font,sidebar,y+212,106,20,Component.literal("Right click color")));
   staffRight.setMaxLength(7);staffRight.setValue(data.staffRight());
   button("Apply to all staffs",sidebar,y+240,135,()->{
    String left=staffLeft.getValue(),right=staffRight.getValue();
    if(!StaffColors.valid(left)||!StaffColors.valid(right)){
     message="Use #RRGGBB in both color fields.";return;
    }
    send("staff_colors",left+","+right);
   });
  }else{staffLeft=null;staffRight=null;}
  button("Done",x+w-84,y+h-30,72,this::onClose);
 }
 void button(String label,int bx,int by,int bw,Runnable run){addRenderableWidget(Button.builder(Component.literal(label),b->run.run()).bounds(bx,by,bw,20).build());}
 void sendSelected(String action){if(selected<0||selected>=data.cards().size()){message="Select a card first.";return;}send(action,Integer.toString(selected));}
 void sendManySelected(){if(chosen.isEmpty()){message="Select one or more cards first.";return;}send("take_selected",chosen.stream().sorted().map(String::valueOf).collect(java.util.stream.Collectors.joining(",")));}
 void send(String action,String text){ClientPlayNetworking.send(new HandWire.Request(data.pos(),action,text));message="Working…";}
 @Override public void tick(){super.tick();if(++ticks%20==0)ClientPlayNetworking.send(new HandWire.Request(data.pos(),"refresh",""));}
 static void colorSwatch(GuiGraphics g,String value,int bx,int by){
  g.fill(bx-1,by-1,bx+21,by+19,0xFFACBAD0);
  g.fill(bx,by,bx+20,by+18,StaffColors.valid(value)?0xFF000000|StaffColors.rgb(value):0xFF52202B);
 }
 @Override public boolean isPauseScreen(){return false;}
 int gridTop(){return 142;}
 int gridCols(){return Math.max(3,Math.min(8,(w-150)/78));}
 int gridRows(){return Math.max(1,(h-gridTop()-42)/112);}
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(!data.visible())return true;int cols=gridCols(),visibleRows=gridRows(),rows=(data.cards().size()+cols-1)/cols;
  scroll=Math.clamp(scroll-(int)Math.signum(dy),0,Math.max(0,rows-visibleRows));return true;
 }
 @Override public boolean mouseClicked(MouseButtonEvent e,boolean twice){
  if(data.visible()){
   int gx=x+12,gy=y+gridTop(),cw=78,ch=112,cols=gridCols(),rows=gridRows();int relX=(int)e.x()-gx,relY=(int)e.y()-gy;
   if(relX>=0&&relY>=0&&relX<cols*cw&&relY<rows*ch){
    int col=relX/cw,row=relY/ch,at=(scroll+row)*cols+col;if(at>=0&&at<data.cards().size()){selected=at;if(!chosen.add(at))chosen.remove(at);return true;}
   }
  }
  return super.mouseClicked(e,twice);
 }
 @Override public void render(GuiGraphics g,int mx,int my,float delta){
  g.fill(0,0,width,height,0xC0080E18);g.fill(x,y,x+w,y+h,0xFF152032);g.drawString(font,title,x+12,y+12,0xFFFFFFFF);
  String privacy=data.revealAll()?"REVEALED TO ALL":data.visible()?"PRIVATE · YOU CAN VIEW":"PRIVATE · HIDDEN";
  g.drawString(font,privacy+" · "+data.count()+"/"+HandBlockEntity.SIZE+" cards · "+chosen.size()+" selected · Deck Control: "+data.linked(),x+12,y+112,data.revealAll()?0xFFFFD37E:0xFFB3DFFF);
  if(data.canManage())g.drawString(font,"Viewers: "+(data.viewers().isEmpty()?"none":String.join(", ",data.viewers())),x+12,y+124,0xFF9CADC6);
  if(data.pendingDiscards()>0)g.drawString(font,"Strict mulligan: discard "+data.pendingDiscards()+" selected card"+(data.pendingDiscards()==1?"":"s")+" to finish.",x+370,y+88,0xFFFFD37E);
  else if(mulliganMenu)g.drawString(font,"Friendly is free · Strict attempts: "+data.strictMulligans()+" · Cancel finishes mulligans.",x+320,y+88,0xFFB3DFFF);
  else g.drawString(font,"Click cards to toggle multi-select · Right-click podium to add.",x+370,y+88,0xFF9CADC6);
  if(!data.visible()){
   g.drawCenteredString(font,"This hand is private.",x+w/2,y+220,0xFFFFFFFF);
   g.drawCenteredString(font,"The owner can add you as a viewer or reveal the hand.",x+w/2,y+242,0xFF9CADC6);
  }else{
   int gx=x+12,gy=y+gridTop(),cw=78,ch=112,cols=gridCols(),rows=gridRows();
   for(int row=0;row<rows;row++)for(int col=0;col<cols;col++){
    int at=(scroll+row)*cols+col;if(at>=data.cards().size())continue;int cx=gx+col*cw,cy=gy+row*ch;
    g.fill(cx,cy,cx+72,cy+106,chosen.contains(at)?0xFF4B729F:0xFF22324B);CaszualMtgClient.art(g,data.cards().get(at),0,cx+3,cy+3,66,100);
   }
   if(data.hasStaff()&&data.authorized()){
    if(selected>=0&&selected<data.cards().size()){
     ItemStack card=data.cards().get(selected);
     CaszualMtgClient.art(g,card,0,x+w-116,y+264,104,96);
    }
   }else if(selected>=0&&selected<data.cards().size()){
    ItemStack card=data.cards().get(selected);
    CaszualMtgClient.art(g,card,0,x+w-116,y+gridTop(),104,145);
   }
  }
  if(data.hasStaff()&&data.authorized()&&staffLeft!=null&&staffRight!=null){
   int bx=x+w-144;
   g.drawString(font,"LEFT CLICK",bx,y+146,0xFFB3DFFF);
   g.drawString(font,"RIGHT CLICK",bx,y+194,0xFFB3DFFF);
   colorSwatch(g,staffLeft.getValue(),bx+110,y+165);
   colorSwatch(g,staffRight.getValue(),bx+110,y+213);
  }
  if(!message.isBlank())g.drawString(font,font.plainSubstrByWidth(message,w-110),x+12,y+h-22,0xFFFFDA8A);
  super.render(g,mx,my,delta);
 }
}
