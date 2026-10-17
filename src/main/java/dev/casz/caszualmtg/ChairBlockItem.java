package dev.casz.caszualmtg;

import net.minecraft.network.chat.Component;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.item.component.TooltipDisplay;
import java.util.function.Consumer;

/** Craft result retains the exact source material even when picked up or moved. */
public final class ChairBlockItem extends BlockItem {
 public ChairBlockItem(ChairBlock chair,Item.Properties props){super(chair,props);}
 @Override public void appendHoverText(ItemStack stack,Item.TooltipContext context,
   TooltipDisplay display,Consumer<Component> lines,TooltipFlag flag){
  super.appendHoverText(stack,context,display,lines,flag);
  String source=stack.getOrDefault(CaszualMtg.CHAIR_MATERIAL,ChairWood.DEFAULT);
  lines.accept(Component.literal("Wood: ").append(ChairWood.block(source).getName()));
  lines.accept(Component.literal("Place six matching wood blocks in the chair pattern."));
  lines.accept(Component.literal("Right-click with another wood block to reskin."));
 }
}
