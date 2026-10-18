package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import com.spider.mtgcard.graveyard.GraveyardBlock;
import net.minecraft.core.BlockPos;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;

/** Native 100-slot graveyard + 100-slot exile, with reskinnable Caszual trim. */
public final class CustomGraveyard extends GraveyardBlock {
 public static final MapCodec<CustomGraveyard> CODEC=simpleCodec(CustomGraveyard::new);
 public CustomGraveyard(Properties properties){super(properties);}
 @Override protected MapCodec<CustomGraveyard> codec(){return CODEC;}
 @Override protected InteractionResult useItemOn(ItemStack stack,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){
  InteractionResult selected=CustomGameDeviceMaterial.apply(stack,level,pos,player);
  return selected!=InteractionResult.PASS?selected:super.useItemOn(stack,state,level,pos,player,hand,hit);
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  CustomGameDeviceMaterial.loadFromItem(level,pos,stack);
 }
 @Override protected ItemStack getCloneItemStack(LevelReader reader,BlockPos pos,BlockState state,boolean includeData){
  ItemStack copy=super.getCloneItemStack(reader,pos,state,includeData);
  if(reader instanceof Level level)return CustomGameDeviceMaterial.cloneWithMaterial(copy,level,pos);
  return copy;
 }
}
