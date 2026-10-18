package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.context.UseOnContext;

/** Spawn one experimental Commander opponent directly onto a Caszual chair. */
public final class CommanderGolemItem extends Item {
 public CommanderGolemItem(Properties properties){super(properties);}
 @Override public InteractionResult useOn(UseOnContext context){
  BlockPos chair=context.getClickedPos();
  if(!(context.getLevel().getBlockState(chair).getBlock() instanceof ChairBlock))
   return InteractionResult.PASS;
  if(context.getLevel() instanceof ServerLevel level && context.getPlayer() instanceof ServerPlayer player){
   String message=CommanderGolems.place(level,chair,player);
   player.sendSystemMessage(net.minecraft.network.chat.Component.literal(message));
   if(message.startsWith("Commander Golem seated")&&!player.getAbilities().instabuild)
    context.getItemInHand().shrink(1);
  }
  return InteractionResult.SUCCESS;
 }
}
