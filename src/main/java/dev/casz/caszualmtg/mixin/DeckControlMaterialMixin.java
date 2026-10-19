package dev.casz.caszualmtg.mixin;

import dev.casz.caszualmtg.*;
import com.spider.mtgcard.deckcontrol.DeckControlBlockEntity;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import org.jetbrains.annotations.Nullable;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Retain native MTGCard storage and menu while allowing customized panels. */
@Mixin(DeckControlBlockEntity.class)
public abstract class DeckControlMaterialMixin implements BoxMaterial {
 @Unique private String caszual$skin=BoxMaterial.DEFAULT;
 @Unique public String companion$material(){return caszual$skin;}
 @Unique public void companion$material(String value){
  String next=BoxMaterial.safe(value);
  if(next.equals(caszual$skin))return;
  caszual$skin=next;
  BlockEntity self=(BlockEntity)(Object)this;
  self.setChanged();
  if(self.getLevel()!=null){
   var state=self.getBlockState();var pos=self.getBlockPos();
   self.getLevel().sendBlockUpdated(pos,state,state,3);
  }
 }
 public Object getRenderData(){return caszual$skin;}
 @Inject(method="getDisplayName",at=@At("HEAD"),cancellable=true)
 private void caszual$title(CallbackInfoReturnable<Component> cir){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_DECK_CONTROL))
   cir.setReturnValue(Component.translatable("block.caszual_mtg.custom_deck_control"));
 }
 /** The parent MTGCard entity supplies the type/factory on *both* placement
  * and world reload; a packet is needed for reskinning remote clients. */
 public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create((BlockEntity)(Object)this);
 }

 @Inject(method="loadAdditional",at=@At("TAIL"),remap=false)
 private void caszual$load(ValueInput input,CallbackInfo ci){
  caszual$skin=BoxMaterial.safe(input.getStringOr("CaszualMaterial",BoxMaterial.DEFAULT));
 }
 @Inject(method="saveAdditional",at=@At("TAIL"),remap=false)
 private void caszual$save(ValueOutput output,CallbackInfo ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_DECK_CONTROL))
   output.putString("CaszualMaterial",caszual$skin);
 }
 @Inject(method="getUpdateTag",at=@At("RETURN"),remap=false)
 private void caszual$tag(HolderLookup.Provider lookup,CallbackInfoReturnable<CompoundTag> ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_DECK_CONTROL))
   ci.getReturnValue().putString("CaszualMaterial",caszual$skin);
 }
}
