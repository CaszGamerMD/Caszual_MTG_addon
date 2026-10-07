package dev.casz.mtg;
import dev.casz.mtg.mixin.ContainerAccess;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.networking.v1.*;
import net.fabricmc.fabric.api.client.screen.v1.*;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.EntityHitResult;
import com.spider.mtgcard.api.CardItemRegistry;
import com.spider.mtgcard.client.compat.GuiGraphics;
import com.spider.mtgcard.client.java.CardArtManager;
import com.spider.mtgcard.display.CardDisplayEntity;
import com.spider.mtgcard.util.*;
import net.minecraft.client.renderer.RenderPipelines;
import java.util.*;
import org.lwjgl.glfw.GLFW;
public final class ClientCompanion implements ClientModInitializer {
 static final Map<Screen,Preview> previews=new WeakHashMap<>();
 static final class Preview {ItemStack card=ItemStack.EMPTY;int face;boolean shown;}
 public void onInitializeClient(){
  CustomBoxModels.register();
  net.minecraft.client.gui.screens.MenuScreens.register(Companion.COMMUNITY_MENU,CommunityScreen::new);
  ClientPlayNetworking.registerGlobalReceiver(Wire.Reply.TYPE,(reply,ctx)->{if(reply.kind()==2){if(ctx.client().gui.screen() instanceof CommunityScreen screen&&screen.getMenu().pos.equals(reply.pos()))screen.update(reply);return;}if(ctx.client().gui.screen() instanceof BankScreen screen&&screen.pos.equals(reply.pos())&&screen.kind==reply.kind())screen.update(reply);else if(!(ctx.client().gui.screen() instanceof BankScreen))ctx.client().gui.setScreen(new BankScreen(reply));});
  ClientPlayNetworking.registerGlobalReceiver(HandWire.Reply.TYPE,(reply,ctx)->{if(ctx.client().gui.screen() instanceof HandScreen screen&&screen.data.pos().equals(reply.pos()))screen.update(reply);else if(reply.message().equals("Hand ready."))ctx.client().gui.setScreen(new HandScreen(reply));});
  ClientPlayNetworking.registerGlobalReceiver(DeckboxRefreshWire.Refresh.TYPE,(refresh,ctx)->{
   var pos=refresh.pos();
   if(ctx.client().level!=null)ctx.client().levelRenderer.allChanged();
  });
  ClientPlayConnectionEvents.DISCONNECT.register((h,cx)->previews.clear());
  ScreenEvents.AFTER_INIT.register((mc,screen,w,h)->{if(!(screen instanceof AbstractContainerScreen<?>))return;Preview state=new Preview();previews.put(screen,state);
   ScreenKeyboardEvents.allowKeyPress(screen).register((s,event)->{if(event.key()==GLFW.GLFW_KEY_V){var slot=((ContainerAccess)s).companion$getHoveredSlot();if(slot!=null&&CardItemRegistry.isCard(slot.getItem())&&!StackData.readHidden(slot.getItem())){state.card=slot.getItem().copy();state.face=TcgCardMeta.read(state.card).face();state.shown=true;return false;}}if(event.key()==GLFW.GLFW_KEY_F&&state.shown){state.face=(state.face+1)%Math.max(1,TcgCardMeta.faceCount(state.card));return false;}return true;});
   ScreenKeyboardEvents.allowKeyRelease(screen).register((s,event)->{if(event.key()==GLFW.GLFW_KEY_V){state.shown=false;return false;}return true;});
   ScreenEvents.afterExtract(screen).register((s,g,mx,my,t)->{if(state.shown){GuiGraphics gg=new GuiGraphics(g);gg.nextStratum();gg.fill(0,0,s.width,s.height,0xE0121824);int height=Math.max(30,s.height-44),cw=Math.round(height*0.716f);art(gg,state.card,state.face,(s.width-cw)/2,12,cw,height);gg.drawCenteredString(mc.font,"Release V to return · F to flip",s.width/2,s.height-20,0xFFFFFFFF);}});
  });
  HudElementRegistry.addLast(Companion.id("counter_hud"),(g,delta)->{var mc=Minecraft.getInstance();if(mc.gui.screen()!=null||mc.gui.hud.isHidden()||!(mc.hitResult instanceof EntityHitResult hit)||!(hit.getEntity() instanceof CardDisplayEntity c))return;ItemStack card=c.getDisplayCardStack(c.getDisplayCardId(c.findSelectedDisplayIndex(mc.player)));if(card.isEmpty()||StackData.readHidden(card))return;var counters=CardCounterNbt.readCounterMap(card);if(counters.isEmpty())return;int x=16,y=44;g.fill(x-6,y-6,x+224,y+22+Math.min(16,counters.size())*15,0xDC101824);g.text(mc.font,TcgCardMeta.displayName(card),x,y,0xFFB3E1FF);y+=20;for(var e:counters.entrySet().stream().limit(16).toList()){g.text(mc.font,e.getKey()+": "+e.getValue(),x,y,0xFFFFFFFF);y+=15;}});
 }
 static void art(GuiGraphics g,ItemStack card,int face,int x,int y,int w,int h){var ref=CardArtManager.getOrRequestFace(card,face);if(ref==null||ref.texW()<=0||ref.texH()<=0){g.fill(x,y,x+w,y+h,0xFF243249);g.drawCenteredString(Minecraft.getInstance().font,"Loading card…",x+w/2,y+h/2,0xFFFFFFFF);return;}float scale=Math.min((float)w/ref.texW(),(float)h/ref.texH());int aw=Math.round(ref.texW()*scale),ah=Math.round(ref.texH()*scale);g.blit(RenderPipelines.GUI_TEXTURED,ref.id(),x+(w-aw)/2,y+(h-ah)/2,0,0,aw,ah,ref.texW(),ref.texH(),ref.texW(),ref.texH());}
}
