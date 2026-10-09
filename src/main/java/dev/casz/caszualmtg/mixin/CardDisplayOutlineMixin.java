package dev.casz.caszualmtg.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.spider.mtgcard.api.CardSleeves;
import com.spider.mtgcard.client.display.CardDisplayEntityRenderer;
import com.spider.mtgcard.display.CardDisplayEntity;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.client.renderer.state.level.CameraRenderState;
import net.minecraft.core.Direction;
import net.minecraft.resources.Identifier;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(CardDisplayEntityRenderer.class)
public abstract class CardDisplayOutlineMixin {
 private static final Identifier COMPANION$DEFAULT_BACK=Identifier.fromNamespaceAndPath("mtgcard","textures/item/card.png");
 private static final float COMPANION$BACK_U0=147f/1040f;
 private static final float COMPANION$BACK_U1=892f/1040f;
 private static final float COMPANION$SLEEVE_U0=130f/1040f;
 private static final float COMPANION$SLEEVE_U1=911f/1040f;

 @Inject(method="submit",at=@At("TAIL"))
 private void companion$submitStaffOutline(CardDisplayEntityRenderer.State state,PoseStack matrices,SubmitNodeCollector queue,CameraRenderState cameraState,CallbackInfo ci){
  if(state.outlineColor==0||state.cards==null||state.cards.isEmpty())return;
  int attachments=Math.max(0,state.cards.size()-1);
  for(int i=state.cards.size()-1;i>=0;i--)companion$outlineCard(state,state.cards.get(i),i,attachments,matrices,queue);
 }

 private static void companion$outlineCard(CardDisplayEntityRenderer.State state,CardDisplayEntityRenderer.CardState card,int displayIndex,int attachmentCount,PoseStack matrices,SubmitNodeCollector queue){
  matrices.pushPose();
  companion$orient(matrices,state.facing);
  if(state.facing==Direction.UP||state.facing==Direction.DOWN){
   matrices.mulPose(new Matrix4f().rotation(Axis.ZP.rotationDegrees(-state.flatYawStep*90f)));
  }

  float baseNormalOffset=(state.facing==Direction.UP||state.facing==Direction.DOWN)?0.002f:0.01f;
  float layerOffset=0.0015f*(state.cards.size()-displayIndex);
  float yOffset=(float)CardDisplayEntity.stackLocalYOffset(displayIndex,attachmentCount);
  matrices.translate(0f,yOffset,baseNormalOffset+layerOffset);

  float degrees=card.rotStep()==1?90f:0f;
  matrices.mulPose(new Matrix4f().rotation(Axis.ZP.rotationDegrees(-degrees)));

  float ar=(float)card.texW()/(float)card.texH();
  float halfW,halfH;
  if(ar>=1f){halfW=0.5f;halfH=0.5f/ar;}
  else{halfW=0.5f*ar;halfH=0.5f;}

  boolean cardBack=COMPANION$DEFAULT_BACK.equals(card.texId());
  boolean sleeve=CardSleeves.get(card.stack()).map(value->value.backTexture().equals(card.texId())).orElse(false);
  float u0=sleeve?COMPANION$SLEEVE_U0:cardBack?COMPANION$BACK_U0:0f;
  float u1=sleeve?COMPANION$SLEEVE_U1:cardBack?COMPANION$BACK_U1:1f;

  queue.submitCustomGeometry(matrices,RenderTypes.outline(card.texId()),(entry,vc)->{
   Matrix4f mat=entry.pose();
   int color=state.outlineColor;
   vc.addVertex(mat,-halfW,-halfH,0f).setColor(color).setUv(u0,1f).setNormal(0f,0f,1f);
   vc.addVertex(mat,-halfW, halfH,0f).setColor(color).setUv(u0,0f).setNormal(0f,0f,1f);
   vc.addVertex(mat, halfW, halfH,0f).setColor(color).setUv(u1,0f).setNormal(0f,0f,1f);
   vc.addVertex(mat, halfW,-halfH,0f).setColor(color).setUv(u1,1f).setNormal(0f,0f,1f);
  });
  matrices.popPose();
 }

 private static void companion$orient(PoseStack matrices,Direction facing){
  switch(facing){
   case SOUTH -> {}
   case NORTH -> matrices.mulPose(new Matrix4f().rotation(Axis.YP.rotationDegrees(180f)));
   case EAST -> matrices.mulPose(new Matrix4f().rotation(Axis.YP.rotationDegrees(90f)));
   case WEST -> matrices.mulPose(new Matrix4f().rotation(Axis.YP.rotationDegrees(-90f)));
   case UP -> matrices.mulPose(new Matrix4f().rotation(Axis.XP.rotationDegrees(-90f)));
   case DOWN -> matrices.mulPose(new Matrix4f().rotation(Axis.XP.rotationDegrees(90f)));
  }
 }
}
