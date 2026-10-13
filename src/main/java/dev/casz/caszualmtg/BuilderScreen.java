package dev.casz.caszualmtg;

import com.spider.mtgcard.client.compat.*;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.components.*;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Inventory;
import org.lwjgl.util.tinyfd.TinyFileDialogs;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Full-viewport Builder: no controls or vanilla inventory slots overlap the card list. */
public final class BuilderScreen extends LegacyContainerScreen<BuilderMenu> {
 Wire.Reply data;
 EditBox url;
 int selected=-1,scroll=0,face=0;
 boolean commander=true;
 String status="";
 long lastRefresh;

 public BuilderScreen(BuilderMenu menu,Inventory inv,Component title){super(menu,inv,title,640,430);}

 public void update(Wire.Reply reply){
  data=reply;
  if(!reply.message().isBlank())status=reply.message();
  if(reply.message().startsWith("Draft cleared.")){
   selected=-1;scroll=0;face=0;
   if(url!=null)url.setValue("");
  }else if(url!=null&&!url.isFocused()&&!reply.url().equals(url.getValue())&&!reply.resolving()){
   url.setValue(reply.url());
  }
  commander=(reply.flags()&2)!=0;
  if(selected>=reply.rows().size())selected=-1;
  scroll=Math.clamp(scroll,0,Math.max(0,reply.rows().size()-visibleRows()));
 }

