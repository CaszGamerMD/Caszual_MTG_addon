package dev.casz.mtg.mixin;
import net.minecraft.client.renderer.item.ItemStackRenderState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;
@Mixin(ItemStackRenderState.class)
public interface ItemLayersAccess {
 @Accessor("activeLayerCount") int companion$layerCount();
 @Accessor("layers") ItemStackRenderState.LayerRenderState[] companion$layers();
}
