package dev.casz.caszualmtg;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.blockentity.BlockEntityRenderer;
import net.minecraft.client.renderer.blockentity.BlockEntityRendererProvider;
import net.minecraft.client.renderer.blockentity.state.BlockEntityRenderState;
import net.minecraft.client.renderer.feature.ModelFeatureRenderer;
import net.minecraft.client.renderer.item.ItemModelResolver;
import net.minecraft.client.renderer.item.ItemStackRenderState;
import net.minecraft.client.renderer.state.level.CameraRenderState;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.Direction;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;
import org.jetbrains.annotations.Nullable;

/** Displays actual (not generic) miniature item/block models of all five stored deckboxes. */
public final class DeckboxRackRenderer implements BlockEntityRenderer<DeckboxRackEntity,DeckboxRackRenderer.State> {
 private final ItemModelResolver resolver;
 public DeckboxRackRenderer(BlockEntityRendererProvider.Context context){resolver=context.itemModelResolver();}
 public static final class State extends BlockEntityRenderState {
  final ItemStackRenderState[] boxes=new ItemStackRenderState[DeckboxRackEntity.SIZE];
  Direction facing=Direction.NORTH;
  boolean wall;
 }
 @Override public State createRenderState(){return new State();}
 @Override public void extractRenderState(DeckboxRackEntity be,State state,float delta,Vec3 camera,
    @Nullable ModelFeatureRenderer.CrumblingOverlay crumbling){
  BlockEntityRenderer.super.extractRenderState(be,state,delta,camera,crumbling);
  state.facing=be.getBlockState().getValue(DeckboxRackBlock.FACING);
  state.wall=be.getBlockState().getValue(DeckboxRackBlock.WALL);
  for(int i=0;i<state.boxes.length;i++){
   state.boxes[i]=null;
   ItemStack stack=be.getItem(i);
   if(stack.isEmpty())continue;
   ItemStackRenderState item=new ItemStackRenderState();
   resolver.updateForTopItem(item,stack,ItemDisplayContext.FIXED,be.getLevel(),null,i+be.getBlockPos().hashCode());
   state.boxes[i]=item;
  }
 }
 @Override public void submit(State state,PoseStack poses,SubmitNodeCollector out,CameraRenderState camera){
  poses.pushPose();
  poses.translate(.5,0,.5);
  poses.mulPose(Axis.YP.rotationDegrees(-state.facing.toYRot()));
  poses.translate(-.5,0,-.5);
  for(int i=0;i<state.boxes.length;i++){
   ItemStackRenderState item=state.boxes[i];if(item==null)continue;
   poses.pushPose();
   // Lower the baked FIXED deckbox models a further 0.75 model pixels: their
   // visual bases were still hovering above the ledge in game. Keep each
   // center aligned with the six-pixel shelf, for both wall and floor mounts.
   poses.translate((1.55+i*3.05)/16.0,(state.wall?7.0:0.0)/16.0+2.90/16.0,4.0/16.0);
   poses.scale(.195f,.195f,.195f);
   item.submit(poses,out,state.lightCoords,OverlayTexture.NO_OVERLAY,0);
   poses.popPose();
  }
  poses.popPose();
 }
}
