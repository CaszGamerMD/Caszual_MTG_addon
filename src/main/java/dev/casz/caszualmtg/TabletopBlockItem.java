package dev.casz.caszualmtg;

import net.minecraft.network.chat.Component;
import net.minecraft.world.item.*;
import net.minecraft.world.item.component.TooltipDisplay;
import java.util.function.Consumer;

/** The original tabletop ID stays the same; the item now carries its chosen frame wood. */
public final class TabletopBlockItem extends BlockItem {
 public TabletopBlockItem(TabletopBlock block,Item.Properties p){super(block,p);}
 @Override public void appendHoverText(ItemStack stack,Item.TooltipContext context,
   TooltipDisplay display,Consumer<Component> lines,TooltipFlag flag){
  super.appendHoverText(stack,context,display,lines,flag);
  String source=stack.getOrDefault(CaszualMtg.TABLE_MATERIAL,"minecraft:dark_oak_planks");
  lines.accept(Component.literal("Frame wood: ").append(ChairWood.block(source).getName()));
  lines.accept(Component.literal("Sneak-right-click placed table with another wood to reskin."));
 }
}
