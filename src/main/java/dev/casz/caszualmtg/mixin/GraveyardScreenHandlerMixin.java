package dev.casz.caszualmtg.mixin;

import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import com.spider.mtgcard.graveyard.GraveyardScreenHandler;
import dev.casz.caszualmtg.CaszualMtg;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** MTGCard's vanilla-only block check forcibly closed Custom Graveyard GUIs. */
@Mixin(GraveyardScreenHandler.class)
public abstract class GraveyardScreenHandlerMixin {
 @Inject(method="stillValid",at=@At("HEAD"),cancellable=true)
 private void caszual$keepCustomGraveyardOpen(Player player,CallbackInfoReturnable<Boolean> cir){
  BlockPos pos=((GraveyardScreenHandler)(Object)this).pos;
  if(!player.level().getBlockState(pos).is(CaszualMtg.CUSTOM_GRAVEYARD))return;
  cir.setReturnValue(player.distanceToSqr(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5)<=64
    &&player.level().getBlockEntity(pos) instanceof GraveyardBlockEntity);
 }
}
