package dev.casz.caszualmtg.mixin;

import net.minecraft.world.inventory.Slot;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

/** The vanilla slot fields are final; shift client-only menu geometry at screen init. */
@Mixin(Slot.class)
public interface MenuSlotPositionAccessor {
 @Mutable @Accessor("x") void caszual$setX(int x);
 @Mutable @Accessor("y") void caszual$setY(int y);
}
