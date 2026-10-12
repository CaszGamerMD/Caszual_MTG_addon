package dev.casz.caszualmtg;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.spider.mtgcard.client.java.CardArtManager;
import com.spider.mtgcard.deckbox.DeckboxBlock;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider;
import net.minecraft.client.renderer.blockentity.state.BlockEntityRenderState;
import net.minecraft.client.renderer.feature.ModelFeatureRenderer;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.state.level.CameraRenderState;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.Direction;
import net.minecraft.resources.Identifier;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;
import org.jetbrains.annotations.Nullable;
import org.joml.Matrix4f;

/** Renders MTGCard's actual commander artwork atop a placed, closed deckbox. */
public final class CommanderTopRenderer
    implements BlockEntityRenderer<DeckboxBlockEntity,CommanderTopRenderer.State> {
 private static final Identifier BACKGROUND=Identifier.fromNamespaceAndPath("mtgcard","textures/misc/white.png");
 private static final float Y_BORDER=15.18f/16f,Y_ART=15.195f/16f;
 private static final int BORDER=0xFF19131B;
 public CommanderTopRenderer(BlockEntityRendererProvider.Context context){}

 public static final class State extends BlockEntityRenderState {
  Identifier art;
  Direction facing=Direction.NORTH;
  Direction spin=Direction.NORTH;
  boolean visible;
 }
 @Override public State createRenderState(){return new State();}
 @Override public void extractRenderState(DeckboxBlockEntity box,State state,float partialTick,Vec3 camera,
     @Nullable ModelFeatureRenderer.CrumblingOverlay crumbling){
  BlockEntityRenderer.super.extractRenderState(box,state,partialTick,camera,crumbling);
  state.art=null;
  state.visible=false;
  var block=box.getBlockState();
  if(!block.hasProperty(DeckboxBlock.OPEN)||block.getValue(DeckboxBlock.OPEN))return;
  ItemStack commander=((CommanderTopAccess)box).caszual$commanderForDisplay();
  if(commander.isEmpty())return;
  state.facing=block.getValue(DeckboxBlock.FACING);
  state.spin=block.getValue(DeckboxBlock.SPIN);
  // The existing MTGCard art cache handles on-demand downloads and disk caching.
  var texture=CardArtManager.getOrRequestFace(commander,0);
  if(texture==null)return;
  state.art=texture.id();
  state.visible=true;
 }
 @Override public void submit(State state,PoseStack poses,SubmitNodeCollector collector,CameraRenderState camera){
  if(!state.visible||state.art==null)return;
  poses.pushPose();
  poses.translate(.5,0,.5);
  // For upright boxes, turn the art toward the front of the deckbox.
  Direction rotation=state.facing.getAxis().isHorizontal()?state.facing:state.spin;
  poses.mulPose(com.mojang.math.Axis.YP.rotationDegrees(-rotation.toYRot()));
  poses.translate(-.5,0,-.5);

  // A black frame stays just above the top panel; the card never z-fights it.
  collector.submitCustomGeometry(poses,RenderTypes.entityCutout(BACKGROUND),(p,v)->{
   quad(p.pose(),v,.243f,.757f,.145f,.855f,Y_BORDER,0.0f,0.0f,1.0f,1.0f,
     state.lightCoords,BORDER);
  });
  collector.submitCustomGeometry(poses,RenderTypes.entityCutout(state.art),(p,v)->{
   quad(p.pose(),v,.257f,.743f,.158f,.842f,Y_ART,0.0f,0.0f,1.0f,1.0f,
     state.lightCoords,0xFFFFFFFF);
  });
  poses.popPose();
 }
 private static void quad(Matrix4f transform,VertexConsumer out,
     float x0,float x1,float z0,float z1,float y,
     float u0,float v0,float u1,float v1,int light,int argb){
  // CCW winding, face normal +Y. Artwork top points away from the observer.
  point(out,transform,x0,y,z1,u0,v1,light,argb);
  point(out,transform,x1,y,z1,u1,v1,light,argb);
  point(out,transform,x1,y,z0,u1,v0,light,argb);
  point(out,transform,x0,y,z0,u0,v0,light,argb);
 }
 private static void point(VertexConsumer out,Matrix4f transform,
     float x,float y,float z,float u,float v,int light,int argb){
  out.addVertex(transform,x,y,z).setColor((argb>>>16)&255,(argb>>>8)&255,argb&255,(argb>>>24)&255)
    .setUv(u,v).setOverlay(OverlayTexture.NO_OVERLAY).setLight(light).setNormal(0,1,0);
 }
}
