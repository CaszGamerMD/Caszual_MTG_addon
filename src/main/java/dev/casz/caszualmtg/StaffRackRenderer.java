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

/** Four full-height hanging 3D staff item models, with their exact saved item data. */
public final class StaffRackRenderer implements BlockEntityRenderer<StaffRackEntity,StaffRackRenderer.State> {
 private final ItemModelResolver resolver;
 // Raise the hanging items exactly one full block relative to the old
 // rack layout. This keeps the displayed models spaced the same distance apart
 // and prevents their amethyst tops from intersecting the metal hooks.
 // The original offset was -0.62; the new one is (-0.62 + 1.00).
 public static final float STAFF_HORIZONTAL_SCALE=.69f,STAFF_VERTICAL_SCALE=.92f;
 public static final double STAFF_VERTICAL_OFFSET=.38;
 public static final double STAFF_DEPTH=9.0/16.0;
 public StaffRackRenderer(BlockEntityRendererProvider.Context context){resolver=context.itemModelResolver();}
 public static final class State extends BlockEntityRenderState {
  final ItemStackRenderState[] staffs=new ItemStackRenderState[StaffRackEntity.SIZE];
  Direction facing=Direction.NORTH;
 }
 @Override public State createRenderState(){return new State();}
 @Override public void extractRenderState(StaffRackEntity rack,State state,float delta,Vec3 camera,
      @Nullable ModelFeatureRenderer.CrumblingOverlay crumbling){
  BlockEntityRenderer.super.extractRenderState(rack,state,delta,camera,crumbling);
  state.facing=rack.getBlockState().getValue(StaffRackBlock.FACING);
  for(int i=0;i<StaffRackEntity.SIZE;i++){
   ItemStack stack=rack.getItem(i);
   state.staffs[i]=null;
   if(stack.isEmpty())continue;
   ItemStackRenderState item=new ItemStackRenderState();
   resolver.updateForTopItem(item,stack,ItemDisplayContext.FIXED,rack.getLevel(),null,
      rack.getBlockPos().hashCode()+i);
   state.staffs[i]=item;
  }
 }
 @Override public void submit(State state,PoseStack poses,SubmitNodeCollector out,CameraRenderState camera){
  poses.pushPose();
  poses.translate(.5,0,.5);
  // Model points local NORTH; rotate it to the face on which the rack was placed.
  poses.mulPose(Axis.YP.rotationDegrees(180f-state.facing.toYRot()));
  poses.translate(-.5,0,-.5);
  for(int i=0;i<StaffRackEntity.SIZE;i++){
   ItemStackRenderState item=state.staffs[i];
   if(item==null)continue;
   poses.pushPose();
   poses.translate((2.0+4.0*i)/16.0,STAFF_VERTICAL_OFFSET,STAFF_DEPTH);
   poses.scale(STAFF_HORIZONTAL_SCALE,STAFF_VERTICAL_SCALE,STAFF_HORIZONTAL_SCALE);
   item.submit(poses,out,state.lightCoords,OverlayTexture.NO_OVERLAY,0);
   poses.popPose();
  }
  poses.popPose();
 }
}
