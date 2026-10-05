package dev.casz.mtg;
import com.spider.mtgcard.client.compat.GuiGraphics;
import com.spider.mtgcard.util.TcgCardMeta;
import net.minecraft.client.gui.Font;
import java.util.List;
/** The same four-column grid layout and hit-testing serve all three databases. */
public final class CardBrowser {
 public static int cellWidth(int width){return (width-18)/4;}
 public static int cellHeight(int width){return Math.round((cellWidth(width)-8)/.716f)+22;}
 public static int visible(int width,int height,boolean grid){return grid?4*Math.max(1,height/cellHeight(width)):Math.max(1,height/24);}
 public static int clampScroll(int offset,int count,int width,int height,boolean grid){int visible=visible(width,height,grid);if(grid){int rows=(count+3)/4,shown=visible/4;return Math.clamp(offset/4,0,Math.max(0,rows-shown))*4;}return Math.clamp(offset,0,Math.max(0,count-visible));}
 public static int hit(int mx,int my,int x,int y,int width,int height,int scroll,int count,boolean grid){if(mx<x||mx>=x+width||my<y||my>=y+height)return -1;int at;if(grid){int cw=cellWidth(width),ch=cellHeight(width),column=(mx-x)/(cw+6),row=(my-y)/ch;if(column>=4||(mx-x)%(cw+6)>=cw||row>=visible(width,height,true)/4)return -1;at=scroll+row*4+column;}else{int row=(my-y)/24;if(row>=visible(width,height,false))return -1;at=scroll+row;}return at<count?at:-1;}
 public static void render(GuiGraphics g,Font font,List<Wire.Row> rows,int x,int y,int width,int height,int scroll,int selected,boolean grid,boolean art){int visible=visible(width,height,grid);for(int i=0;i<visible;i++){int at=scroll+i;if(at>=rows.size())break;var row=rows.get(at);var meta=TcgCardMeta.read(row.card());String printing=meta.set().toUpperCase(java.util.Locale.ROOT)+" #"+meta.collectorNumber();String count=row.count()<0?"∞":Long.toString(row.count());if(grid){int cw=cellWidth(width),ch=cellHeight(width),cx=x+(i%4)*(cw+6),cy=y+(i/4)*ch;g.fill(cx,cy,cx+cw,cy+ch-3,at==selected?0xFF4B729F:0xFF22324B);ClientCompanion.art(g,row.card(),0,cx+4,cy+3,cw-8,ch-24);g.drawString(font,font.plainSubstrByWidth(meta.name(),cw-8),cx+4,cy+ch-20,0xFFFFFFFF);g.drawString(font,font.plainSubstrByWidth(art?printing:"Copies: "+count,cw-8),cx+4,cy+ch-10,0xFFB3DFFF);}else{int ry=y+i*24;g.fill(x,ry,x+width,ry+22,at==selected?0xFF365880:0xFF22324B);String label=meta.name()+" ["+count+"]"+(art?" · "+printing:"");g.drawString(font,font.plainSubstrByWidth(label,width-12),x+6,ry+7,0xFFFFFFFF);}}}
}
