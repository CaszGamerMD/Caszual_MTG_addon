package dev.casz.mtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.*;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import org.jetbrains.annotations.Nullable;

public final class HandBlock extends BaseEntityBlock {
 public static final MapCodec<HandBlock> CODEC=MapCodec.unit(()->new HandBlock(BlockBehaviour.Properties.of()));
 public HandBlock(Properties p){super(p);}
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public net.minecraft.world.level.block.RenderShape getRenderShape(BlockState state){return net.minecraft.world.level.block.RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState state){return new HandBlockEntity(pos,state);}
 @Override protected InteractionResult useWithoutItem(BlockState state,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)HandLogic.open(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,@Nullable LivingEntity placer,ItemStack stack){
  super.setPlacedBy(level,pos,state,placer,stack);
  if(placer instanceof Player p&&level.getBlockEntity(pos) instanceof HandBlockEntity hand)hand.ensureOwner(p);
 }
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel level,BlockPos pos,boolean moved){
  if(level.getBlockState(pos).getBlock()!=this&&level.getBlockEntity(pos) instanceof HandBlockEntity hand)Containers.dropContents(level,pos,hand);
  super.affectNeighborsAfterRemoval(state,level,pos,moved);
 }
}
