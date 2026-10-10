package dev.casz.caszualmtg.mixin;

import dev.casz.caszualmtg.StaffColors;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Minecraft glow outlines already use an int RGB color. The default team
 * color enum is restricted; decode only our private scoreboard team names
 * to enable precise 24-bit glow color for every staff-marked entity.
 */
@Mixin(Entity.class)
public abstract class StaffRgbOutlineMixin {
 @Inject(method="getTeamColor",at=@At("RETURN"),cancellable=true)
 private void caszual$rgbStaffOutline(CallbackInfoReturnable<Integer> cir){
  int rgb=StaffColors.fromTeam(((Entity)(Object)this).getTeam());
  if(rgb>=0)cir.setReturnValue(rgb);
 }
}
