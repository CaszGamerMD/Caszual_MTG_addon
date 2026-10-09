package dev.casz.caszualmtg.mixin;

import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import dev.casz.caszualmtg.HandLogic;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Routes every MTGCard draw path, including redstone draws, into a linked Hand block. */
@Mixin(DeckControlBlockEntity.class)
public abstract class DeckControlHandMixin {
 @Inject(method="drawTopAndEject",at=@At("HEAD"),cancellable=true,remap=false)
 private void companion$routeDraw(CallbackInfo ci){
  if(HandLogic.routeDraw((DeckControlBlockEntity)(Object)this))ci.cancel();
 }
}
