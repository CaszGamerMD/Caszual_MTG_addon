package dev.casz.caszualmtg;

import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;

/** Material selection for Caszual Deck Control and Graveyard.
 * The parent MTGCard inventories, menus, and card/link records stay native.
 * Like CustomDeckbox: sneak-use any block to change the decorative panels.
 */
public final class CustomGameDeviceMaterial {
 private CustomGameDeviceMaterial(){}
 public static InteractionResult apply(ItemStack held,Level level,BlockPos pos,Player player){
  if(!player.isShiftKeyDown()||!(held.getItem() instanceof BlockItem block))
   return InteractionResult.PASS;
  if(!player.mayBuild())return InteractionResult.FAIL;
  BlockEntity be=level.getBlockEntity(pos);
  if(!(be instanceof BoxMaterial material))return InteractionResult.PASS;
  if(!level.isClientSide()){
   String next=BoxMaterial.safe(BuiltInRegistries.BLOCK.getKey(block.getBlock()).toString());
   if(!next.equals(material.companion$material())){
    material.companion$material(next);
    if(!player.getAbilities().instabuild)held.shrink(1);
   }
  }
  return InteractionResult.SUCCESS;
 }
 public static void loadFromItem(Level level,BlockPos pos,ItemStack stack){
  if(level.getBlockEntity(pos) instanceof BoxMaterial material)
   material.companion$material(stack.getOrDefault(CaszualMtg.BOX_MATERIAL,BoxMaterial.DEFAULT));
 }
 public static ItemStack cloneWithMaterial(ItemStack stack,Level level,BlockPos pos){
  if(level.getBlockEntity(pos) instanceof BoxMaterial material)
   stack.set(CaszualMtg.BOX_MATERIAL,material.companion$material());
  return stack;
 }
}
