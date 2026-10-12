package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.*;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.BaseEntityBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.phys.BlockHitResult;
import org.jetbrains.annotations.Nullable;

public final class BuilderBlock extends BaseEntityBlock {
 public static final MapCodec<BuilderBlock> CODEC=simpleCodec(BuilderBlock::new);
 public BuilderBlock(BlockBehaviour.Properties p){super(p);}
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public RenderShape getRenderShape(BlockState s){return RenderShape.MODEL;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState s){return new BuilderBlockEntity(pos,s);}
 @Override protected InteractionResult useItemOn(ItemStack item,BlockState state,Level level,BlockPos pos,Player player,InteractionHand hand,BlockHitResult hit){return useWithoutItem(state,level,pos,player,hit);}
 @Override protected InteractionResult useWithoutItem(BlockState s,Level l,BlockPos pos,Player p,BlockHitResult hit){if(p instanceof ServerPlayer sp)ServerLogic.open(sp,pos,3);return InteractionResult.SUCCESS;}
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel world,BlockPos pos,boolean moved){
  if(world.getBlockState(pos).getBlock()!=this&&world.getBlockEntity(pos) instanceof BuilderBlockEntity builder)Containers.dropContents(world,pos,builder);
  super.affectNeighborsAfterRemoval(state,world,pos,moved);
 }
}
