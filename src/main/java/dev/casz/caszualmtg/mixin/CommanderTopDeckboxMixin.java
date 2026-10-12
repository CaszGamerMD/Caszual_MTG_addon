package dev.casz.caszualmtg.mixin;

import com.spider.mtgcard.api.CardItemRegistry;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import dev.casz.caszualmtg.CommanderTopAccess;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.resources.RegistryOps;
import net.minecraft.nbt.NbtOps;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import java.util.UUID;

/** Sends only the one public-facing card, not the deckbox's inventory. */
@Mixin(DeckboxBlockEntity.class)
public abstract class CommanderTopDeckboxMixin implements CommanderTopAccess {
 private static final String CASZUAL_COMMANDER="CaszualTopCommander";
 @Unique private ItemStack caszual$visibleCommander=ItemStack.EMPTY;

 /**
  * MTGCard puts its commander into SECOND_SIDE_SLOT (100). Older Caszual
  * Deck Builder versions populated FIRST_SIDE_SLOT (99), so support that too.
  */
 @Unique private static ItemStack caszual$select(DeckboxBlockEntity box){
  ItemStack commander=box.getItem(DeckboxBlockEntity.SECOND_SIDE_SLOT);
  if(commander.isEmpty())commander=box.getItem(DeckboxBlockEntity.FIRST_SIDE_SLOT);
  return !commander.isEmpty()&&CardItemRegistry.isCard(commander)?commander:ItemStack.EMPTY;
 }
 @Override public ItemStack caszual$commanderForDisplay(){
  var box=(DeckboxBlockEntity)(Object)this;
  if(box.getLevel()!=null&&box.getLevel().isClientSide())return caszual$visibleCommander;
  return caszual$select(box);
 }
 @Inject(method="getUpdateTag",remap=false,at=@At("RETURN"))
 private void caszual$includeCommander(HolderLookup.Provider lookup,CallbackInfoReturnable<CompoundTag> cir){
  var box=(DeckboxBlockEntity)(Object)this;
  ItemStack card=caszual$select(box);
  if(card.isEmpty())return;
  // Copy just the selected card. No main-deck or other side-slot contents are sent.
  ItemStack.CODEC.encodeStart(RegistryOps.create(NbtOps.INSTANCE,lookup),card.copyWithCount(1))
   .result().ifPresent(encoded->cir.getReturnValue().put(CASZUAL_COMMANDER,encoded));
 }
 @Inject(method="loadAdditional",remap=false,at=@At("TAIL"))
 private void caszual$readCommander(ValueInput input,CallbackInfo ci){
  // Initial chunk/BE update packets call loadAdditional on the client.
  var box=(DeckboxBlockEntity)(Object)this;
  if(box.getLevel()!=null&&box.getLevel().isClientSide())
   caszual$visibleCommander=input.read(CASZUAL_COMMANDER,ItemStack.CODEC).orElse(ItemStack.EMPTY);
 }
 @Inject(method="setItem",remap=false,at=@At("TAIL"))
 private void caszual$commanderChanged(int slot,ItemStack stack,CallbackInfo ci){
  if(slot!=DeckboxBlockEntity.SECOND_SIDE_SLOT&&slot!=DeckboxBlockEntity.FIRST_SIDE_SLOT)return;
  var box=(DeckboxBlockEntity)(Object)this;
  if(box.getLevel()!=null&&!box.getLevel().isClientSide())box.sync();
 }
 @Inject(method="loadStorageId",remap=false,at=@At("TAIL"))
 private void caszual$placedStorageLoaded(UUID id,CallbackInfo ci){
  // Placement of a UUID-backed deckbox can replace its cards from external storage.
  var box=(DeckboxBlockEntity)(Object)this;
  if(box.getLevel()!=null&&!box.getLevel().isClientSide())box.sync();
 }
}
