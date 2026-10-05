package dev.casz.mtg.mixin;
import dev.casz.mtg.*;
import com.spider.mtgcard.deckbox.DeckboxBlockEntity;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.component.DataComponentMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.storage.*;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.*;

/** Preserve MTGCard's own block-entity type, menu and external storage implementation. */
@Mixin(DeckboxBlockEntity.class)
public abstract class DeckboxMaterialMixin implements BoxMaterial {
 @Unique private volatile String companion$skin=BoxMaterial.DEFAULT;
 @Unique public String companion$material(){return companion$skin;}
 @Unique public void companion$material(String value){companion$skin=BoxMaterial.safe(value);var self=(DeckboxBlockEntity)(Object)this;self.setChanged();self.sync();}
 public Object getRenderData(){return companion$skin;}
 @Inject(method="loadAdditional",at=@At("TAIL"),remap=false)
 private void companion$load(ValueInput input,CallbackInfo ci){companion$skin=BoxMaterial.safe(input.getStringOr("CompanionMaterial",BoxMaterial.DEFAULT));}
 @Inject(method="saveAdditional",at=@At("TAIL"),remap=false)
 private void companion$save(ValueOutput output,CallbackInfo ci){var self=(DeckboxBlockEntity)(Object)this;if(self.getBlockState().is(Companion.CUSTOM_BOX))output.putString("CompanionMaterial",companion$skin);}
 @Inject(method="collectImplicitComponents",at=@At("TAIL"),remap=false)
 private void companion$components(DataComponentMap.Builder builder,CallbackInfo ci){var self=(DeckboxBlockEntity)(Object)this;if(self.getBlockState().is(Companion.CUSTOM_BOX))builder.set(Companion.BOX_MATERIAL,companion$skin);}
 @Inject(method="getUpdateTag",at=@At("RETURN"),remap=false)
 private void companion$update(HolderLookup.Provider lookup,CallbackInfoReturnable<CompoundTag> ci){var self=(DeckboxBlockEntity)(Object)this;if(self.getBlockState().is(Companion.CUSTOM_BOX))ci.getReturnValue().putString("CompanionMaterial",companion$skin);}
}