 int side(){return FullScreenMenuLayout.sidebarX(width);}
 int listWidth(){return FullScreenMenuLayout.browseWidth(width);}
 int listTop(){return 122;}
 int listHeight(){return FullScreenMenuLayout.browseHeight(height,listTop());}
 int visibleRows(){return Math.max(1,listHeight()/20);}
 int previewTop(){return 171;}
 int previewHeight(){return Math.max(112,Math.min(270,FullScreenMenuLayout.inventoryTop(height)-176));}
 int buildY(){return FullScreenMenuLayout.actionY(height);}
 void button(String label,int x,int y,int wide,Runnable action){
  addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(x,y,wide,20).build());
 }

 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,640,430))return;
  String previousUrl=url==null?(data==null?"":data.url()):url.getValue();
  // Use all available GUI pixels, not a fixed 640x430 floating panel.
  imageWidth=width;
  imageHeight=height;
  super.init();
  FullScreenMenuLayout.positionInventory(menu,1,height);
  FullScreenMenuLayout.position(menu.slots.getFirst(),side()+17,128);
  int right=width-FullScreenMenuLayout.MARGIN;
  url=addRenderableWidget(new EditBox(font,12,34,width-237,20,Component.literal("Archidekt URL")));
  url.setMaxLength(512);
  url.setHint(Component.literal("Paste an Archidekt deck URL"));
  url.setValue(previousUrl);
  button("Import URL",width-219,34,105,()->send("import_url",url.getValue(),commander?2:0));
  button("Reset",width-107,34,95,()->send("reset","",0));
  button("Import .txt",12,66,104,this::chooseFile);
  button("Paste list",122,66,100,()->importText(minecraft.keyboardHandler.getClipboard()));
  button("Check cards",228,66,110,()->send("plan","",commander?2:0));
  button(commander?"Commander: ON":"Commander: OFF",width-299,66,145,()->{
   commander=!commander;rebuildWidgets();
  });
  button("Shop missing",width-146,66,134,()->send("shop","",0));
  button("Build complete",12,buildY(),154,()->send("build","",commander?2:0));
  button("Build available",172,buildY(),154,()->send("build","",(commander?2:0)|1));
  button("Done",right-74,height-32,74,this::onClose);
 }

 @Override public void removed(){MtgGuiScaleHelper.restoreGuiScale(this);super.removed();}

 void send(String action,String text,int flags){
  if(!ClientPlayNetworking.canSend(Wire.Request.TYPE))return;
  ClientPlayNetworking.send(new Wire.Request(menu.pos,action,text,flags));
  status="Working…";
 }
 void chooseFile(){
  try{
   String path=TinyFileDialogs.tinyfd_openFileDialog("Import MTG decklist",minecraft.gameDirectory.getAbsolutePath(),null,"Decklist (*.txt)",false);
   if(path!=null)load(Path.of(path));
  }catch(Exception e){status="File picker unavailable. Drop a .txt file or paste the list.";}
 }
 @Override public void onFilesDrop(List<Path> files){if(!files.isEmpty())load(files.getFirst());}
 void load(Path path){
  try{
   if(!path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".txt")||Files.size(path)>24000){
    status="Choose a .txt file under 24 KB.";return;
   }
   importText(Files.readString(path,StandardCharsets.UTF_8));
  }catch(Exception e){status="Cannot open decklist file: "+e.getMessage();}
 }
 void importText(String text){
  if(text.length()>24000){status="Decklist is too long.";return;}
  send("import",text,commander?2:0);
 }
 @Override public boolean isPauseScreen(){return false;}
 @Override public void containerTick(){
  super.containerTick();
  if(data!=null&&data.resolving()&&++lastRefresh%60==0)send("refresh","",0);
 }

 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){
  g.fill(0,0,width,height,0xFF152032);
  g.fill(0,0,width,27,0xFF202F45);
  g.drawString(font,title,12,11,0xFFFFFFFF);
  String label=data==null?"Loading builder…":
    data.resolving()?"Resolving cards in background…":
    data.deck().isBlank()?"Import a decklist to begin.":data.message();
  g.drawString(font,font.plainSubstrByWidth(label,width-24),12,99,
    data!=null&&data.resolving()?0xFFFFD37E:0xFFB3DFFF);

  int bx=12,by=listTop(),bw=listWidth(),bh=listHeight();
  g.fill(bx-1,by-1,bx+bw+1,by+bh+1,0xFF41536C);
  g.fill(bx,by,bx+bw,by+bh,0xFF101B2A);
  if(data!=null){
   int rows=Math.min(visibleRows(),Math.max(0,data.rows().size()-scroll));
   for(int i=0;i<rows;i++){
    int index=scroll+i;
    var card=data.rows().get(index);
    int y=by+i*20;
    g.fill(bx,y,bx+bw,y+19,index==selected?0xFF365880:0xFF22324B);
    String line=(card.count()<0?"…":card.count()+"/"+card.requested())+" "+card.key();
    g.drawString(font,font.plainSubstrByWidth(line,bw-12),bx+6,y+6,
      card.count()<0?0xFFFFCC7A:card.count()>=card.requested()?0xFF90E8A0:0xFFFFD37E);
   }
   if(data.rows().isEmpty())
    g.drawString(font,"Import a URL, .txt file, or pasted decklist.",bx+8,by+12,0xFFB3DFFF);
  }

  int sidebar=side(),sidebarWidth=FullScreenMenuLayout.sidebarWidth(width);
  g.drawString(font,"Output deckbox",sidebar+43,132,0xFFB3DFFF);
  int py=previewTop(),ph=previewHeight();
  g.fill(sidebar+3,py-3,width-12,py+ph+3,0xFF34435C);
  g.fill(sidebar+4,py-2,width-13,py+ph+2,0xFF101B2A);
  if(data!=null&&selected>=0&&selected<data.rows().size())
   CaszualMtgClient.art(g,data.rows().get(selected).card(),face,sidebar+11,py+3,sidebarWidth-23,ph-6);
  else g.drawCenteredString(font,"Select a card to preview",sidebar+sidebarWidth/2,py+ph/2,0xFFB3DFFF);

  int reportTop=py+ph+13,reportMax=FullScreenMenuLayout.inventoryTop(height)-12;
  if(data!=null&&!data.report().isBlank()&&reportTop+12<reportMax){
   g.drawString(font,"Missing / availability",sidebar+4,reportTop,0xFFFFD37E);
   int ry=reportTop+14;
   for(String line:data.report().split("\\R")){
    if(line.isBlank())continue;
    if(ry+10>=reportMax)break;
    g.drawString(font,font.plainSubstrByWidth(line,sidebarWidth-12),sidebar+4,ry,0xFFFFCC88);
    ry+=13;
   }
  }

  g.drawString(font,"Your inventory",12,FullScreenMenuLayout.inventoryLabelY(height),0xFFB3DFFF);
  g.drawString(font,font.plainSubstrByWidth("Nearby catalogues / community storage: 4 blocks",width-228),
    204,FullScreenMenuLayout.inventoryLabelY(height),0xFF9CADC6);
  for(var slot:menu.slots){
   g.fill(slot.x-1,slot.y-1,slot.x+17,slot.y+17,0xFF91A5C1);
   g.fill(slot.x,slot.y,slot.x+16,slot.y+16,0xFF27364D);
  }
  if(!status.isEmpty())g.drawString(font,
    font.plainSubstrByWidth(status,width-310),202,FullScreenMenuLayout.statusY(height),0xFFFFDA8A);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}

 @Override public boolean mouseClicked(MouseButtonEvent event,boolean twice){
  int mx=(int)event.x(),my=(int)event.y();
  if(data!=null&&mx>=12&&mx<12+listWidth()&&my>=listTop()&&my<listTop()+listHeight()){
   int index=scroll+(my-listTop())/20;
   if(index<data.rows().size()&&(my-listTop())/20<visibleRows()){
    selected=index;face=0;return true;
   }
  }
  return super.mouseClicked(event,twice);
 }
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(data!=null&&mx>=12&&mx<12+listWidth()&&my>=listTop()&&my<listTop()+listHeight()){
   scroll=Math.clamp(scroll-(int)Math.signum(dy)*3,0,Math.max(0,data.rows().size()-visibleRows()));
   return true;
  }
  return super.mouseScrolled(mx,my,dx,dy);
 }
}
