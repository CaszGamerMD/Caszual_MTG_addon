package dev.casz.caszualmtg;
import dev.casz.caszualmtg.mixin.ContainerAccess;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.networking.v1.*;
import net.fabricmc.fabric.api.client.screen.v1.*;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.minecraft.client.Minecraft;
import net.minecraft.core.SectionPos;
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
public final class CaszualMtgClient implements ClientModInitializer {
 static final Map<Screen,Preview> previews=new WeakHashMap<>();
 static final class Preview {ItemStack card=ItemStack.EMPTY;int face;boolean shown;}
 public void onInitializeClient(){
  // Client initialization is finished before Jade or other overlays inspect blocks.
  net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents.CLIENT_STARTED
      .register(client -> MtgBlockEntitySafety.verifyAtLifecycle("client startup"));
  CustomBoxModels.register();
  // Per-vertex block tinting in 26.2: exact 24-bit playmat and paper cushion.
  // A pure-white texture is used so RGB is not multiplied by a wool/carpet dye.
  net.fabricmc.fabric.api.client.rendering.v1.BlockColorRegistry.register(
   java.util.List.of(new net.minecraft.client.color.block.BlockTintSource(){
    @Override public int color(net.minecraft.world.level.block.state.BlockState state){
     return 0xFF315348;
    }
    @Override public int colorInWorld(net.minecraft.world.level.block.state.BlockState state,
      net.minecraft.client.renderer.block.BlockAndTintGetter level,net.minecraft.core.BlockPos pos){
     Object data=level.getBlockEntityRenderData(pos);
     return data instanceof TabletopBlockEntity.RenderData rendered
      ?0xFF000000|(rendered.rgb()&0xFFFFFF):0xFF315348;
    }
   }),CaszualMtg.TABLETOP);
  net.fabricmc.fabric.api.client.rendering.v1.BlockColorRegistry.register(
   java.util.List.of(new net.minecraft.client.color.block.BlockTintSource(){
    @Override public int color(net.minecraft.world.level.block.state.BlockState state){
     return 0xFFFFFFFF;
    }
    @Override public int colorInWorld(net.minecraft.world.level.block.state.BlockState state,
      net.minecraft.client.renderer.block.BlockAndTintGetter level,net.minecraft.core.BlockPos pos){
     if(state.getValue(ChairBlock.CUSHION)!=ChairBlock.Cushion.PAPER)return 0xFFFFFFFF;
     Object data=level.getBlockEntityRenderData(pos);
     return data instanceof ChairBlockEntity.RenderData rendered
      ?0xFF000000|(rendered.paperRgb()&0xFFFFFF):0xFFFFFFFF;
    }
   }),CaszualMtg.MATERIAL_CHAIR);
  // The native MTGCard block-entity type includes both vanilla and Caszual deckboxes.
  // Register only a world block renderer; inventory items stay visually unchanged.
  if(com.spider.mtgcard.registry.ModBlockEntities.DECKBOX!=null)
   net.minecraft.client.renderer.blockentity.BlockEntityRenderers.register(
     com.spider.mtgcard.registry.ModBlockEntities.DECKBOX,CommanderTopRenderer::new);
  net.minecraft.client.renderer.blockentity.BlockEntityRenderers.register(CaszualMtg.RACK_BE,DeckboxRackRenderer::new);
  net.minecraft.client.renderer.blockentity.BlockEntityRenderers.register(CaszualMtg.STAFF_RACK_BE,StaffRackRenderer::new);
  net.minecraft.client.gui.screens.MenuScreens.register(CaszualMtg.COMMUNITY_MENU,CommunityScreen::new);
  net.minecraft.client.gui.screens.MenuScreens.register(CaszualMtg.BUILDER_MENU,BuilderScreen::new);
  net.minecraft.client.gui.screens.MenuScreens.register(CaszualMtg.RACK_MENU,DeckboxRackScreen::new);
  net.minecraft.client.gui.screens.MenuScreens.register(CaszualMtg.STAFF_RACK_MENU,StaffRackScreen::new);
  ScreenEvents.AFTER_INIT.register((mc,screen,w,h)->{
   if(screen instanceof HandScreen hand)
    ScreenKeyboardEvents.allowKeyPress(screen).register((shown,event)->!hand.handleHotkey(event.key()));
   else if(screen instanceof TabletopScreen table)
    ScreenKeyboardEvents.allowKeyPress(screen).register((shown,event)->!table.handleHotkey(event.key()));
  });
  ScreenEvents.AFTER_INIT.register((mc,screen,w,h)->{
   if(!(screen instanceof com.spider.mtgcard.client.gui.CardStoreScreen store))return;
   // MTGCard adjusts the virtual menu origin after calculating its panels.
   // Re-anchor the extra deckbox slot to the live purchase button coordinates.
   CardStoreDeckboxLayout.arrange(store);
   ScreenEvents.afterExtract(screen).register((shown,graphics,mx,my,t)->{
    int px=CardStoreDeckboxLayout.screenSlotX(store);
    int py=CardStoreDeckboxLayout.screenSlotY(store);
    GuiGraphics gg=new GuiGraphics(graphics);
    gg.fill(px-2,py-2,px+18,py,0xFFC2A66F);
    gg.fill(px-2,py+16,px+18,py+18,0xFFC2A66F);
    gg.fill(px-2,py,px,py+16,0xFFC2A66F);
    gg.fill(px+16,py,px+18,py+16,0xFFC2A66F);
    gg.drawString(mc.font,"Deckbox output",px+24,py+4,0xFFFFDDA2);
    CardStoreDeckboxLayout.drawProgress(store,gg,mc.font);
   });
  });
  ClientPlayNetworking.registerGlobalReceiver(Wire.Reply.TYPE,(reply,ctx)->{if(reply.kind()==2){if(ctx.client().gui.screen() instanceof CommunityScreen screen&&screen.getMenu().pos.equals(reply.pos()))screen.update(reply);return;}if(reply.kind()==3){if(ctx.client().gui.screen() instanceof BuilderScreen screen&&screen.getMenu().pos.equals(reply.pos()))screen.update(reply);return;}if(ctx.client().gui.screen() instanceof BankScreen screen&&screen.pos.equals(reply.pos())&&screen.kind==reply.kind())screen.update(reply);else if(!(ctx.client().gui.screen() instanceof BankScreen))ctx.client().gui.setScreen(new BankScreen(reply));});
  ClientPlayNetworking.registerGlobalReceiver(TabletopWire.Reply.TYPE,(reply,ctx)->{
   if(ctx.client().gui.screen() instanceof TabletopScreen screen&&screen.data.pos().equals(reply.pos()))
    screen.update(reply);
   else if(reply.message().equals("Table ready."))ctx.client().gui.setScreen(new TabletopScreen(reply));
  });
  ClientPlayNetworking.registerGlobalReceiver(HandWire.Reply.TYPE,(reply,ctx)->{if(ctx.client().gui.screen() instanceof HandScreen screen&&screen.data.pos().equals(reply.pos()))screen.update(reply);else if(reply.message().equals("Hand ready."))ctx.client().gui.setScreen(new HandScreen(reply));});
  ClientPlayNetworking.registerGlobalReceiver(CardStoreStatusWire.Progress.TYPE,(progress,ctx)->{
   if(ctx.client().gui.screen() instanceof com.spider.mtgcard.client.gui.CardStoreScreen store)
    CardStoreDeckboxLayout.updateProgress(store,progress);
  });
  ClientPlayNetworking.registerGlobalReceiver(DeckboxRefreshWire.Refresh.TYPE,(refresh,ctx)->{
   var pos=refresh.pos();
   if(ctx.client().level!=null)ctx.client().level.setSectionDirtyWithNeighbors(SectionPos.blockToSectionCoord(pos.getX()),SectionPos.blockToSectionCoord(pos.getY()),SectionPos.blockToSectionCoord(pos.getZ()));
  });
  ClientPlayConnectionEvents.DISCONNECT.register((h,cx)->previews.clear());
  ScreenEvents.AFTER_INIT.register((mc,screen,w,h)->{if(!(screen instanceof AbstractContainerScreen<?>))return;Preview state=new Preview();previews.put(screen,state);
   ScreenKeyboardEvents.allowKeyPress(screen).register((s,event)->{if(event.key()==GLFW.GLFW_KEY_V){var slot=((ContainerAccess)s).companion$getHoveredSlot();if(slot!=null&&CardItemRegistry.isCard(slot.getItem())&&!StackData.readHidden(slot.getItem())){state.card=slot.getItem().copy();state.face=TcgCardMeta.read(state.card).face();state.shown=true;return false;}}if(event.key()==GLFW.GLFW_KEY_F&&state.shown){state.face=(state.face+1)%Math.max(1,TcgCardMeta.faceCount(state.card));return false;}return true;});
   ScreenKeyboardEvents.allowKeyRelease(screen).register((s,event)->{if(event.key()==GLFW.GLFW_KEY_V){state.shown=false;return false;}return true;});
   ScreenEvents.afterExtract(screen).register((s,g,mx,my,t)->{if(state.shown){GuiGraphics gg=new GuiGraphics(g);gg.nextStratum();gg.fill(0,0,s.width,s.height,0xE0121824);int height=Math.max(30,s.height-44),cw=Math.round(height*0.716f);art(gg,state.card,state.face,(s.width-cw)/2,12,cw,height);gg.drawCenteredString(mc.font,"Release V to return · F to flip",s.width/2,s.height-20,0xFFFFFFFF);}});
  });
  HudElementRegistry.addLast(CaszualMtg.id("counter_hud"),(g,delta)->{var mc=Minecraft.getInstance();if(mc.gui.screen()!=null||mc.gui.hud.isHidden()||!(mc.hitResult instanceof EntityHitResult hit)||!(hit.getEntity() instanceof CardDisplayEntity c))return;ItemStack card=c.getDisplayCardStack(c.getDisplayCardId(c.findSelectedDisplayIndex(mc.player)));if(card.isEmpty()||StackData.readHidden(card))return;var counters=CardCounterNbt.readCounterMap(card);if(counters.isEmpty())return;int x=16,y=44;g.fill(x-6,y-6,x+224,y+22+Math.min(16,counters.size())*15,0xDC101824);g.text(mc.font,TcgCardMeta.displayName(card),x,y,0xFFB3E1FF);y+=20;for(var e:counters.entrySet().stream().limit(16).toList()){g.text(mc.font,e.getKey()+": "+e.getValue(),x,y,0xFFFFFFFF);y+=15;}});
 }
 static void art(GuiGraphics g,ItemStack card,int face,int x,int y,int w,int h){var ref=CardArtManager.getOrRequestFace(card,face);if(ref==null||ref.texW()<=0||ref.texH()<=0){g.fill(x,y,x+w,y+h,0xFF243249);g.drawCenteredString(Minecraft.getInstance().font,"Loading card…",x+w/2,y+h/2,0xFFFFFFFF);return;}float scale=Math.min((float)w/ref.texW(),(float)h/ref.texH());int aw=Math.round(ref.texW()*scale),ah=Math.round(ref.texH()*scale);g.blit(RenderPipelines.GUI_TEXTURED,ref.id(),x+(w-aw)/2,y+(h-ah)/2,0,0,aw,ah,ref.texW(),ref.texH(),ref.texW(),ref.texH());}
}
