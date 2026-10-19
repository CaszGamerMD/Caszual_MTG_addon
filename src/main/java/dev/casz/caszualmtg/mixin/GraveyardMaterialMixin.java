package dev.casz.caszualmtg.mixin;

import dev.casz.caszualmtg.*;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.ValueInput;
import net.minecraft.world.level.storage.ValueOutput;
import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * MTGCard's GRAVEYARD block entity type always reloads its native class, not a
 * custom subclass. Attach the custom data/visuals to that native class instead.
 */
@Mixin(GraveyardBlockEntity.class)
public abstract class GraveyardMaterialMixin implements BoxMaterial,GraveyardLid {
 @Unique private String caszual$skin=BoxMaterial.DEFAULT;
 @Unique private boolean caszual$lidPinned;

 @Override public String companion$material(){return caszual$skin;}
 @Override public void companion$material(String value){
  String next=BoxMaterial.safe(value);
  if(next.equals(caszual$skin))return;
  caszual$skin=next;
  BlockEntity self=(BlockEntity)(Object)this;
  self.setChanged();
  if(self.getLevel()!=null){
   BlockState state=self.getBlockState();
   self.getLevel().sendBlockUpdated(self.getBlockPos(),state,state,Block.UPDATE_ALL);
  }
 }
 public Object getRenderData(){return caszual$skin;}
 @Inject(method="getDisplayName",at=@At("HEAD"),cancellable=true)
 private void caszual$title(CallbackInfoReturnable<Component> cir){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD))
   cir.setReturnValue(Component.translatable("block.caszual_mtg.custom_graveyard"));
 }

 @Override public boolean caszual$isLidPinned(){return caszual$lidPinned;}
 @Override public void caszual$setLidPinned(boolean open){
  BlockEntity self=(BlockEntity)(Object)this;
  if(!self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD))return;
  caszual$lidPinned=open;
  self.setChanged();
  if(self.getLevel()!=null&&!self.getLevel().isClientSide()){
   BlockState state=self.getBlockState();
   if(state.getValue(CustomGraveyard.OPEN)!=open)
    self.getLevel().setBlock(self.getBlockPos(),state.setValue(CustomGraveyard.OPEN,open),Block.UPDATE_ALL);
  }
 }

 @Inject(method="loadAdditional",at=@At("TAIL"))
 private void caszual$load(ValueInput input,CallbackInfo ci){
  caszual$skin=BoxMaterial.safe(input.getStringOr("CaszualMaterial",BoxMaterial.DEFAULT));
  caszual$lidPinned=input.getBooleanOr("CaszualLidPinned",false);
 }
 @Inject(method="saveAdditional",at=@At("TAIL"))
 private void caszual$save(ValueOutput output,CallbackInfo ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD)){
   output.putString("CaszualMaterial",caszual$skin);
   output.putBoolean("CaszualLidPinned",caszual$lidPinned);
  }
 }

 /** The native Graveyard BE inherits getUpdateTag/getUpdatePacket from
  * BlockEntity: add explicit payload support for model render data. */
 public CompoundTag getUpdateTag(HolderLookup.Provider lookup){
  return ((BlockEntity)(Object)this).saveWithoutMetadata(lookup);
 }
 public @Nullable Packet<ClientGamePacketListener> getUpdatePacket(){
  return ClientboundBlockEntityDataPacket.create((BlockEntity)(Object)this);
 }

 @Inject(method="onViewerOpen",at=@At("TAIL"))
 private void caszual$onOpen(CallbackInfo ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD))
   caszual$setLidPinned(true);
 }
 @Inject(method="onViewerClose",at=@At("TAIL"))
 private void caszual$onClose(CallbackInfo ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD)&&caszual$lidPinned)
   caszual$setLidPinned(true);
 }
}
