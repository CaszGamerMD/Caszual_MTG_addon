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

/** Native deckbox output slot, persistent server draft and plan preview. */
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
  if(url!=null&&reply.message().contains("cleared"))url.setValue("");
  else if(url!=null&&!url.isFocused()&&!reply.url().equals(url.getValue())&&!reply.resolving())url.setValue(reply.url());
  commander=(reply.flags()&2)!=0;
 }
 @Override protected void init(){
  if(MtgGuiScaleHelper.applyAutoFitGuiScale(this,3,640,430))return;
  super.init();
  String currentUrl=url==null?(data==null?"":data.url()):url.getValue();
  url=addRenderableWidget(new EditBox(font,leftPos+12,topPos+32,402,20,Component.literal("Archidekt URL")));
  url.setMaxLength(512);url.setHint(Component.literal("Paste an Archidekt deck URL"));
  url.setValue(currentUrl);
  button("Import URL",422,32,108,()->send("import_url",url.getValue(),commander?2:0));
  button("Reset",536,32,90,()->send("reset","",0));
  button("Import .txt",12,60,104,this::chooseFile);
  button("Paste list",122,60,100,()->importText(minecraft.keyboardHandler.getClipboard()));
  button("Check cards",228,60,110,()->send("plan","",commander?2:0));
  button(commander?"Commander: ON":"Commander: OFF",346,60,142,()->{commander=!commander;rebuildWidgets();});
  button("Shop missing",494,60,132,()->send("shop","",0));
  button("Build complete",12,284,154,()->send("build","",commander?2:0));
  button("Build available",172,284,154,()->send("build","",(commander?2:0)|1));
  button("Done",544,402,82,this::onClose);
 }
 @Override public void removed(){MtgGuiScaleHelper.restoreGuiScale(this);super.removed();}
 void button(String label,int x,int y,int width,Runnable action){
  addRenderableWidget(Button.builder(Component.literal(label),b->action.run()).bounds(leftPos+x,topPos+y,width,20).build());
 }
 void send(String action,String text,int flags){
  if(!ClientPlayNetworking.canSend(Wire.Request.TYPE))return;
  ClientPlayNetworking.send(new Wire.Request(menu.pos,action,text,flags));status="Working…";
 }
 void chooseFile(){
  try{String path=TinyFileDialogs.tinyfd_openFileDialog("Import MTG decklist",minecraft.gameDirectory.getAbsolutePath(),null,"Decklist (*.txt)",false);
   if(path!=null)load(Path.of(path));
  }catch(Exception e){status="File picker unavailable. Drop a .txt file or paste the list.";}
 }
 @Override public void onFilesDrop(List<Path> files){if(!files.isEmpty())load(files.getFirst());}
 void load(Path path){
  try{
   if(!path.getFileName().toString().toLowerCase(Locale.ROOT).endsWith(".txt")||Files.size(path)>24000){status="Choose a .txt file under 24 KB.";return;}
   importText(Files.readString(path,StandardCharsets.UTF_8));
  }catch(Exception e){status="Cannot open decklist file: "+e.getMessage();}
 }
 void importText(String text){if(text.length()>24000){status="Decklist is too long.";return;}send("import",text,commander?2:0);}
 @Override public boolean isPauseScreen(){return false;}
 @Override public void containerTick(){
  super.containerTick();
  if(data!=null&&data.resolving()&&++lastRefresh%60==0)send("refresh","",0);
 }
 @Override protected void renderBg(GuiGraphics g,float delta,int mx,int my){
  int x=leftPos,y=topPos;g.fill(x,y,x+640,y+430,0xFF152032);
  g.drawString(font,title,x+12,y+12,0xFFFFFFFF);
  String label=data==null?"Loading builder…":data.resolving()?"Resolving cards in background…":data.deck().isBlank()?"Import a decklist to begin.":data.message();
  g.drawString(font,font.plainSubstrByWidth(label,610),x+12,y+88,data!=null&&data.resolving()?0xFFFFD37E:0xFFB3DFFF);
  if(data!=null){
   int yRow=y+115;
   for(int i=scroll;i<Math.min(data.rows().size(),scroll+9);i++){
    var r=data.rows().get(i);
    g.fill(x+12,yRow,x+408,yRow+18,i==selected?0xFF365880:0xFF22324B);
    String line=(r.count()<0?"…":r.count()+"/"+r.requested())+" "+r.key();
    g.drawString(font,font.plainSubstrByWidth(line,385),x+18,yRow+5,r.count()<0?0xFFFFCC7A:r.count()>=r.requested()?0xFF90E8A0:0xFFFFD37E);
    yRow+=19;
   }
   if(selected>=0&&selected<data.rows().size())
    CaszualMtgClient.art(g,data.rows().get(selected).card(),face,x+434,y+116,176,160);
   int i=0;
   for(String line:data.report().split("\\R")){if(line.isBlank()||i>=3)break;g.drawString(font,font.plainSubstrByWidth(line,400),x+12,y+312+i*13,0xFFFFC98B);i++;}
  }
  g.drawString(font,"Output deckbox",x+452,y+42,0xFFB3DFFF);
  g.drawString(font,"Card sources: nearby catalogues / community storage (4 blocks)",x+12,y+376,0xFF9CADC6);
  g.drawString(font,"Your inventory",x+12,y+305,0xFFB3DFFF);
  for(var slot:menu.slots){g.fill(x+slot.x-1,y+slot.y-1,x+slot.x+17,y+slot.y+17,0xFF91A5C1);g.fill(x+slot.x,y+slot.y,x+slot.x+16,y+slot.y+16,0xFF27364D);}
  if(!status.isEmpty())g.drawString(font,font.plainSubstrByWidth(status,520),x+12,y+404,0xFFFFDA8A);
 }
 @Override protected void renderLabels(GuiGraphics g,int mx,int my){}
 @Override public boolean mouseClicked(MouseButtonEvent e,boolean twice){
  int cx=(int)e.x()-leftPos-12,cy=(int)e.y()-topPos-115;
  if(data!=null&&cx>=0&&cx<408&&cy>=0&&cy<171){
   int index=scroll+cy/19;if(index<data.rows().size()){selected=index;face=0;return true;}
  }
  return super.mouseClicked(e,twice);
 }
 @Override public boolean mouseScrolled(double mx,double my,double dx,double dy){
  if(data!=null&&mx>=leftPos+12&&mx<leftPos+420&&my>=topPos+115&&my<topPos+286){
   scroll=Math.clamp(scroll-(int)Math.signum(dy)*3,0,Math.max(0,data.rows().size()-9));return true;
  }
  return super.mouseScrolled(mx,my,dx,dy);
 }
}
