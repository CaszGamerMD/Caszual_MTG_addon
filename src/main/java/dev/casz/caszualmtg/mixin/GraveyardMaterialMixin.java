package dev.casz.caszualmtg.mixin;

import dev.casz.caszualmtg.*;
import com.spider.mtgcard.graveyard.GraveyardBlockEntity;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
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
@Mixin(GraveyardBlockEntity.class)
public abstract class GraveyardMaterialMixin implements BoxMaterial {
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
 @Inject(method="loadAdditional",at=@At("TAIL"),remap=false)
 private void caszual$load(ValueInput input,CallbackInfo ci){
  caszual$skin=BoxMaterial.safe(input.getStringOr("CaszualMaterial",BoxMaterial.DEFAULT));
 }
 @Inject(method="saveAdditional",at=@At("TAIL"),remap=false)
 private void caszual$save(ValueOutput output,CallbackInfo ci){
  BlockEntity self=(BlockEntity)(Object)this;
  if(self.getBlockState().is(CaszualMtg.CUSTOM_GRAVEYARD))
   output.putString("CaszualMaterial",caszual$skin);
 }
}
