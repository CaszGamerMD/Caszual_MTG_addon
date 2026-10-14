package dev.casz.caszualmtg;

import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.jetbrains.annotations.Nullable;

/** Adjacent tiles at equal height form one shared multiplayer tabletop. */
public final class TabletopBlock extends BaseEntityBlock {
 public static final MapCodec<TabletopBlock> CODEC=MapCodec.unit(()->new TabletopBlock(Properties.of()));
 private static final VoxelShape SHAPE=Block.box(0,0,0,16,14,16);
 public TabletopBlock(Properties props){super(props);}
 @Override protected MapCodec<? extends BaseEntityBlock> codec(){return CODEC;}
 @Override public RenderShape getRenderShape(BlockState s){return RenderShape.MODEL;}
 @Override protected VoxelShape getShape(BlockState s,BlockGetter level,BlockPos pos,CollisionContext ctx){return SHAPE;}
 @Override public @Nullable BlockEntity newBlockEntity(BlockPos pos,BlockState s){return new TabletopBlockEntity(pos,s);}
 @Override protected InteractionResult useWithoutItem(BlockState s,Level level,BlockPos pos,Player player,BlockHitResult hit){
  if(player instanceof ServerPlayer sp)TabletopLogic.open(sp,pos);
  return InteractionResult.SUCCESS;
 }
 @Override protected InteractionResult useItemOn(ItemStack held,BlockState s,Level level,BlockPos pos,Player p,net.minecraft.world.InteractionHand hand,BlockHitResult hit){return useWithoutItem(s,level,pos,p,hit);}
 private static void dropContents(Level level,BlockPos pos){
  if(level.isClientSide())return;
  if(level.getBlockEntity(pos) instanceof TabletopBlockEntity tile)for(ItemStack card:tile.drain())popResource(level,pos,card);
 }
 @Override public BlockState playerWillDestroy(Level level,BlockPos pos,BlockState state,Player p){dropContents(level,pos);return super.playerWillDestroy(level,pos,state,p);}
 @Override protected void affectNeighborsAfterRemoval(BlockState state,ServerLevel level,BlockPos pos,boolean moved){
  if(!level.getBlockState(pos).is(CaszualMtg.TABLETOP))dropContents(level,pos);
  super.affectNeighborsAfterRemoval(state,level,pos,moved);
 }
}
