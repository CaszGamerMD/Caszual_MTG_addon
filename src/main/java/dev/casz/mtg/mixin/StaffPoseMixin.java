package dev.casz.mtg.mixin;

import dev.casz.mtg.Companion;
import net.minecraft.client.model.HumanoidModel;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.renderer.entity.state.HumanoidRenderState;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(HumanoidModel.class)
public abstract class StaffPoseMixin {
 @Shadow @Final public ModelPart rightArm;
 @Shadow @Final public ModelPart leftArm;

 @Inject(method="setupAnim",at=@At("TAIL"))
 private void companion$staffPose(HumanoidRenderState state,CallbackInfo ci){
  if(state.rightHandItemStack.is(Companion.TARGETING_STAFF)){
   rightArm.xRot=-1.20F;
   rightArm.yRot=-0.12F;
   rightArm.zRot=0.05F;
  }
  if(state.leftHandItemStack.is(Companion.TARGETING_STAFF)){
   leftArm.xRot=-1.20F;
   leftArm.yRot=0.12F;
   leftArm.zRot=-0.05F;
  }
 }
}
