package dev.casz.mtg.mixin;

import com.spider.mtgcard.display.CardDisplayEntity;
import dev.casz.mtg.Companion;
import dev.casz.mtg.StaffTargets;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(CardDisplayEntity.class)
public abstract class CardDisplayStaffMixin {
 @Inject(method="interact",at=@At("HEAD"),cancellable=true)
 private void companion$staffOrange(Player player,InteractionHand hand,Vec3 location,CallbackInfoReturnable<InteractionResult> cir){
  if(!player.getItemInHand(hand).is(Companion.TARGETING_STAFF))return;
  if(player instanceof ServerPlayer serverPlayer)StaffTargets.mark(serverPlayer,(Entity)(Object)this,StaffTargets.Color.ORANGE);
  cir.setReturnValue(InteractionResult.SUCCESS);
 }

 @Inject(method="hurtServer",at=@At("HEAD"),cancellable=true)
 private void companion$staffWhite(ServerLevel level,DamageSource source,float amount,CallbackInfoReturnable<Boolean> cir){
  Entity attacker=source.getEntity();
  if(!(attacker instanceof ServerPlayer player))return;
  if(!player.getMainHandItem().is(Companion.TARGETING_STAFF))return;
  StaffTargets.mark(player,(Entity)(Object)this,StaffTargets.Color.WHITE);
  cir.setReturnValue(true);
 }
}
